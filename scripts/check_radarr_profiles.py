#!/usr/bin/env python3
"""Guard against Radarr orphaned quality-profile references (AGENTS.md landmine #8).

A movie row pointing at a deleted quality profile makes `/api/v3/movie` return
500 for the whole collection — the "The given key '17' was not present in the
dictionary" failure. The API itself 500s once broken, so it can't enumerate the
offender; check the SQLite DB directly, read-only, for movies whose
QualityProfileId is not present in QualityProfiles.

Read-only and safe to run while Radarr is live. Exit codes:
  0  every movie references an existing quality profile
  1  one or more movies reference a deleted (or NULL) quality profile
  2  the Radarr DB could not be located or read (operational; treat as skip)

Usage:
  python3 scripts/check_radarr_profiles.py
  python3 scripts/check_radarr_profiles.py --db /path/to/radarr.db
  RADARR_DB=/path/to/radarr.db python3 scripts/check_radarr_profiles.py
"""

import argparse
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "config" / "radarr" / "radarr.db"

_SELECT_DANGLING = """
SELECT m.Id, m.Path, m.QualityProfileId, mm.TmdbId, mm.Title
FROM Movies m
JOIN MovieMetadata mm ON mm.Id = m.MovieMetadataId
LEFT JOIN QualityProfiles q ON q.Id = m.QualityProfileId
WHERE q.Id IS NULL
ORDER BY m.Id
"""


def find_dangling(db_path) -> list:
    """Return [(id, path, profile_id, tmdb, title)] for movies referencing a
    missing or NULL quality profile. Opens read-only against the live DB,
    falling back to immutable (main-file snapshot, WAL ignored) if the live
    connection can't be established (e.g. locked -shm)."""
    uri = f"file:{urllib.parse.quote(str(db_path))}?mode="
    con = None
    last_exc = None
    for mode in ("ro", "immutable"):
        try:
            con = sqlite3.connect(uri + mode, uri=True, timeout=15)
            break
        except (sqlite3.Error, OSError) as exc:
            con = None
            last_exc = exc
    if con is None:
        raise last_exc
    try:
        return con.execute(_SELECT_DANGLING).fetchall()
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("RADARR_DB", str(DEFAULT_DB)))
    args = ap.parse_args()
    path = Path(args.db)
    if not path.is_file():
        print(f"radarr DB not found at {path}; skipping (set RADARR_DB or --db)")
        return 2
    try:
        dangling = find_dangling(path)
    except sqlite3.Error as exc:
        print(f"CHECK FAILED: could not read radarr DB {path}: {exc}")
        return 2
    if dangling:
        for mid, mpath, prof, tmdb, title in dangling:
            print(f"  DANGLING: movie {mid} '{title}' (tmdb {tmdb}) -> missing quality profile {prof}")
        print()
        print(f"CHECK FAILED: {len(dangling)} movie(s) reference a deleted quality profile")
        print("  Fix: assign each to an existing profile via Radarr's movie editor,")
        print("  or see /api/v3/qualityprofile for valid profile ids.")
        return 1
    print("OK: every movie references an existing quality profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
