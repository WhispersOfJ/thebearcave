#!/usr/bin/env python3
"""Flag *arr import queues backing up with stuck completed downloads.

Sonarr/Radarr keep a download in the queue after it completes until the
automatic import moves the file into the library. Normally that takes
seconds. But a class of grabs cannot be auto-imported at all — releases
the *arr only matched to a series/movie *by ID* at grab time (bulk
series searches and indexer results whose titles don't title-match, e.g.
an ARK release returned for Trailer Park Boys) are deliberately held for
manual review, and Sonarr surfaces them as a warning on the queue item:

    Found matching series via grab history, but release was matched to
    series by ID. Automatic import is not possible. (importBlocked)

On 2026-09-02 one mass search left 230 such items piled up — 219
importBlocked + 11 importPending, all completed, all warning — for two
days before anyone noticed, because nothing watched the *arr import
queues. This check closes that gap: each morning it counts queue items
that are completed-and-stuck (status=completed, warning, importBlocked
or importPending) and fails once the count exceeds a threshold, long
before the pile reaches hundreds.

Scripts/drain_sonarr_queue.py (--app radarr|sonarr) is the remediation:
it manually imports what resolves and removes the rest.

Exit codes (the check_* family contract, read by the maintenance digest):
  0  stuck count <= threshold (healthy; nothing needs attention)
  1  stuck count > threshold (FAIL — drain the queue)
  2  app unreachable / API error / key missing (soft WARN — cannot
     assess; a sleeping stack must not spam a FAIL)

Usage:
  python3 scripts/check_arr_import_queue.py --app sonarr
  python3 scripts/check_arr_import_queue.py --app radarr
  python3 scripts/check_arr_import_queue.py --app radarr --threshold 3
  python3 scripts/check_arr_import_queue.py --offline  # CI/no-live-app
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URLS = {
    "sonarr": "http://localhost:8989/api/v3",
    "radarr": "http://localhost:7878/api/v3",
}
DEFAULT_TIMEOUT = 30
DEFAULT_THRESHOLD = 10


def fetch_queue(base_url: str, api_key: str, timeout: int) -> dict:
    """Fetch every queue page. Raises on any failure."""
    if not api_key:
        raise RuntimeError("API key not set")
    page_size = 200
    all_records = []
    page = 1
    total_records = None
    while True:
        url = (f"{base_url.rstrip('/')}/queue?page={page}"
               f"&pageSize={page_size}")
        req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ValueError("queue API response has no records list")
        records = data["records"]
        all_records.extend(records)
        raw_total = data.get("totalRecords")
        if isinstance(raw_total, int) and raw_total >= 0:
            total_records = raw_total
        if not records or len(records) < page_size or (
                total_records is not None and len(all_records) >= total_records):
            return {**data, "records": all_records,
                    "totalRecords": total_records if total_records is not None
                    else len(all_records)}
        page += 1


def stuck_items(data: dict) -> list[dict]:
    """Queue records that are completed and held from import.

    ``stuck`` = status completed AND trackedDownloadStatus warning AND
    trackedDownloadState in (importBlocked, importPending) — the exact
    population scripts/drain_sonarr_queue.py acts on. A healthy queue is
    empty of these (the import consumes them within minutes); a pile-up
    means downloads finished faster than the import guard could clear
    them (the 2026-09-02 230-item class). Returns [] on a well-formed
    empty queue; the caller validates the response shape separately.
    """
    if not isinstance(data, dict):
        return []
    recs = data.get("records")
    if not isinstance(recs, list):
        return []
    stuck = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        if r.get("status") != "completed":
            continue
        if r.get("trackedDownloadStatus") != "warning":
            continue
        if r.get("trackedDownloadState") not in ("importBlocked",
                                                 "importPending"):
            continue
        stuck.append(r)
    return stuck


def check(base_url: str, api_key: str, timeout: int,
          threshold: int) -> tuple[int, str]:
    """Run the check for one app. Returns (exit_code, message)."""
    try:
        data = fetch_queue(base_url, api_key, timeout)
    except (urllib.error.URLError, RuntimeError, json.JSONDecodeError,
            OSError) as exc:
        return 2, f"app queue API unreachable: {exc}"

    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        return 2, "could not parse queue API response (no records list)"
    stuck = stuck_items(data)
    n = len(stuck)
    blocked = sum(1 for r in stuck
                  if r.get("trackedDownloadState") == "importBlocked")
    pending = n - blocked
    state = (f"{n} stuck completed item(s) ({blocked} importBlocked, "
             f"{pending} importPending)")
    if n > threshold:
        return 1, (
            f"{state} > threshold {threshold}. Imports are held for manual "
            "review (matched-by-ID or unimportable); drain with "
            "scripts/drain_sonarr_queue.py --app <sonarr|radarr> --apply")
    if n:
        return 0, f"{state} (<= threshold {threshold}) — no action needed"
    return 0, "no stuck completed items (0 <= threshold %d)" % threshold


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", choices=sorted(DEFAULT_URLS), default="sonarr",
                    help="which *arr to check (default: %(default)s)")
    ap.add_argument("--url", default="",
                    help="API base URL (default: per-app localhost or $APP_URL)")
    ap.add_argument("--api-key", default="",
                    help="API key (default: $SONARR_API_KEY / $RADARR_API_KEY)")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help="max stuck items before FAIL (default: %(default)s)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="HTTP timeout seconds (default: %(default)s)")
    ap.add_argument("--offline", action="store_true",
                    help="CI mode: skip the live check entirely (exit 0)")
    args = ap.parse_args()

    if args.offline:
        print("OK (offline mode — live import-queue check skipped)")
        return 0

    env_suffix = args.app.upper()
    url = args.url or os.environ.get(f"{env_suffix}_URL",
                                     DEFAULT_URLS[args.app])
    api_key = args.api_key or os.environ.get(f"{env_suffix}_API_KEY", "")
    if not api_key:
        print(f"{env_suffix}_API_KEY not set "
              f"(pass --api-key or export {env_suffix}_API_KEY)",
              file=sys.stderr)
        return 2

    code, msg = check(url, api_key, args.timeout, args.threshold)
    prefix = {0: "PASS", 1: "FAIL", 2: "SKIP"}[code]
    print(f"{prefix} {args.app} import queue: {msg}")
    return code


if __name__ == "__main__":
    sys.exit(main())
