#!/usr/bin/env python3
"""Regression test for scripts/prune_sonarr_db.py.

Verifies the Sonarr maintenance path (the EpisodeFiles analogue of
scripts/prune_radarr_db.py plus event-JSON slimming) cannot silently
bit-rot:

  * a bloated DB (big EpisodeFiles.MediaInfo blobs + History rows with Data
    JSON + DownloadHistory rows with Data/Release JSON) is detected, backed
    up, pruned, and left integrity-clean and under the high-water mark
  * History rows older than --keep-history-days are deleted; rows inside the
    window survive
  * JSON payloads (History.Data, DownloadHistory.Data, DownloadHistory.
    Release) older than --keep-data-days are NULLed while their rows are
    KEPT (DownloadId correlation must survive); recent payloads stay intact
  * tables/columns absent from the schema are skipped (no crash on a
    minimal or future-schema DB)
  * logs.db Logs rows are trimmed to the newest N; backups land in a
    timestamped Backups/ dir next to the DB; a healthy DB is a no-op

Runs against the importable module logic (plus throwaway SQLite DBs), so it
works on the CI runner. Fixture dates are computed relative to *now* so the
assertions never rot. Run by validate.yml and nightly-healthcheck.yml, and
locally via `python3 scripts/test_prune_sonarr_db.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import datetime as _dt
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# import check_radarr_db_size under its real name first — prune_sonarr_db
# imports it, and exec_module must populate sys.modules for that to resolve.
spec_check = importlib.util.spec_from_file_location(
    "check_radarr_db_size", SCRIPTS / "check_radarr_db_size.py")
checker = importlib.util.module_from_spec(spec_check)
sys.modules["check_radarr_db_size"] = checker
spec_check.loader.exec_module(checker)

spec_prune = importlib.util.spec_from_file_location(
    "prune_sonarr_db", SCRIPTS / "prune_sonarr_db.py")
prune = importlib.util.module_from_spec(spec_prune)
spec_prune.loader.exec_module(prune)

MiB = 1024 * 1024
NOW = _dt.datetime.now()


def ISO(days_ago: int) -> str:
    """SQLite-comparable timestamp for *days_ago* days before now."""
    return (NOW - _dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


OLD = ISO(100)    # > keep_history_days (90): row deleted
MID = ISO(40)     # > keep_data_days (14), < keep_history_days: payload NULLed
RECENT = ISO(1)   # inside both windows: fully intact


def make_bloated_db(dirpath: Path) -> Path:
    """Throwaway sonarr-schema DB: 250 MiB MediaInfo blobs, History rows with
    Data JSON at three ages, DownloadHistory rows with Data + Release JSON at
    two ages, and a page footprint under the 900 MiB high-water mark used by
    the fixture assertions (only the MediaInfo gate can legitimately trip)."""
    db = dirpath / "sonarr.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE EpisodeFiles (Id INTEGER PRIMARY KEY, MediaInfo TEXT)")
    con.execute("INSERT INTO EpisodeFiles (Id, MediaInfo) VALUES (1, ?)",
                ("x" * 250 * MiB,))
    # History.Data mirrors Sonarr's real schema (NOT NULL) — a blind NULL
    # write must raise/skip, not corrupt; the slim uses '' here.
    con.execute("CREATE TABLE History (Id INTEGER PRIMARY KEY, Date TEXT, "
                "Data TEXT NOT NULL)")
    for i, (age, payload) in enumerate(((100, "old-json-" + "x" * 1000),
                                        (40, "mid-json-" + "x" * 1000),
                                        (1, "recent-json-" + "x" * 1000))):
        con.execute("INSERT INTO History (Id, Date, Data) VALUES (?, ?, ?)",
                    (i + 1, ISO(age), payload))
    con.execute("CREATE TABLE DownloadHistory (Id INTEGER PRIMARY KEY, DownloadId TEXT, "
                "Date TEXT, Data TEXT, Release TEXT)")
    for i, (age, payload) in enumerate(((40, "dlh-mid-json-" + "x" * 1000),
                                        (1, "dlh-recent-json-" + "x" * 1000))):
        con.execute("INSERT INTO DownloadHistory (Id, DownloadId, Date, Data, Release) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (i + 1, f"dlid-{i}", ISO(age), payload, "release-" + payload))
    con.commit()
    con.close()
    return db


def make_logs_db(dirpath: Path) -> Path:
    logs = dirpath / "logs.db"
    con = sqlite3.connect(logs)
    con.execute("CREATE TABLE Logs (Id INTEGER PRIMARY KEY)")
    for i in range(1, 11):
        con.execute("INSERT INTO Logs (Id) VALUES (?)", (i,))
    con.commit()
    con.close()
    return logs


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name} expected {want!r}, got {got!r}")
            failures += 1

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = make_bloated_db(root)
        logs = make_logs_db(root)

        before = checker.read_metrics(db, prune.BLOB_TABLE)
        problems = checker.assess(before["page_size"], before["footprint_bytes"],
                                  before["media_bytes"], 900 * MiB, 200 * MiB,
                                  "sonarr.db", prune.BLOB_TABLE)
        expect("bloated DB is flagged before prune", len(problems) == 1, True)

        probe = sqlite3.connect(db)
        hist_nn = [r for r in probe.execute("PRAGMA table_info(History)")
                   if r[1] == "Data"][0][3]
        expect("fixture pins History.Data NOT NULL (real schema)", hist_nn, 1)
        expect("slim value for History.Data is '' (NOT NULL)",
               prune.slim_value_for(probe, "History", "Data"), "''")
        expect("slim value for DownloadHistory.Release is NULL",
               prune.slim_value_for(probe, "DownloadHistory", "Release"), "NULL")
        probe.close()

        # Backup lands in a timestamped dir next to the DB and holds both DBs.
        dest = prune.backup_files(db, logs, db.parent / "Backups")
        expect("backup dir created", dest.is_dir(), True)
        expect("backup contains sonarr.db", (dest / db.name).is_file(), True)
        expect("backup contains logs.db", (dest / logs.name).is_file(), True)

        # Integrity gate passes before the writes.
        expect("integrity ok before prune", prune.integrity_ok(db), True)

        prune.prune_sonarr(db, logs, keep_history_days=90, keep_log_rows=5,
                           keep_data_days=14)

        after = checker.read_metrics(db, prune.BLOB_TABLE)
        expect("MediaInfo blobs pruned to 0", after["media_bytes"], 0)
        remaining = checker.assess(after["page_size"], after["footprint_bytes"],
                                   after["media_bytes"], 900 * MiB, 200 * MiB,
                                   "sonarr.db", prune.BLOB_TABLE)
        expect("no bloat after prune", remaining, [])
        expect("integrity ok after prune", prune.integrity_ok(db), True)

        con = sqlite3.connect(db)
        h_rows = con.execute("SELECT Date, Data FROM History ORDER BY Date").fetchall()
        expect("old history row deleted, mid + recent kept",
               [r[0] for r in h_rows], [MID, RECENT])
        expect("mid History.Data slimmed to '' (NOT NULL column, row kept)",
               h_rows[0][1], "")
        expect("recent History.Data intact",
               h_rows[1][1].startswith("recent-json-"), True)

        d_rows = con.execute("SELECT Date, Data, Release FROM DownloadHistory "
                             "ORDER BY Date").fetchall()
        expect("DownloadHistory rows kept (correlation survives)",
               len(d_rows), 2)
        expect("mid DownloadHistory.Data NULLed", d_rows[0][1], None)
        expect("mid DownloadHistory.Release NULLed", d_rows[0][2], None)
        expect("recent DownloadHistory.Data intact",
               d_rows[1][1].startswith("dlh-recent-json-"), True)
        expect("recent DownloadHistory.Release intact",
               d_rows[1][2].startswith("release-dlh-recent-json-"), True)
        con.close()

        lcon = sqlite3.connect(logs)
        log_rows = lcon.execute("SELECT COUNT(*) FROM Logs").fetchone()[0]
        lcon.close()
        expect("logs.db trimmed to newest 5", log_rows, 5)

        # A healthy DB (media already 0, no old JSON) is a safe no-op.
        healthy = root / "healthy.db"
        hcon = sqlite3.connect(healthy)
        hcon.execute("CREATE TABLE EpisodeFiles (Id INTEGER PRIMARY KEY, MediaInfo TEXT)")
        hcon.commit()
        hcon.close()
        prune.prune_sonarr(healthy, None)
        hpost = checker.read_metrics(healthy, prune.BLOB_TABLE)
        expect("healthy DB media stays 0", hpost["media_bytes"], 0)
        expect("healthy DB integrity ok", prune.integrity_ok(healthy), True)

        # count_slimmable sees only payloads past the keep-data-days cutoff.
        con = sqlite3.connect(db)
        expect("no slimmable JSON remains after prune",
               prune.count_slimmable(con, 14), 0)
        con.close()

    if failures == 0:
        print("test_prune_sonarr_db: all assertions passed")
        return 0
    print(f"test_prune_sonarr_db: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
