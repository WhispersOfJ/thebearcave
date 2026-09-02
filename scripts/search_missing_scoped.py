#!/usr/bin/env python3
"""Scoped missing-episode search for Sonarr.

Replaces whole-series "Search Missing" sweeps with small, batched, paced,
season/episode-scoped searches, turning a blind 200+-episode blast into a
supervised process that stops for review and aborts early when an
Id-matched / wrong-show grab appears.

Why this exists: Sonarr's own MissingEpisodeSearch already groups by
series/season, but it processes a whole series in one command with no
review gap and auto-grabs everything the indexer returns. Releases whose
titles don't parse to the searched series fall back to the "matched by
ID" path at grab time (ParsingService.FindSeries falls back to the search
criteria's tvdbid) — the class that produced the 2026-09-01 pile-up of
230 stuck items and the wrong-show imports that followed. This wrapper:

  * enumerates missing monitored episodes (wanted/missing API),
  * groups them by (series, season) exactly like Sonarr does internally,
  * orders groups by lastSearchTime so interrupted runs resume in the
    same deterministic order (never-searched first, like Sonarr),
  * searches in batches of --batch episodes with a --gap pause,
  * stops after each batch for review unless --yes (checkpoint),
  * with --verify, re-parses every new grab's title -- Grabbed history
    events newer than a batch-start watermark plus new queue items,
    including unknown-series ones -- and aborts the sweep (rc 2) when any
    is NO_MATCH, parses to no episodes, or resolves to a different series
    than the one it was grabbed for (the ARK-into-TPB-Animated class),
    even if the download fails before it ever reaches the queue. When the
    history API is unavailable the queue diff alone still runs.

Read-only against Sonarr except for the POST /command calls --apply
makes. Dry-run by default.

Exit codes:
  0  completed (or stopped at a checkpoint)
  1  API/network failure (key missing or an endpoint could not be read)
  2  --verify found a NO_MATCH / wrong-series queue item (sweep aborted)

Usage:
  python3 scripts/search_missing_scoped.py --series 25891            # dry-run, one series
  python3 scripts/search_missing_scoped.py --all --batch 10          # dry-run, whole library
  python3 scripts/search_missing_scoped.py --series 25891 --apply --verify
  python3 scripts/search_missing_scoped.py --all --apply --yes       # no checkpoints
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://localhost:8989/api/v3"
DEFAULT_TIMEOUT = 60
DEFAULT_BATCH = 20
DEFAULT_GAP = 60
MISSING_PAGE_SIZE = 200
QUEUE_PAGE_SIZE = 100
HISTORY_PAGE_SIZE = 100
COMMAND_POLL_INTERVAL = 1
COMMAND_WAIT_TIMEOUT = 300


def positive_int(value):
    """Argparse type for values that must be greater than zero."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def nonnegative_int(value):
    """Argparse type for values that may be zero but not negative."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _request(base_url, api_key, path, method="GET", body=None, timeout=DEFAULT_TIMEOUT):
    """Send an API request; return the parsed JSON response ({} if empty)."""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base_url.rstrip('/')}{path}",
                                 data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode()) if raw else {}


def fetch_missing(base_url, api_key, series_ids=None, timeout=DEFAULT_TIMEOUT):
    """All missing monitored episodes, optionally filtered to series_ids.

    Series-scoped runs hit /episode?seriesId= (one small request per
    series, no paging); --all runs paginate /wanted/missing. Both return
    the same record shape (id, seriesId, seasonNumber, episodeNumber,
    title, lastSearchTime) and filter out unmonitored / hasFile rows
    defensively.
    """
    out = []
    if series_ids:
        for sid in series_ids:
            recs = _request(base_url, api_key, f"/episode?seriesId={sid}",
                            timeout=timeout)
            if not isinstance(recs, list):
                raise RuntimeError(
                    f"/episode returned an unexpected shape for series {sid}")
            out.extend(r for r in recs
                       if r.get("monitored", True) is not False
                       and not r.get("hasFile"))
        return out
    page = 1
    while True:
        # No sort params: the endpoint rejects sortDirection=asc (only desc
        # is accepted), and ordering is irrelevant -- build_groups re-sorts
        # by lastSearchTime anyway.
        d = _request(
            base_url, api_key,
            f"/wanted/missing?page={page}&pageSize={MISSING_PAGE_SIZE}",
            timeout=timeout)
        recs = d.get("records") or []
        out.extend(r for r in recs
                   if r.get("monitored", True) is not False
                   and not r.get("hasFile"))
        total = d.get("totalRecords", 0)
        if not recs or page * MISSING_PAGE_SIZE >= total:
            break
        page += 1
    return out


def build_groups(missing):
    """Group episodes by (seriesId, seasonNumber), ordered for resume.

    Mirrors Sonarr's SearchForBulkEpisodes grouping. Groups are ordered
    by their oldest lastSearchTime (never-searched first, using Sonarr's
    DateTime.MinValue convention), then seriesId/seasonNumber, so an
    interrupted run resumes in a stable order.
    """
    groups = {}
    for r in missing:
        key = (r["seriesId"], r["seasonNumber"])
        groups.setdefault(key, []).append(r)
    out = []
    for (sid, sn), eps in groups.items():
        searches = [e["lastSearchTime"] for e in eps if e.get("lastSearchTime")]
        out.append({
            "seriesId": sid,
            "seasonNumber": sn,
            "episodes": sorted(eps, key=lambda e: e["episodeNumber"]),
            "last_search": min(searches) if searches else None,
        })
    out.sort(key=lambda g: (g["last_search"] or "0000-01-01T00:00:00Z",
                            g["seriesId"], g["seasonNumber"]))
    return out


def split_batches(groups, batch_size):
    """Chunk ordered groups into batches of at most batch_size episodes.

    A single season group is never split (a SeasonSearch covers the whole
    season at once), so an oversized group forms a batch of its own.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    batches, cur, n = [], [], 0
    for g in groups:
        if cur and n + len(g["episodes"]) > batch_size:
            batches.append(cur)
            cur, n = [], 0
        cur.append(g)
        n += len(g["episodes"])
    if cur:
        batches.append(cur)
    return batches


