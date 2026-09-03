#!/usr/bin/env python3
"""Regression test for scripts/arrival_notifier.py (TODO.md #7).

Verifies the request->arrival decision logic cannot silently bit-rot:

  * Seerr payload normalization: requester fallback, title fallback, and
    the unresolvable flag (movie without tmdbId / tv without tvdbId)
  * arrival_kind ladder: history-newer-than-request wins; APPROVED/COMPLETED
    + media AVAILABLE falls back to "available"; PENDING never pings on the
    media fallback alone; unresolvable requests never arrive
  * classify_run: already-notified ids are skipped, DECLINED/FAILED become
    drops, and a COMPLETED request that Seerr synced is still caught
  * build_message: movie vs TV (SxxEyy) vs already-available wording
  * state IO: round-trip, corrupt file degrades to {}, save creates parents
  * rc contract: missing API keys -> 2 without touching the network

Runs fully offline. Exits 0 when every assertion holds, 1 otherwise.
"""

import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "arrival_notifier.py"

UTC = timezone.utc
T_2026_09_01_NOON = datetime(2026, 9, 1, 12, 0, tzinfo=UTC).timestamp()
T_2026_09_01_MIDNIGHT = datetime(2026, 9, 1, 0, 0, tzinfo=UTC).timestamp()

