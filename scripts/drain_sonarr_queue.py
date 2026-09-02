#!/usr/bin/env python3
"""Drain stuck completed items from the Sonarr queue.

Sonarr keeps completed downloads in the queue when the automatic import
fails (permissions, naming, a stuck download-client entry). This tool
unsticks them the same way the UI's manual import does:

  1. For each completed queue item, preview candidates via
     /api/v3/manualimport?downloadId=<id>&filterExistingFiles=true
  2. POST /api/v3/command {name: ManualImport, files: [...]} to import the
     resolved series/episodes using the quality/languages from the preview
  3. If the preview is empty or the command fails, remove the queue item
     (removeFromClient=true, blocklist=false) so the episodes stay
     monitored and can be re-fetched

Dry-run by default: prints what would happen. Pass --apply to act.

Exit codes:
  0  ran (dry-run, imported, or removed)
  1  API/network failure (key missing or queue could not be fetched)

Usage:
  python3 scripts/drain_sonarr_queue.py
  python3 scripts/drain_sonarr_queue.py --apply --limit 10
  python3 scripts/drain_sonarr_queue.py --url http://localhost:8989/api/v3 --api-key "$SONARR_API_KEY"
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://localhost:8989/api/v3"  # all paths below are API-relative
DEFAULT_TIMEOUT = 60
DEFAULT_LIMIT = 5


def _request(base_url, api_key, path, method="GET", body=None, timeout=DEFAULT_TIMEOUT):
    """Send an API request; return the parsed JSON response ({} if empty)."""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base_url.rstrip('/')}{path}",
                                 data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode()) if raw else {}


def build_import_files(preview, download_id):
    """Build ManualImport file entries from a manualimport preview.

    Returns (files, None) when every candidate resolves to a series and
    episodes, and ([], reason) otherwise. Import is all-or-nothing: a
    partially-resolved download falls back to queue removal rather than a
    half-import.
    """
    if not preview:
        return [], "empty preview"
    files = []
    for cand in preview:
        series = cand.get("series") or {}
        episodes = cand.get("episodes") or []
        if not series.get("id") or not episodes:
            return [], "unresolved candidate (no series/episodes)"
        files.append({
            "path": cand.get("path"),
            "seriesId": series["id"],
            "episodeIds": [e["id"] for e in episodes],
            "quality": cand.get("quality"),
            "languages": cand.get("languages"),
            "downloadId": download_id,
        })
    return files, None


def import_one(base_url, api_key, item, timeout=DEFAULT_TIMEOUT):
    """Try a full manual import for one queue item. Returns (ok, note)."""
    download_id = item.get("downloadId")
    if not download_id:
        return False, "no downloadId"
    try:
        preview = _request(
            base_url, api_key,
            f"/manualimport?downloadId={download_id}&filterExistingFiles=true",
            timeout=timeout)
    except Exception as exc:  # any API failure -> fall back to removal
        return False, f"preview error: {exc}"
    files, err = build_import_files(preview, download_id)
    if err:
        return False, err
    try:
        cmd = _request(base_url, api_key, "/command", "POST",
                       {"name": "ManualImport", "files": files, "importMode": "auto"},
                       timeout=timeout)
    except Exception as exc:  # any API failure -> fall back to removal
        return False, f"command error: {exc}"
    cid = cmd.get("id")
    if not cid:
        return False, f"no command id: {json.dumps(cmd)[:120]}"
    for _ in range(10):
        time.sleep(1.0)
        st = _request(base_url, api_key, f"/command/{cid}", timeout=timeout)
        if st.get("status") in ("completed", "failed"):
            return st.get("status") == "completed", (
                f"command {st.get('status')} {st.get('message') or ''}")
    return True, f"command {cid} still running (assumed ok)"


def remove_item(base_url, api_key, item, timeout=DEFAULT_TIMEOUT):
    """Remove a queue item without blacklisting, keeping episodes monitored."""
    qid = item["id"]
    params = urllib.parse.urlencode({"removeFromClient": "true", "blocklist": "false"})
    _request(base_url, api_key, f"/queue/{qid}?{params}", "DELETE", timeout=timeout)


def drain(base_url, api_key, limit, status, apply, timeout=DEFAULT_TIMEOUT):
    """Process matching queue items; returns (exit_code, summary)."""
    try:
        q = _request(base_url, api_key,
                     f"/queue?page=1&pageSize=200&status={urllib.parse.quote(status)}",
                     timeout=timeout)
    except (urllib.error.URLError, RuntimeError, json.JSONDecodeError, OSError) as exc:
        return 1, f"Sonarr queue API unreachable: {exc}"

    records = q.get("records") or []
    total = q.get("totalRecords", len(records))
    todo = records[:limit]
    print(f"completed queue items: {total} (processing first {len(todo)})")

    ok = removed = failed = 0
    for item in todo:
        qid, title = item["id"], str(item.get("title", "?"))[:55]
        if not apply:
            ok += 1
            print(f"[dry] {qid} {title}")
            continue
        good, note = import_one(base_url, api_key, item, timeout)
        if good:
            ok += 1
            print(f"[imported] {qid} {title} | {note}")
            continue
        try:
            remove_item(base_url, api_key, item, timeout)
            removed += 1
            print(f"[removed ] {qid} {title} | import failed ({note})")
        except Exception as exc:
            failed += 1
            print(f"[ERROR   ] {qid} {title} | {exc} | {note}")

    summary = f"summary: imported={ok} removed={removed} errors={failed}"
    if not apply:
        summary = "dry-run (no --apply): " + summary
    return 0, summary


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("SONARR_URL", DEFAULT_URL),
                    help="Sonarr base URL (default: %(default)s)")
    ap.add_argument("--api-key", default=os.environ.get("SONARR_API_KEY", ""),
                    help="API key (default: $SONARR_API_KEY)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="max queue items to process (default: %(default)s)")
    ap.add_argument("--status", default="completed",
                    help="queue status filter (default: %(default)s)")
    ap.add_argument("--apply", action="store_true",
                    help="actually import/remove; default is a dry run")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="HTTP timeout seconds (default: %(default)s)")
    args = ap.parse_args()

    if not args.api_key:
        print("SONARR_API_KEY not set (pass --api-key or export SONARR_API_KEY)",
              file=sys.stderr)
        return 1

    code, summary = drain(args.url, args.api_key, args.limit, args.status,
                          args.apply, args.timeout)
    print(summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