def search_commands_for(batch):
    """Command payloads for a batch, mirroring Sonarr's search flow:
    SeasonSearch for multi-episode seasons, EpisodeSearch for singles."""
    cmds = []
    for g in batch:
        if len(g["episodes"]) > 1:
            cmds.append({"name": "SeasonSearch",
                         "seriesId": g["seriesId"],
                         "seasonNumber": g["seasonNumber"]})
        else:
            cmds.append({"name": "EpisodeSearch",
                         "episodeIds": [g["episodes"][0]["id"]]})
    return cmds


def _fetch_paged_records(base_url, api_key, endpoint, page_size, timeout):
    """Read all pages from a Sonarr paginated endpoint."""
    records = []
    page = 1
    while True:
        separator = "&" if "?" in endpoint else "?"
        d = _request(base_url, api_key,
                     f"{endpoint}{separator}page={page}&pageSize={page_size}",
                     timeout=timeout)
        if not isinstance(d, dict):
            raise RuntimeError(f"{endpoint} returned an unexpected shape")
        page_records = d.get("records") or []
        records.extend(page_records)
        total = d.get("totalRecords")
        if not page_records or (total is not None and len(records) >= total):
            return records
        page += 1


def fetch_queue_records(base_url, api_key, timeout=DEFAULT_TIMEOUT):
    """Read the complete queue, including unknown-series items."""
    return _fetch_paged_records(
        base_url, api_key,
        "/queue?includeUnknownSeriesItems=true",
        QUEUE_PAGE_SIZE, timeout)


def fetch_queue_ids(base_url, api_key, timeout=DEFAULT_TIMEOUT):
    """Set of downloadIds currently in the complete queue."""
    return {r.get("downloadId") for r in fetch_queue_records(
        base_url, api_key, timeout) if r.get("downloadId")}