spec = importlib.util.spec_from_file_location("arrival_notifier", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DAY = 86400.0


def expect(name, got, want):
    if got == want:
        print(f"OK: {name}")
        return True
    print(f"FAIL: {name} expected {want!r}, got {got!r}")
    return False


def mk_request(**over):
    base = {
        "id": 1,
        "status": mod.APPROVED,
        "type": "movie",
        "tmdb_id": 12345,
        "tvdb_id": None,
        "title": "The Test Flick",
        "who": "bear",
        "created_epoch": 1_800_000_000,
        "media_status": mod.MEDIA_AVAILABLE,
        "resolvable": True,
    }
    base.update(over)
    return base


def main() -> int:
    failures = 0

    # --- parse_iso ---------------------------------------------------------
    failures += not expect(
        "parse_iso Z-suffix", mod.parse_iso("2026-09-01T12:00:00.000Z"),
        T_2026_09_01_NOON,
    )
    failures += not expect(
        "parse_iso bare +00:00", mod.parse_iso("2026-09-01T12:00:00+00:00"),
        T_2026_09_01_NOON,
    )
    failures += not expect("parse_iso garbage", mod.parse_iso("nope"), None)
    failures += not expect("parse_iso empty", mod.parse_iso(""), None)

    # --- normalize_requests -------------------------------------------------
    payload = {
        "results": [
            {
                "id": 1,
                "status": 2,
                "type": "movie",
                "media": {"tmdbId": 10, "tvdbId": None, "title": "M1", "status": 3},
                "requestedBy": {"plexUsername": "alice"},
                "createdAt": "2026-09-01T00:00:00.000Z",
            },
            {
                "id": 2,
                "status": 2,
                "type": "tv",
                "media": {"tmdbId": 20, "tvdbId": 30, "title": None, "status": 5},
                "requestedBy": {"displayName": "bob"},
                "createdAt": "2026-09-02T00:00:00.000Z",
            },
            {
                "id": 3,
                "status": 1,
                "type": "movie",
                "media": {"tmdbId": None, "tvdbId": None, "title": "no ids"},
                "requestedBy": None,
                "createdAt": "2026-09-03T00:00:00.000Z",
            },
        ]
    }
    reqs = mod.normalize_requests(payload)
    failures += not expect("normalize count", len(reqs), 3)
    failures += not expect("normalize movie", reqs[0]["tmdb_id"], 10)
    failures += not expect("normalize plexUsername", reqs[0]["who"], "alice")
    failures += not expect("normalize tvdbId", reqs[1]["tvdb_id"], 30)
    failures += not expect("normalize displayName fallback", reqs[1]["who"], "bob")
    failures += not expect("normalize unresolvable", reqs[2]["resolvable"], False)
    failures += not expect("normalize missing requester", reqs[2]["who"], "unknown")
    failures += not expect(
        "normalize created epoch", reqs[0]["created_epoch"], T_2026_09_01_MIDNIGHT
    )
    failures += not expect("normalize empty payload", mod.normalize_requests(None), [])

    # --- arrival_kind --------------------------------------------------------
    req = mk_request(created_epoch=1_800_000_000)
    history_new = [{"ts": 1_800_010_000, "season": None, "episode": None}]
    history_old = [{"ts": 1_799_000_000, "season": None, "episode": None}]
    kind, rec = mod.arrival_kind(req, history_new, True)
    failures += not expect("history-newer wins", (kind, rec), ("import", history_new[0]))
    failures += not expect(
        "history-older alone is not arrival", mod.arrival_kind(req, history_old, False), None
    )
    failures += not expect(
        "approved + media available fallback",
        mod.arrival_kind(req, history_old, True),
        ("available", None),
    )
    pending = mk_request(status=mod.PENDING, created_epoch=1_800_000_000)
    failures += not expect(
        "pending never pings on media fallback",
        mod.arrival_kind(pending, history_old, True),
        None,
    )
    completed = mk_request(status=mod.COMPLETED, created_epoch=1_800_000_000)
    failures += not expect(
        "completed + media available caught",
        mod.arrival_kind(completed, history_old, True),
        ("available", None),
    )
    failures += not expect(
        "unresolvable never arrives",
        mod.arrival_kind(mk_request(resolvable=False), history_new, True),
        None,
    )

    # --- build_message --------------------------------------------------------
    tv_req = mk_request(type="tv", title="Show")
    tv_rec = {"ts": 1, "season": 3, "episode": 7}
    failures += not expect(
        "tv message carries SxxEyy",
        mod.build_message("import", tv_req, tv_rec),
        "📺 Show S03E07 has arrived on Plex — requested by bear",
    )
    failures += not expect(
        "movie import message",
        mod.build_message("import", mk_request(title="Flick"), None),
        "🎬 Flick is now on Plex — requested by bear",
    )
    failures += not expect(
        "already-available message",
        mod.build_message("available", mk_request(title="Oldie"), None),
        "🎬 Oldie was already available — requested by bear",
    )
    failures += not expect(
        "null title fallback",
        mod.build_message("import", mk_request(title=None), None),
        "🎬 Unknown title is now on Plex — requested by bear",
    )

    # --- classify_run ---------------------------------------------------------
    def hist_for(ts_list):
        return [{"ts": t, "season": None, "episode": None} for t in ts_list]

    notified_state = {"requests": {"1": {"notified_ts": 1, "kind": "import"}}}
    reqs = [
        mk_request(id=1, status=mod.APPROVED),                    # already notified
        mk_request(id=2, status=mod.DECLINED),                    # drop
        mk_request(id=3, status=mod.FAILED),                      # drop
        mk_request(id=4, status=mod.APPROVED, media_status=3),    # pending
        mk_request(id=5, status=mod.APPROVED, media_status=5),    # media fallback
        mk_request(id=6, status=mod.APPROVED, created_epoch=1_800_000_000,
                   media_status=3),                               # history import
    ]
    hist_map = {4: [], 5: [], 6: hist_for([1_800_010_000])}

    def hist_lookup(r):
        return hist_map.get(r["id"], [])

    def media_available(r):
        return r["media_status"] == mod.MEDIA_AVAILABLE

    arrivals, drops = mod.classify_run(notified_state, reqs, hist_lookup, media_available)
    failures += not expect("notified skipped", [a[0]["id"] for a in arrivals], [5, 6])
    failures += not expect("declined/failed dropped", [d["id"] for d in drops], [2, 3])

    # --- state IO ---------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "deep" / "state.json"
        state = {"requests": {"7": {"notified_ts": 1, "kind": "import"}}}
        mod.save_state(state_path, state)
        failures += not expect("state round-trip", mod.load_state(state_path), state)
        (Path(tmp) / "bad.json").write_text("{torn")
        failures += not expect("corrupt state degrades", mod.load_state(Path(tmp) / "bad.json"), {})
        failures += not expect("missing state", mod.load_state(Path(tmp) / "absent.json"), {})

    # --- rc contract: missing keys -> 2, no network ----------------------------
    with tempfile.TemporaryDirectory() as tmp:
        old_env = {k: os.environ.get(k) for k in ("SEERR_API_KEY", "RADARR_API_KEY",
                                                  "SONARR_API_KEY")}
        for k in old_env:
            os.environ.pop(k, None)
        try:
            rc = mod.run(
                type("A", (), {"state_file": str(Path(tmp) / "s.json"),
                               "dry_run": True, "no_refresh": False, "json": False})()
            )
        finally:
            for k, v in old_env.items():
                if v is not None:
                    os.environ[k] = v
        failures += not expect("missing keys -> rc 2", rc, 2)

    print()
    if failures == 0:
        print("All arrival-notifier tests passed.")
        return 0
    print(f"{failures} arrival-notifier test(s) failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
