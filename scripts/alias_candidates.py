#!/usr/bin/env python3
"""Report Sonarr alias candidates from recent grab history.

When Sonarr grabs a release whose title does not parse to any series, the grab
falls back to ID-matching and auto-import refuses it at import time. The
durable fix is upstream: the alternate-title lookup is a shared, community
dataset, so requesting the variant title there fixes every Sonarr install
(see the "matched by ID" section in docs/operations/troubleshooting.md).

This tool mines grab history for that class. It replays each distinct grabbed
release title through Sonarr's own parse API and classifies:

  TITLE_MATCH — parse resolves to the grabbed series: healthy, no alias needed
  WRONG_SHOW  — parse resolves to a different series: bad indexer match;
                report it to the indexer, it is NOT an alias candidate
  NO_MATCH    — parse finds no series: the alias candidate

Read-only: GET /history (grabbed events) and GET /parse only.

Usage:
  python3 scripts/alias_candidates.py                  # last 7 days, human output
  python3 scripts/alias_candidates.py --days 30
  python3 scripts/alias_candidates.py --series 25891   # one series only
  python3 scripts/alias_candidates.py --json           # machine-readable

Exit 0 = no candidates found; 1 = candidates found; 2 = cannot assess
(Sonarr unreachable / auth rejected) — the check_* family convention, so a
cron or the maintenance digest can consume the rc directly.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_URL = "http://localhost:8989/api/v3"
PAGE_SIZE = 1000
GRABBED_EVENT_TYPE = 1  # Sonarr HistoryEventType.Grabbed
PARSE_GAP_SECONDS = 0.05  # /parse is a real parse run; be polite
MAX_PARSE_CALLS = 500  # cap after a burst-sized sweep; truncation is reported


def request_json(url: str, api_key: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_grabbed(base_url: str, api_key: str, since: datetime,
                  series_id: int | None = None) -> list[dict]:
    """All grabbed-event history records at/after ``since`` (newest first)."""
    rows: list[dict] = []
    page = 1
    while True:
        params = (f"page={page}&pageSize={PAGE_SIZE}&sortKey=date"
                  f"&sortDirection=descending&eventType={GRABBED_EVENT_TYPE}")
        if series_id is not None:
            params += f"&seriesId={series_id}"
        records = request_json(f"{base_url.rstrip('/')}/history?{params}", api_key)
        batch = records.get("records", [])
        if not batch:
            break
        for rec in batch:
            when = _parse_sonarr_date(rec.get("date", ""))
            if when is not None and when < since:
                return rows  # sorted descending — everything older follows
            rows.append(rec)
        total = records.get("totalRecords", 0)
        if page * PAGE_SIZE >= total:
            break
        page += 1
    return rows


def _parse_sonarr_date(value: str) -> datetime | None:
    """ISO-8601; a naive timestamp is assumed UTC (Sonarr reports UTC)."""
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when


def classify_grabs(history_rows: list[dict], parse_fn,
                   gap: float = PARSE_GAP_SECONDS,
                   max_parse_calls: int = MAX_PARSE_CALLS) -> dict:
    """Classify distinct (series, release-title) grabs via ``parse_fn``.

    Pure aside from ``parse_fn``: tests inject a table; main() binds the
    HTTP parse call. ``parse_fn(title) -> {"id": int|None, "title": str}``
    (a normalized parse result; id None means no series parsed).
    """
    distinct: dict[tuple[int, str], str] = {}
    for rec in history_rows:
        series = rec.get("series") or {}
        sid, s_title = series.get("id"), series.get("title", "")
        source = (rec.get("sourceTitle") or "").strip()
        if sid is None or not source:
            continue  # unanchored history rows have no alias meaning
        distinct.setdefault((sid, s_title), source)

    truncated = False
    calls = 0
    results: list[dict] = []
    counts = {"TITLE_MATCH": 0, "WRONG_SHOW": 0, "NO_MATCH": 0}
    for (sid, s_title), source in sorted(distinct.items(),
                                         key=lambda kv: kv[0][1].lower()):
        if calls >= max_parse_calls:
            truncated = True
            break
        calls += 1
        parsed = parse_fn(source)
        parsed_id, parsed_title = parsed.get("id"), parsed.get("title", "")
        if parsed_id == sid:
            cls = "TITLE_MATCH"
        elif parsed_id is not None:
            cls = "WRONG_SHOW"
        else:
            cls = "NO_MATCH"
        counts[cls] += 1
        results.append({
            "series_id": sid,
            "series_title": s_title,
            "release_title": source,
            "class": cls,
            "parsed_title": parsed_title,
        })
        if gap:
            time.sleep(gap)

    return {
        "counts": counts,
        "grabs_checked": calls,
        "grabs_total": len(distinct),
        "truncated": truncated,
        "results": results,
    }


def sonarr_parse_fn(base_url: str, api_key: str):
    """parse_fn bound to Sonarr's GET /parse (normalized to {id, title})."""
    def parse_fn(title: str) -> dict:
        url = (f"{base_url.rstrip('/')}/parse?"
               f"title={urllib.parse.quote(title, safe='')}")
        resp = request_json(url, api_key)
        series = resp.get("series") or {}
        return {"id": series.get("id"), "title": series.get("title", "")}
    return parse_fn