def _parse_and_classify(base_url, api_key, title, series_id,
                        expected_series_ids, download_id, timeout):
    """Return an offender when a title cannot prove a requested-series match."""
    try:
        parsed = _request(
            base_url, api_key,
            f"/parse?title={urllib.parse.quote(title, safe='')}", timeout=timeout)
    except Exception as exc:  # conservative: cannot verify => suspect
        return {"downloadId": download_id, "title": title,
                "seriesId": series_id, "parsed": f"parse error: {exc}"}
    pseries = parsed.get("series") or {}
    if (series_id not in expected_series_ids
            or pseries.get("id") != series_id
            or not (parsed.get("episodes") or [])):
        return {"downloadId": download_id, "title": title,
                "seriesId": series_id,
                "parsed": pseries.get("title") or "NO_MATCH"}
    return None


def verify_new_items(base_url, api_key, before_ids, expected_series_ids,
                     timeout=DEFAULT_TIMEOUT):
    """Re-parse every queue item that appeared since before_ids.

    Returns (ok, offenders). ok is False when any new item's /parse
    result is NO_MATCH (no series) or resolves to a different series than
    the queue item's own seriesId -- the Id-matched wrong-show grab class
    (ARK into TPB-Animated, The Sticky into The Tick, ...). Unknown-series
    items (seriesId is None) can never be verified and are always
    suspects. Offenders are dicts {downloadId, title, seriesId, parsed}.
    """
    offenders = []
    for r in fetch_queue_records(base_url, api_key, timeout):
        dl = r.get("downloadId")
        if not dl or dl in before_ids:
            continue
        offender = _parse_and_classify(
            base_url, api_key, str(r.get("title", "?")), r.get("seriesId"),
            expected_series_ids, dl, timeout)
        if offender:
            offenders.append(offender)
    return (not offenders), offenders


def _grab_key(record):
    """Return a sortable (date, id) key for a grabbed-history record."""
    return (str(record.get("date") or ""), int(record.get("id") or 0))


def _is_grabbed(record):
    """Accept Sonarr's numeric and string forms of the Grabbed event type."""
    event_type = record.get("eventType")
    return event_type == 1 or str(event_type).casefold() == "grabbed"


def _fetch_grab_history(base_url, api_key, timeout, stop_at=None,
                        first_page_only=False):
    """Read newest grabbed events, stopping once the watermark is reached."""
    records = []
    page = 1
    while True:
        d = _request(
            base_url, api_key,
            "/history?eventType=1&sortKey=date&sortDirection=descending"
            f"&page={page}&pageSize={HISTORY_PAGE_SIZE}", timeout=timeout)
        if not isinstance(d, dict):
            raise RuntimeError("/history returned an unexpected shape")
        page_records = [r for r in (d.get("records") or [])
                        if r.get("id") and _is_grabbed(r)]
        records.extend(page_records)
        if first_page_only or (
                stop_at is not None and page_records and all(
                    _grab_key(r) <= stop_at for r in page_records)):
            break
        total = d.get("totalRecords")
        if not d.get("records") or (
                total is not None
                and page * HISTORY_PAGE_SIZE >= total):
            break
        page += 1
    return records


def fetch_grab_watermark(base_url, api_key, timeout=DEFAULT_TIMEOUT):
    """Return the batch-start (max grabbed date, id) watermark.

    Grabs that fail before they are ever queue-visible (dead NZBs failing
    seconds after grab) never appear in the queue, so a queue diff alone
    cannot see them. The watermark lets verify re-read /history for Grabbed
    events newer than the batch start. None means the history API was
    unavailable; the caller must use the queue-diff-only fallback rather
    than treating the entire recent history as new.
    """
    try:
        records = _fetch_grab_history(base_url, api_key, timeout,
                                       first_page_only=True)
    except Exception:
        return None
    return max((_grab_key(r) for r in records), default=("", 0))


