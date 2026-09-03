#!/usr/bin/env python3
"""Regression test for scripts/activity_feed.py (TODO.md #8).

Verifies the feed poller cannot silently bit-rot:

  * record normalization for Radarr (movie object) and Sonarr (series +
    episode objects), with sourceTitle fallback
  * event mapping: imports/upgrades/deletions, grabs skipped
  * upgrade detection: a second import for the same item is "upgrade" only
    while its key is still on record; a delete clears the key
  * cursor math: id > last_id, deduped; first-run backfill window
  * renderers: text labels + SxxEyy, JSON shape, RSS 2.0 with escaped
    titles and stable guids
  * end-to-end run(): a canned local HTTP server drives the poll; assert
    the JSONL/feed.json/feed.xml/state artifacts and that a second run
    only picks up records newer than the cursor (and flags the upgrade)

Runs fully offline. Exits 0 when every assertion holds, 1 otherwise.
"""

import http.server
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "activity_feed.py"

spec = importlib.util.spec_from_file_location("activity_feed", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def expect(name, got, want):
    if got == want:
        print(f"OK: {name}")
        return True
    print(f"FAIL: {name} expected {want!r}, got {got!r}")
    return False


def iso_now_ago(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))


def main() -> int:
    failures = 0
    now = int(time.time())

    # --- normalize_record -----------------------------------------------------
    radarr_rec = {
        "id": 11,
        "movieId": 5,
        "date": iso_now_ago(3600),
        "eventType": "downloadFolderImported",
        "sourceTitle": "The Movie 2026 1080p",
        "quality": {"quality": {"name": "Bluray-1080p"}},
        "data": {"releaseGroup": "GRP"},
        "movie": {"id": 5, "title": "The Movie", "year": 2026},
    }
    n = mod.normalize_record("radarr", radarr_rec)
    failures += not expect("radarr title", n["title"], "The Movie")
    failures += not expect("radarr year", n["year"], 2026)
    failures += not expect("radarr quality", n["quality"], "Bluray-1080p")
    failures += not expect("radarr source", n["source"], "GRP")

    sonarr_rec = {
        "id": 22,
        "seriesId": 9,
        "episodeId": 77,
        "date": iso_now_ago(1800),
        "eventType": "downloadFolderImported",
        "sourceTitle": "Show - S02E04",
        "quality": {"quality": {"name": "WEB-1080p"}},
        "data": {},
        "series": {"id": 9, "title": "Show", "year": 2024},
        "episode": {"id": 77, "seasonNumber": 2, "episodeNumber": 4},
    }
    s = mod.normalize_record("sonarr", sonarr_rec)
    failures += not expect("sonarr title", s["title"], "Show")
    failures += not expect("sonarr season", s["season"], 2)
    failures += not expect("sonarr episode", s["episode"], 4)
    failures += not expect("sonarr no source", s["source"], None)

    fallback = mod.normalize_record("radarr", {"id": 1, "date": iso_now_ago(10),
                                               "eventType": "x", "sourceTitle": "Fallback 2020",
                                               "data": {}, "movie": None})
    failures += not expect("sourceTitle fallback", fallback["title"], "Fallback 2020")

    # --- item_key + kind_for (normalized records) --------------------------------
    n_rad = mod.normalize_record("radarr", radarr_rec)
    n_son = mod.normalize_record("sonarr", sonarr_rec)
    failures += not expect("radarr item key", mod.item_key("radarr", n_rad), "radarr:5")
    failures += not expect("sonarr item key", mod.item_key("sonarr", n_son), "sonarr:77")

    last_import = {}
    kind, upd = mod.kind_for("radarr", n_rad, last_import)
    failures += not expect("first import kind", kind, "import")
    failures += not expect("first import updates state", upd, {"radarr:5": 11})
    last_import.update(upd)
    kind2, _ = mod.kind_for("radarr", n_rad, last_import)
    failures += not expect("second import is upgrade", kind2, "upgrade")

    del_rec = {"id": 12, "movieId": 5, "date": iso_now_ago(100),
               "eventType": "movieFileDeleted", "sourceTitle": "The Movie",
               "quality": None, "data": {}, "movie": {"id": 5, "title": "The Movie"}}
    n_del = mod.normalize_record("radarr", del_rec)
    kind3, upd3 = mod.kind_for("radarr", n_del, last_import)
    failures += not expect("delete kind", kind3, "delete")
    failures += not expect("delete clears key", upd3, {"radarr:5": None})

    grab_rec = {"id": 13, "date": iso_now_ago(50), "eventType": "movieGrabbed",
                "sourceTitle": "Grab", "data": {}, "movie": {"id": 6}}
    n_grab = mod.normalize_record("radarr", grab_rec)
    failures += not expect("grab skipped", mod.kind_for("radarr", n_grab, {}), (None, {}))

    # --- new_records + backfill -------------------------------------------------
    recs = [
        {"id": 12, "ts": now - 1000},
        {"id": 11, "ts": now - 2000},
        {"id": 10, "ts": now - 3000},
    ]
    failures += not expect(
        "cursor keeps newer only",
        [r["id"] for r in mod.new_records("radarr", {"radarr": {"last_id": 11}}, recs)],
        [12],
    )
    failures += not expect(
        "no cursor returns all",
        [r["id"] for r in mod.new_records("radarr", {}, recs)],
        [12, 11, 10],
    )
    cutoff = mod.backfill_cutoff(recs, now)
    failures += not expect(
        "backfill window keeps inside 24h", [r["id"] for r in cutoff], [12, 11, 10]
    )
    failures += not expect(
        "backfill window drops old",
        [r["id"] for r in mod.backfill_cutoff([{"id": 1, "ts": now - 200000}], now)],
        [],
    )

    # --- renderers ---------------------------------------------------------------
    entry = mod.build_entry("radarr", mod.normalize_record("radarr", radarr_rec), "import")
    text = mod.render_text([entry], 5)
    failures += not expect("text has import label", len(text), 1)
    failures += not ("imported" in text[0] and "The Movie (2026)" in text[0])
    rj = json.loads(mod.render_json([entry], 5))
    failures += not expect("json shape", (rj["entries"][0]["kind"], rj["entries"][0]["app"]),
                           ("import", "radarr"))
    rss = mod.render_rss([entry], 5)
    failures += not ("<?xml" in rss and "<rss version=\"2.0\">" in rss and "<item>" in rss)
    failures += "Imported: The Movie (2026)" not in rss
    failures += "thebearcave-radarr-11" not in rss
    evil = mod.build_entry("sonarr", mod.normalize_record("sonarr", sonarr_rec), "import")
    evil["title"] = "Show <b>&"
    evil_rss = mod.render_rss([evil], 5)
    failures += not expect("rss escapes title", "Show &lt;b&gt;&amp;" in evil_rss, True)

    # --- state IO -----------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.json"
        mod.save_state(p, {"radarr": {"last_id": 9}})
        failures += not expect("state round-trip", mod.load_state(p), {"radarr": {"last_id": 9}})
        (Path(tmp) / "bad.json").write_text("{broken")
        failures += not expect("corrupt state degrades", mod.load_state(Path(tmp) / "bad.json"), {})

    # --- end-to-end run() against a canned local server ---------------------------
    class Handler(http.server.BaseHTTPRequestHandler):
        records = None

        def do_GET(self):
            if self.path.startswith("/api/v3/history"):
                # Sonarr answers with an empty history; Radarr serves the
                # canned records (the two apps share this server, so the
                # X-Api-Key header tells them apart).
                if self.headers.get("X-Api-Key") == "kr":
                    body = json.dumps({"records": self.records}).encode()
                else:
                    body = b'{"records": []}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    def mk_records():
        return [
            {"id": 12, "movieId": 5, "date": iso_now_ago(3600),
             "eventType": "downloadFolderImported", "sourceTitle": "The Movie 1080p",
             "quality": {"quality": {"name": "Bluray-1080p"}}, "data": {"releaseGroup": "GRP"},
             "movie": {"id": 5, "title": "The Movie", "year": 2026}},
            {"id": 11, "movieId": 5, "date": iso_now_ago(7200),
             "eventType": "movieFileDeleted", "sourceTitle": "The Movie",
             "quality": None, "data": {},
             "movie": {"id": 5, "title": "The Movie", "year": 2026}},
            {"id": 10, "movieId": 5, "date": iso_now_ago(10800),
             "eventType": "downloadFolderImported", "sourceTitle": "The Movie 1080p",
             "quality": {"quality": {"name": "WEB-1080p"}}, "data": {},
             "movie": {"id": 5, "title": "The Movie", "year": 2026}},
            {"id": 9, "movieId": 8, "date": iso_now_ago(100000),
             "eventType": "downloadFolderImported", "sourceTitle": "Old",
             "quality": None, "data": {}, "movie": {"id": 8, "title": "Old"}},
            {"id": 8, "movieId": 7, "date": iso_now_ago(500),
             "eventType": "movieGrabbed", "sourceTitle": "Grab",
             "quality": None, "data": {}, "movie": {"id": 7, "title": "Grabby"}},
        ]

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            Handler.records = mk_records()
            state_file = str(Path(tmp) / "state.json")
            feed_file = str(Path(tmp) / "feed.jsonl")
            json_file = str(Path(tmp) / "feed.json")
            rss_file = str(Path(tmp) / "feed.xml")
            old_env = {
                k: os.environ.get(k)
                for k in ("RADARR_API_KEY", "SONARR_API_KEY", "RADARR_URL", "SONARR_URL")
            }
            os.environ["RADARR_API_KEY"] = "kr"
            os.environ["SONARR_API_KEY"] = "ks"
            os.environ["RADARR_URL"] = "http://127.0.0.1:%d" % port
            os.environ["SONARR_URL"] = "http://127.0.0.1:%d" % port
            try:
                rc = mod.run(type("A", (), {
                    "state_file": state_file, "feed_file": feed_file,
                    "json_file": json_file, "rss_file": rss_file,
                    "print_limit": None, "json_out": False})())
            finally:
                for k, v in old_env.items():
                    if v is not None:
                        os.environ[k] = v
                    else:
                        os.environ.pop(k, None)
            failures += not expect("run rc", rc, 0)
            lines = Path(feed_file).read_text().splitlines()
            kinds = [json.loads(ln)["kind"] for ln in lines]
            # desc order: 12 import, 11 delete, 10 import; grab skipped;
            # id 9 outside the 24h backfill window; sonarr served nothing.
            failures += not expect("run kinds", kinds, ["import", "delete", "import"])
            failures += not expect(
                "run cursor", mod.load_state(Path(state_file))["radarr"]["last_id"], 12
            )
            fj = json.loads(Path(json_file).read_text())
            failures += not expect("feed.json rendered", len(fj["entries"]), 3)
            failures += "The Movie (2026)" not in Path(rss_file).read_text()

            # Second run: only records newer than the cursor; the new import
            # for movie 5 is an upgrade (run 1's import re-set the key after
            # the delete cleared it).
            Handler.records = mk_records() + [
                {"id": 13, "movieId": 5, "date": iso_now_ago(100),
                 "eventType": "downloadFolderImported", "sourceTitle": "The Movie 2160p",
                 "quality": {"quality": {"name": "Remux-2160p"}}, "data": {},
                 "movie": {"id": 5, "title": "The Movie", "year": 2026}}
            ]
            os.environ["RADARR_API_KEY"] = "kr"
            os.environ["SONARR_API_KEY"] = "ks"
            os.environ["RADARR_URL"] = "http://127.0.0.1:%d" % port
            os.environ["SONARR_URL"] = "http://127.0.0.1:%d" % port
            try:
                rc2 = mod.run(type("A", (), {
                    "state_file": state_file, "feed_file": feed_file,
                    "json_file": json_file, "rss_file": rss_file,
                    "print_limit": None, "json_out": False})())
            finally:
                for k, v in old_env.items():
                    if v is not None:
                        os.environ[k] = v
                    else:
                        os.environ.pop(k, None)
            failures += not expect("second run rc", rc2, 0)
            lines2 = Path(feed_file).read_text().splitlines()
            last_kinds = [json.loads(ln)["kind"] for ln in lines2]
            failures += not expect("second run only new", len(last_kinds), 4)
            failures += not expect("second run kind (upgrade)", last_kinds[-1], "upgrade")
    finally:
        server.shutdown()

    # --- rc contract: no keys -> 2, no network -----------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        old = {k: os.environ.get(k) for k in ("RADARR_API_KEY", "SONARR_API_KEY")}
        for k in old:
            os.environ.pop(k, None)
        try:
            rc = mod.run(type("A", (), {
                "state_file": str(Path(tmp) / "s.json"), "feed_file": str(Path(tmp) / "f.jsonl"),
                "json_file": str(Path(tmp) / "j.json"), "rss_file": str(Path(tmp) / "r.xml"),
                "print_limit": None, "json_out": False})())
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v
        failures += not expect("no keys -> rc 2", rc, 2)

    print()
    if failures == 0:
        print("All activity-feed tests passed.")
        return 0
    print(f"{failures} activity-feed test(s) failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