def print_report(report: dict, window_days: int) -> None:
    counts = report["counts"]
    print(f"Sonarr alias candidates — last {window_days} day(s) "
          f"({report['grabs_checked']}/{report['grabs_total']} distinct grabs "
          "parsed)")
    if report["truncated"]:
        print(f"  WARNING: parse-call cap ({MAX_PARSE_CALLS}) reached — "
              "narrow the window with --days/--series", file=sys.stderr)
    print(f"  TITLE_MATCH: {counts['TITLE_MATCH']}  "
          f"WRONG_SHOW: {counts['WRONG_SHOW']}  "
          f"NO_MATCH: {counts['NO_MATCH']}")
    candidates = [r for r in report["results"] if r["class"] == "NO_MATCH"]
    if candidates:
        print("\nAlias candidates (request these variant titles upstream):")
        for r in sorted(candidates, key=lambda r: r["series_title"].lower()):
            print(f"  [{r['series_id']}] {r['series_title']}: "
                  f"{r['release_title']}")
    wrong = [r for r in report["results"] if r["class"] == "WRONG_SHOW"]
    if wrong:
        print("\nWrong-show grabs (bad indexer matches — report, don't alias):")
        for r in sorted(wrong, key=lambda r: r["series_title"].lower()):
            print(f"  [{r['series_id']}] {r['series_title']}: "
                  f"{r['release_title']} -> {r['parsed_title']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("SONARR_URL", DEFAULT_URL),
                    help="Sonarr API base (default %(default)s)")
    ap.add_argument("--api-key", default=os.environ.get("SONARR_API_KEY", ""),
                    help="Sonarr API key (default $SONARR_API_KEY)")
    ap.add_argument("--days", type=int, default=7,
                    help="grab-history window in days (default %(default)s)")
    ap.add_argument("--series", type=int, default=None,
                    help="limit to one Sonarr series ID")
    ap.add_argument("--gap", type=float, default=PARSE_GAP_SECONDS,
                    help="seconds between parse calls (default %(default)s)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args(argv)

    if not args.api_key:
        print("error: no API key (set SONARR_API_KEY or pass --api-key)",
              file=sys.stderr)
        return 2
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    try:
        rows = fetch_grabbed(args.url, args.api_key, since, args.series)
        report = classify_grabs(rows, sonarr_parse_fn(args.url, args.api_key),
                                gap=args.gap)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            OSError) as exc:
        print(f"CHECK SKIPPED: cannot assess Sonarr grab history: {exc}",
              file=sys.stderr)
        return 2

    report["window_days"] = args.days
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args.days)

    return 1 if report["counts"]["NO_MATCH"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