def new_grab_offenders(base_url, api_key, watermark, expected_series_ids,
                       timeout=DEFAULT_TIMEOUT):
    """Parse every Grabbed history event newer than the watermark.

    Returns (available, offenders, count). available=False when the history
    API could not be read or its batch-start watermark was unavailable (the
    caller falls back to the queue diff alone). Offenders have the same
    dict shape as verify_new_items; any grab whose title parses NO_MATCH,
    to no episodes, or to a different series than the grab's own seriesId
    is listed regardless of whether the download is still in the queue.
    """
    if watermark is None:
        return False, [], 0
    try:
        records = _fetch_grab_history(base_url, api_key, timeout, watermark)
    except Exception:
        return False, [], 0
    offenders = []
    new_records = [r for r in records if _grab_key(r) > watermark]
    for r in new_records:
        offender = _parse_and_classify(
            base_url, api_key, str(r.get("sourceTitle") or "?"),
            r.get("seriesId"), expected_series_ids, r.get("downloadId"), timeout)
        if offender:
            offenders.append(offender)
    return True, offenders, len(new_records)


def _command_result(record):
    """Return True/False for a terminal command, or None while it runs."""
    status = str(record.get("status") or "").casefold()
    if status == "failed":
        return False
    if status == "completed":
        return str(record.get("result") or "").casefold() not in (
            "failed", "cancelled")
    return None


def wait_for_command(base_url, api_key, response, timeout=DEFAULT_TIMEOUT):
    """Wait for a posted Sonarr command to reach a terminal state."""
    command_id = response.get("id") if isinstance(response, dict) else None
    if not command_id:
        return False
    result = _command_result(response)
    if result is not None:
        return result
    deadline = time.monotonic() + COMMAND_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        try:
            current = _request(base_url, api_key,
                               f"/command/{command_id}", timeout=timeout)
        except Exception:
            return False
        result = _command_result(current)
        if result is not None:
            return result
        time.sleep(min(COMMAND_POLL_INTERVAL,
                       max(0, deadline - time.monotonic())))
    return False


def merge_offenders(*groups):
    """Dedupe offender dicts from history and queue verification.

    A downloadId is shared by the two views when available. A missing id
    gets a stable content key so multiple unknown queue items are retained.
    """
    out = {}
    for group in groups:
        for offender in group:
            key = offender.get("downloadId")
            if not key:
                key = (offender.get("title"), offender.get("seriesId"),
                       offender.get("parsed"))
            out[key] = offender
    return list(out.values())


