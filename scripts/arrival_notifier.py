#!/usr/bin/env python3
"""Request → arrival notifier (TODO.md #7).

The minimal useful slice of retired watchstate: when a Seerr request's
media actually lands on the stack — the *arr app imported the download —
refresh Plex and send ONE Discord ping per request. No container, no
listener, no state beyond a small JSON file under .cache/; run from a user
timer (every 15 minutes is plenty). Cursor-style state means a missed run or
a down service never loses or duplicates a ping.

Detection is *arr-history-first, Seerr-verdict-second*:

  1. Open requests (PENDING/APPROVED) and unnotified COMPLETED requests are
     resolved to *arr items: movies via the request's tmdbId (Radarr), shows
     via tvdbId (Sonarr).
  2. The *arr History API is asked for the newest import
     (eventType=downloadFolderImported) for that item. An import newer than
     the request itself is the ground truth that the download landed.
  3. When history cannot confirm (the request was for something already on
     Plex, or Seerr synced completion without a history record), an
     APPROVED or COMPLETED request whose media status is AVAILABLE is
     treated as arrived too.
  4. DECLINED/FAILED requests are dropped from the watch set without a ping
     (a retried request is watched fresh, so it still notifies if it later
     arrives).

Delivery rules:

  * One ping per request, ever — successful deliveries are recorded in the
    state file; a failed webhook POST is NOT recorded, so the next run
    retries.
  * Plex section refresh happens only when a ping is actually attempted
    (--no-refresh skips it; refresh failure never blocks the ping).
  * DISCORD_WEBHOOK_URL unset → feature disabled: the run exits 0 and
    reports, but nothing is marked notified, so setting the webhook later
    delivers any pending arrivals.

Seerr status ladder (verified against seerr-team/seerr
server/constants/media.ts, 2026-09-03):
  request: 1 PENDING, 2 APPROVED, 3 DECLINED, 4 FAILED, 5 COMPLETED
  media:   1 UNKNOWN, 2 PENDING, 3 PROCESSING, 4 PARTIALLY_AVAILABLE,
           5 AVAILABLE, 6 BLOCKLISTED, 7 DELETED

Exit codes:
  0  ran cleanly (nothing pending, or every arrival delivered/disabled)
  1  arrival(s) detected but the Discord webhook POST failed
  2  cannot assess — Seerr/*arr APIs unreachable (retry next run)

Usage:
  python3 scripts/arrival_notifier.py
  python3 scripts/arrival_notifier.py --dry-run --no-refresh
  python3 scripts/arrival_notifier.py --json
  python3 scripts/arrival_notifier.py --state-file /tmp/arrivals.json

Install as a user timer (every 15 minutes) so the digest's timer check sees
it healthy:

  # ~/.config/systemd/user/stack-arrival-notify.service
  [Unit]
  Description=Bear Cave request->arrival notifier
  [Service]
  Type=oneshot
  EnvironmentFile=/home/bear/TheBearCave/.env
  ExecStart=/usr/bin/python3 /home/bear/TheBearCave/scripts/arrival_notifier.py

  # ~/.config/systemd/user/stack-arrival-notify.timer
  [Unit]
  Description=Bear Cave arrival notifier (every 15 min)
  [Timer]
  OnCalendar=*:0/15
  Persistent=true
  [Install]
  WantedBy=timers.target

  systemctl --user daemon-reload
  systemctl --user enable --now stack-arrival-notify.timer
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / ".cache" / "arrivals" / "state.json"

API_TIMEOUT = 10  # seconds, matching STACK_API_TIMEOUT_LIGHT

# Seerr request statuses (server/constants/media.ts, verified 2026-09-03).
PENDING, APPROVED, DECLINED, FAILED, COMPLETED = 1, 2, 3, 4, 5
WATCH_STATUSES = {PENDING, APPROVED, COMPLETED}
# Media status AVAILABLE == 5 (Seerr enum).
MEDIA_AVAILABLE = 5

URLS = {
    "seerr": ("SEERR_URL", "http://localhost:5055"),
    "radarr": ("RADARR_URL", "http://localhost:7878"),
    "sonarr": ("SONARR_URL", "http://localhost:8989"),
    "plex": ("PLEX_URL", "http://localhost:32400"),
}


# --- small helpers -----------------------------------------------------------


def parse_iso(ts):
    """ISO-8601 timestamp (with or without Z) -> epoch seconds, or None."""
    if not ts:
        return None
    try:
        s = ts
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None


def env_url(key, fallback):
    """Resolve a service base URL from the environment (mirrors __helpers.sh)."""
    import os

    return os.environ.get(key) or fallback


# --- pure decision logic (unit-tested offline) --------------------------------


def normalize_requests(payload):
    """Seerr /request response -> list of normalized request dicts.

    Each dict: id, status, type, tmdb_id, tvdb_id, title, who, created_epoch,
    media_status. Records that cannot be resolved to an *arr item (no tmdbId
    for a movie, no tvdbId for a show) carry ``resolvable=False`` and are
    skipped by classify_run.
    """
    out = []
    for r in (payload or {}).get("results") or []:
        media = r.get("media") or {}
        requester = r.get("requestedBy") or {}
        kind = r.get("type")
        created = parse_iso(r.get("createdAt"))
        out.append(
            {
                "id": r.get("id"),
                "status": r.get("status"),
                "type": kind,
                "tmdb_id": media.get("tmdbId"),
                "tvdb_id": media.get("tvdbId"),
                "title": media.get("title"),
                "who": requester.get("plexUsername") or requester.get("displayName")
                or "unknown",
                "created_epoch": created,
                "media_status": media.get("status"),
                "resolvable": bool(
                    media.get("tmdbId") if kind == "movie" else media.get("tvdbId")
                ),
            }
        )
    return out


def arrival_kind(request, history, media_available):
    """Classify one request against its *arr history + Seerr media state.

    history: list of {"ts": epoch, "season": int|None, "episode": int|None}
    (newest import records for the item). Returns ("import", newest_record),
    ("available", None), or None when the item has not arrived yet.
    """
    if not request.get("resolvable"):
        return None
    created = request.get("created_epoch")
    newer = [h for h in history if h["ts"] is not None and (created is None or h["ts"] > created)]
    if newer:
        newest = max(newer, key=lambda h: h["ts"])
        return ("import", newest)
    if request.get("status") in (APPROVED, COMPLETED) and media_available:
        return ("available", None)
    return None


def build_message(kind, request, record):
    """Discord content for one arrival. Record is the newest history dict."""
    title = request.get("title") or "Unknown title"
    who = request.get("who")
    if kind == "import" and request.get("type") == "tv" and record:
        se = ""
        if record.get("season") is not None and record.get("episode") is not None:
            se = " S%02dE%02d" % (record["season"], record["episode"])
        return "📺 %s%s has arrived on Plex — requested by %s" % (title, se, who)
    if kind == "import":
        return "🎬 %s is now on Plex — requested by %s" % (title, who)
    return "🎬 %s was already available — requested by %s" % (title, who)


def classify_run(state, requests, history_lookup, media_available_lookup):
    """Split the watch set into arrivals vs drops vs still-pending.

    state: {"requests": {request_id: {"notified_ts": ...}}} — already-notified
    ids are skipped. history_lookup(request) -> list of history dicts;
    media_available_lookup(request) -> bool. Returns (arrivals, drops):
    arrivals = [(request, kind, record)], drops = [request].
    """
    notified = set((state.get("requests") or {}).keys())
    arrivals = []
    drops = []
    for req in requests:
        rid = req.get("id")
        if not req.get("resolvable") or rid is None or str(rid) in notified:
            continue
        if req.get("status") in (DECLINED, FAILED):
            drops.append(req)
            continue
        if req.get("status") not in WATCH_STATUSES:
            continue
        result = arrival_kind(req, history_lookup(req), media_available_lookup(req))
        if result:
            kind, record = result
            arrivals.append((req, kind, record))
    return arrivals, drops


def load_state(path):
    path = Path(path)
    if path.is_file():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


# --- HTTP transport (thin; the bash surface uses curl, python uses urllib) ----


def http_json(url, headers=None, timeout=API_TIMEOUT):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_json(base, path, headers, timeout=API_TIMEOUT):
    """GET one JSON resource; raises on non-2xx/unreachable."""
    sep = "" if base.endswith("/") else "/"
    url = base + sep + path.lstrip("/")
    return http_json(url, headers=headers, timeout=timeout)


def seerr_requests(base, key):
    """Paginate GET /api/v1/request?take=100&skip=N until exhausted."""
    out = []
    skip = 0
    take = 100
    headers = {"X-Api-Key": key}
    while True:
        data = fetch_json(base, "api/v1/request?take=%d&skip=%d" % (take, skip), headers)
        batch = (data or {}).get("results") or []
        out.extend(batch)
        if len(batch) < take:
            return out
        skip += take


def history_imports(base, key, app, item_id):
    """Newest *arr import history for an item -> list of {"ts", "season", "episode"}.

    Radarr: GET /api/v3/history?movieId=..&eventType=downloadFolderImported&pageSize=1
    Sonarr: GET /api/v3/history?seriesId=..&eventType=downloadFolderImported&pageSize=1
    """
    params = "pageSize=1&sortKey=date&sortDirection=desc&eventType=downloadFolderImported"
    if app == "radarr":
        params += "&movieId=%s" % item_id
    else:
        params += "&seriesId=%s" % item_id
    data = fetch_json(base, "api/v3/history?%s" % params, {"X-Api-Key": key})
    records = (data or {}).get("records") or []
    out = []
    for rec in records:
        episode = rec.get("episode") or {}
        out.append(
            {
                "ts": parse_iso(rec.get("date")),
                "season": episode.get("seasonNumber"),
                "episode": episode.get("episodeNumber"),
            }
        )
    return out


def plex_section_refresh(base, token, wanted_type):
    """POST /library/sections/{key}/refresh for the first section of the
    wanted type (movie/show). Returns True on success, False when skipped or
    failed (never fatal — the ping goes out regardless)."""
    if not token:
        return False
    try:
        data = fetch_json(
            base + "/library/sections?X-Plex-Token=" + token,
            "",
            {"Accept": "application/json"},
        )
    except Exception:
        return False
    for sec in (data.get("MediaContainer") or {}).get("Directory") or []:
        if sec.get("type") == wanted_type:
            try:
                fetch_json(
                    base
                    + "/library/sections/%s/refresh?X-Plex-Token=%s"
                    % (sec.get("key"), token),
                    "",
                    headers={},
                    timeout=5,
                )
                return True
            except Exception:
                return False
    return False


def discord_post(webhook, content, timeout=API_TIMEOUT):
    """POST one Discord message; raises on any failure."""
    body = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout):
        return True


# --- orchestration -------------------------------------------------------------


def run(args):
    import os

    state = load_state(Path(args.state_file))
    seerr_base = env_url(*URLS["seerr"])
    seerr_key = os.environ.get("SEERR_API_KEY", "")
    radarr_base = env_url(*URLS["radarr"])
    radarr_key = os.environ.get("RADARR_API_KEY", "")
    sonarr_base = env_url(*URLS["sonarr"])
    sonarr_key = os.environ.get("SONARR_API_KEY", "")
    plex_base = env_url(*URLS["plex"])
    plex_token = os.environ.get("PLEX_TOKEN", "")
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")

    if not seerr_key or not radarr_key or not sonarr_key:
        print(
            "Cannot assess: SEERR_API_KEY / RADARR_API_KEY / SONARR_API_KEY must be set",
            file=sys.stderr,
        )
        return 2

    # --- fetch the request list ------------------------------------------------
    try:
        requests = normalize_requests(seerr_requests(seerr_base, seerr_key))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(
            "Cannot assess: Seerr unreachable at %s (%s)" % (seerr_base, exc),
            file=sys.stderr,
        )
        return 2

    # --- resolve each watch-set request against the *arr history ---------------

    def history_lookup(req):
        try:
            if req.get("type") == "movie":
                movies = fetch_json(
                    radarr_base, "api/v3/movie?tmdbId=%s" % req.get("tmdb_id"),
                    {"X-Api-Key": radarr_key},
                )
                movie_ids = [m.get("id") for m in (movies or []) if m.get("id")]
                if not movie_ids:
                    return []
                return history_imports(radarr_base, radarr_key, "radarr", movie_ids[0])
            series = fetch_json(
                sonarr_base, "api/v3/series?tvdbId=%s" % req.get("tvdb_id"),
                {"X-Api-Key": sonarr_key},
            )
            series_ids = [s.get("id") for s in (series or []) if s.get("id")]
            if not series_ids:
                return []
            return history_imports(sonarr_base, sonarr_key, "sonarr", series_ids[0])
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return []

    def media_available_lookup(req):
        return req.get("media_status") == MEDIA_AVAILABLE

    arrivals, drops = classify_run(
        state, requests, history_lookup, media_available_lookup
    )
    notified = set((state.get("requests") or {}).keys())
    watch_set = [
        r
        for r in requests
        if r.get("resolvable")
        and r.get("id") is not None
        and str(r.get("id")) not in notified
        and r.get("status") in WATCH_STATUSES
    ]
    pending_count = len(watch_set) - len(arrivals)

    # --- dry run: pure preview, no side effects ---------------------------------
    if args.dry_run:
        for req, kind, record in arrivals:
            print(build_message(kind, req, record))
        print(
            "dry run: %d arrival(s), %d still watched, %d closed dropped"
            % (len(arrivals), pending_count, len(drops))
        )
        return 0

    # --- webhook unset: feature disabled ----------------------------------------
    if not webhook:
        if arrivals:
            print(
                "DISCORD_WEBHOOK_URL not set — %d arrival(s) pending delivery "
                "(nothing marked notified)" % len(arrivals)
            )
        requests_map = state.setdefault("requests", {})
        for req in drops:
            requests_map.pop(str(req.get("id")), None)
        save_state(Path(args.state_file), state)
        return 0

    # --- deliver -----------------------------------------------------------------
    delivered, failed = [], []
    for req, kind, record in arrivals:
        if not args.no_refresh:
            plex_section_refresh(
                plex_base, plex_token, "movie" if req.get("type") == "movie" else "show"
            )
        try:
            discord_post(webhook, build_message(kind, req, record))
            delivered.append((req, kind, record))
        except (urllib.error.URLError, OSError) as exc:
            failed.append((req, kind, exc))

    # --- persist state ------------------------------------------------------------
    requests_map = state.setdefault("requests", {})
    for req, kind, _record in delivered:
        requests_map[str(req.get("id"))] = {"notified_ts": int(time.time()), "kind": kind}
    for req in drops:
        requests_map.pop(str(req.get("id")), None)
    save_state(Path(args.state_file), state)

    # --- report -------------------------------------------------------------------
    pending = pending_count - len(delivered) - len(failed)
    if args.json:
        report = {
            "watched": pending_count,
            "arrivals": [
                {"id": r["id"], "kind": k, "title": r.get("title"), "who": r.get("who")}
                for r, k, _rec in delivered
            ],
            "failed": [
                {"id": r["id"], "title": r.get("title"), "error": str(exc)}
                for r, _, exc in failed
            ],
            "pending": pending,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for req, kind, record in delivered:
            print(build_message(kind, req, record))
        for req, kind, exc in failed:
            print(
                "FAILED to notify: %s (%s)" % (req.get("title") or req.get("id"), exc),
                file=sys.stderr,
            )
        if not delivered and not failed:
            print("No arrivals pending (%d still watched)." % pending)
        elif drops:
            print("%d closed request(s) dropped from the watch set." % len(drops))

    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="detect only; no refresh, no ping, no state change")
    parser.add_argument("--no-refresh", action="store_true", help="skip the Plex section refresh on arrival")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE), help="state file path (default: .cache/arrivals/state.json)")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())