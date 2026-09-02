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
  * with --verify, re-parses every new queue item's title and aborts the
    sweep when any of them is NO_MATCH or resolves to a different series
    than the one it was grabbed for (the ARK-into-TPB-Animated class).

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
import urllib.parse
import urllib.request

DEFAULT_URL = "http://localhost:8989/api/v3"
DEFAULT_TIMEOUT = 60
DEFAULT_BATCH = 20
DEFAULT_GAP = 60
MISSING_PAGE_SIZE = 200


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


def fetch_queue_ids(base_url, api_key, timeout=DEFAULT_TIMEOUT):
    """Set of downloadIds currently in the queue (verify watermark)."""
    d = _request(base_url, api_key, "/queue?page=1&pageSize=200",
                 timeout=timeout)
    return {r.get("downloadId") for r in (d.get("records") or [])
            if r.get("downloadId")}


def verify_new_items(base_url, api_key, before_ids, timeout=DEFAULT_TIMEOUT):
    """Re-parse every queue item that appeared since before_ids.

    Returns (ok, offenders). ok is False when any new item's /parse
    result is NO_MATCH (no series) or resolves to a different series than
    the queue item's own seriesId -- the Id-matched wrong-show grab class
    (ARK into TPB-Animated, The Sticky into The Tick, ...). Offenders are
    (release title, queue seriesId, parsed series title or "NO_MATCH").
    """
    d = _request(base_url, api_key, "/queue?page=1&pageSize=200",
                 timeout=timeout)
    offenders = []
    for r in d.get("records") or []:
        dl = r.get("downloadId")
        if not dl or dl in before_ids:
            continue
        sid = r.get("seriesId")
        title = str(r.get("title", "?"))[:90]
        try:
            parsed = _request(
                base_url, api_key,
                f"/parse?title={urllib.parse.quote(title)}", timeout=timeout)
        except Exception as exc:  # conservative: cannot verify => suspect
            offenders.append((title, sid, f"parse error: {exc}"))
            continue
        pseries = parsed.get("series") or {}
        if pseries.get("id") != sid or not (parsed.get("episodes") or []):
            offenders.append((title, sid, pseries.get("title") or "NO_MATCH"))
    return (not offenders), offenders


def run(base_url, api_key, series_ids, all_series, batch_size, gap,
        checkpoint, verify, apply, timeout=DEFAULT_TIMEOUT):
    """Run the scoped sweep; returns (exit_code, summary)."""
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
                # Read-only pre-flight: the code path is exercised against
                # the live queue; nothing was searched so nothing is new.
                before = fetch_queue_ids(base_url, api_key, timeout)
                ok, offenders = verify_new_items(base_url, api_key, before,
                                                 timeout)
                state = "OK" if ok else f"SUSPECT: {offenders[0]}"
                print(f"  verify (dry-run, nothing searched): "
                      f"{len(offenders)} new item(s) -> {state}")
            continue

        before = fetch_queue_ids(base_url, api_key, timeout)
        for c in cmds:
            _request(base_url, api_key, "/command", "POST", c, timeout)
        if gap:
            print(f"  waiting {gap}s before verify/review...")
            time.sleep(gap)
        if verify:
            ok, offenders = verify_new_items(base_url, api_key, before,
                                             timeout)
            if not ok:
                print("VERIFY FAILED -- aborting sweep:")
                for title, sid, parsed in offenders:
                    print(f"  {title} | queue series {sid} | parsed {parsed}")
                return 2, (f"verify-abort: {len(offenders)} suspect queue "
                           "item(s); review and remove before continuing")
            print(f"  verify: {len(offenders)} new item(s), all parse to "
                  "their own series")
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
    scope.add_argument("--series", type=int, action="append", metavar="ID",
                       help="sonarr series id(s) to search (repeatable)")
    scope.add_argument("--all", action="store_true",
                       help="all monitored series with missing episodes")
    ap.add_argument("--url", default=os.environ.get("SONARR_URL", DEFAULT_URL),
                    help="API base URL (default: %(default)s)")
    ap.add_argument("--api-key", default="",
                    help="API key (default: $SONARR_API_KEY)")
    ap.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                    help="max episodes searched per batch (default: %(default)s)")
    ap.add_argument("--gap", type=int, default=DEFAULT_GAP,
                    help="pause seconds between batches (default: %(default)s; 0 disables)")
    ap.add_argument("--yes", action="store_true",
                    help="disable checkpoints; run every batch in one pass")
    ap.add_argument("--verify", action="store_true",
                    help="parse-check new queue items after each batch; abort "
                         "on NO_MATCH or a different series than the one searched")
    ap.add_argument("--apply", action="store_true",
                    help="actually POST search commands; default is a dry run")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="HTTP timeout seconds (default: %(default)s)")
    args = ap.parse_args()

    api_key = args.api_key or os.environ.get("SONARR_API_KEY", "")
    if not api_key:
        print("SONARR_API_KEY not set (pass --api-key or export SONARR_API_KEY)",
              file=sys.stderr)
        return 1

    code, summary = run(args.url, api_key, args.series, args.all, args.batch,
                        args.gap, checkpoint=not args.yes, verify=args.verify,
                        apply=args.apply, timeout=args.timeout)
    print(summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