def run(base_url, api_key, series_ids, all_series, batch_size, gap,
        checkpoint, verify, apply, timeout=DEFAULT_TIMEOUT):
    """Run the scoped sweep; returns (exit_code, summary)."""
    if batch_size < 1:
        return 1, "batch must be greater than zero"
    if gap < 0:
        return 1, "gap cannot be negative"
    if timeout < 1:
        return 1, "timeout must be greater than zero"
    if not all_series and not series_ids:
        return 1, "at least one series or --all is required"
    missing = fetch_missing(base_url, api_key,
                            None if all_series else series_ids, timeout)
    if not missing:
        return 0, "no missing episodes to search"
    groups = build_groups(missing)
    batches = split_batches(groups, batch_size)
    print(f"missing episodes: {len(missing)} across {len(groups)} season "
          f"group(s) -> {len(batches)} batch(es)")

    for i, batch in enumerate(batches, 1):
        cmds = search_commands_for(batch)
        eps = sum(len(g["episodes"]) for g in batch)
        print(f"batch {i}/{len(batches)}: {eps} episode(s), {len(cmds)} command(s)")
        for g in batch:
            print(f"  series {g['seriesId']} S{g['seasonNumber']:02d} "
                  f"({len(g['episodes'])} missing, last search "
                  f"{g['last_search'] or 'never'})")
        if not apply:
            for c in cmds:
                print(f"  [dry] POST /command {c}")
            if verify:
                # Read-only pre-flight: both verify legs run against the
                # live APIs; nothing was searched so nothing is new.
                expected_series_ids = {g["seriesId"] for g in batch}
                watermark = fetch_grab_watermark(base_url, api_key, timeout)
                hist_ok, hist, _ = new_grab_offenders(
                    base_url, api_key, watermark, expected_series_ids, timeout)
                before = fetch_queue_ids(base_url, api_key, timeout)
                _, qoff = verify_new_items(base_url, api_key, before,
                                           expected_series_ids, timeout)
                if not hist_ok:
                    print("  verify (dry-run): history API unavailable; "
                          "queue diff only")
                offenders = merge_offenders(hist, qoff)
                state = "OK" if not offenders else f"SUSPECT: {offenders[0]['parsed']}"
                print(f"  verify (dry-run, nothing searched): "
                      f"{len(offenders)} suspect(s) -> {state}")
            continue

        expected_series_ids = {g["seriesId"] for g in batch}
        watermark = fetch_grab_watermark(base_url, api_key, timeout)
        before = fetch_queue_ids(base_url, api_key, timeout)
        command_failed = False
        for c in cmds:
            response = _request(base_url, api_key, "/command", "POST", c,
                                timeout=timeout)
            if not wait_for_command(base_url, api_key, response, timeout):
                command_failed = True
                break
        if gap:
            print(f"  waiting {gap}s before verify/review...")
            time.sleep(gap)
        if verify:
            hist_ok, hist, hist_count = new_grab_offenders(
                base_url, api_key, watermark, expected_series_ids, timeout)
            _, qoff = verify_new_items(base_url, api_key, before,
                                       expected_series_ids, timeout)
            if not hist_ok:
                print("  verify: history API unavailable; queue diff only")
            offenders = merge_offenders(hist, qoff)
            if offenders:
                print("VERIFY FAILED -- aborting sweep:")
                for o in offenders:
                    print(f"  {o['title']} | series {o['seriesId']} | "
                          f"parsed {o['parsed']}")
                return 2, (f"verify-abort: {len(offenders)} suspect grab(s) "
                           "(grabbed or queued); review before continuing")
            print(f"  verify: {hist_count} new grab(s), {len(qoff)} new queue "
                  "item(s), all parse to their own series")
        if command_failed:
            return 1, "search command did not complete before timeout"
        if checkpoint and i < len(batches):
            print("checkpoint: batch {i} done. Review the queue, then "
                  "re-run with the same arguments to resume (groups are "
                  "ordered by lastSearchTime).".replace("{i}", str(i)))
            return 0, f"checkpoint after batch {i}/{len(batches)}"
    return 0, "complete"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--series", type=positive_int, action="append", metavar="ID",
                       help="sonarr series id(s) to search (repeatable)")
    scope.add_argument("--all", action="store_true",
                       help="all monitored series with missing episodes")
    ap.add_argument("--url", default=os.environ.get("SONARR_URL", DEFAULT_URL),
                    help="API base URL (default: %(default)s)")
    ap.add_argument("--api-key", default="",
                    help="API key (default: $SONARR_API_KEY)")
    ap.add_argument("--batch", type=positive_int, default=DEFAULT_BATCH,
                    help="max episodes searched per batch (default: %(default)s)")
    ap.add_argument("--gap", type=nonnegative_int, default=DEFAULT_GAP,
                    help="pause seconds between batches (default: %(default)s; 0 disables)")
    ap.add_argument("--yes", action="store_true",
                    help="disable checkpoints; run every batch in one pass")
    ap.add_argument("--verify", action="store_true",
                    help="parse-check new grabs (history watermark) and new "
                         "queue items after each batch; abort on NO_MATCH or "
                         "a different series than the one searched")
    ap.add_argument("--apply", action="store_true",
                    help="actually POST search commands; default is a dry run")
    ap.add_argument("--timeout", type=positive_int, default=DEFAULT_TIMEOUT,
                    help="HTTP timeout seconds (default: %(default)s)")
    args = ap.parse_args()

    api_key = args.api_key or os.environ.get("SONARR_API_KEY", "")
    if not api_key:
        print("SONARR_API_KEY not set (pass --api-key or export SONARR_API_KEY)",
              file=sys.stderr)
        return 1

    try:
        code, summary = run(args.url, api_key, args.series, args.all, args.batch,
                            args.gap, checkpoint=not args.yes, verify=args.verify,
                            apply=args.apply, timeout=args.timeout)
    except (urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
        print(f"API/network failure: {exc}", file=sys.stderr)
        return 1
    print(summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
