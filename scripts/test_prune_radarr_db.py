#!/usr/bin/env python3
"""Regression test for scripts/prune_radarr_db.py.

Verifies the maintenance path cannot silently bit-rot:

  * a bloated DB (big MovieFiles.MediaInfo blobs + old History rows) is
    detected, backed up, pruned to 0 blobs, history-trimmed, re-VACUUMed,
    and left integrity-clean and under the high-water mark
  * logs.db Logs rows are trimmed to the newest N
  * a healthy DB is a no-op (media already 0, DB untouched, integrity kept)
  * backups land in a timestamped Backups/ dir next to the DB

Runs against the importable module logic (plus throwaway SQLite DBs), so it
works on the CI runner. Run by validate.yml and nightly-healthcheck.yml, and
locally via `python3 scripts/test_prune_radarr_db.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# import check_radarr_db_size under its real name first — prune_radarr_db
# imports it, and exec_module must populate sys.modules for that to resolve.
spec_check = importlib.util.spec_from_file_location(
    "check_radarr_db_size", SCRIPTS / "check_radarr_db_size.py")
checker = importlib.util.module_from_spec(spec_check)
sys.modules["check_radarr_db_size"] = checker
spec_check.loader.exec_module(checker)

spec_prune = importlib.util.spec_from_file_location(
    "prune_radarr_db", SCRIPTS / "prune_radarr_db.py")
prune = importlib.util.module_from_spec(spec_prune)
spec_prune.loader.exec_module(prune)

MiB = 1024 * 1024


def make_bloated_db(dirpath: Path) -> Path:
    """Throwaway radarr-schema DB: 250 MiB of MediaInfo blobs + one old and
    one recent History row, with a page footprint under the 900 MiB high-water
    mark (so only the MediaInfo gate can legitimately trip)."""
    db = dirpath / "radarr.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE MovieFiles (Id INTEGER PRIMARY KEY, MediaInfo TEXT)")
    con.execute("INSERT INTO MovieFiles (Id, MediaInfo) VALUES (1, ?)",
                ("x" * 250 * MiB,))
    con.execute("CREATE TABLE History (Id INTEGER PRIMARY KEY, Date TEXT)")
    con.execute("INSERT INTO History (Id, Date) VALUES (1, '2026-01-01T00:00:00Z')")
    con.execute("INSERT INTO History (Id, Date) VALUES (2, '2026-09-01T00:00:00Z')")
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

        before = checker.read_metrics(db)
        problems = checker.assess(before["page_size"], before["footprint_bytes"],
                                  before["media_bytes"], 900 * MiB, 200 * MiB)
        expect("bloated DB is flagged before prune", len(problems) == 1, True)

        # Backup lands in a timestamped dir next to the DB and holds both DBs.
        dest = prune.backup_files(db, logs, db.parent / "Backups")
        expect("backup dir created", dest.is_dir(), True)
        expect("backup contains radarr.db", (dest / db.name).is_file(), True)
        expect("backup contains logs.db", (dest / logs.name).is_file(), True)

        # Integrity gate passes before the writes.
        expect("integrity ok before prune", prune.integrity_ok(db), True)

        prune.prune_radarr(db, logs, keep_history_days=90, keep_log_rows=5)

        after = checker.read_metrics(db)
        expect("MediaInfo blobs pruned to 0", after["media_bytes"], 0)
        remaining = checker.assess(after["page_size"], after["footprint_bytes"],
                                   after["media_bytes"], 900 * MiB, 200 * MiB)
        expect("no bloat after prune", remaining, [])
        expect("integrity ok after prune", prune.integrity_ok(db), True)

        con = sqlite3.connect(db)
        rows = con.execute("SELECT Date FROM History ORDER BY Date").fetchall()
        con.close()
        expect("old history trimmed, recent kept",
               rows, [("2026-09-01T00:00:00Z",)])

        lcon = sqlite3.connect(logs)
        log_rows = lcon.execute("SELECT COUNT(*) FROM Logs").fetchone()[0]
        lcon.close()
        expect("logs.db trimmed to newest 5", log_rows, 5)

        # A healthy DB (media already 0) is a safe no-op, not an error.
        healthy = root / "healthy.db"
        hcon = sqlite3.connect(healthy)
        hcon.execute("CREATE TABLE MovieFiles (Id INTEGER PRIMARY KEY, MediaInfo TEXT)")
        hcon.commit()
        hcon.close()
        prune.prune_radarr(healthy, None)
        hpost = checker.read_metrics(healthy)
        expect("healthy DB media stays 0", hpost["media_bytes"], 0)
        expect("healthy DB integrity ok", prune.integrity_ok(healthy), True)

    if failures == 0:
        print("test_prune_radarr_db: all assertions passed")
        return 0
    print(f"test_prune_radarr_db: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
