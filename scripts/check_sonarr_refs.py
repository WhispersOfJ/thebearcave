#!/usr/bin/env python3
"""Guard against Sonarr orphan references (the *arr-family sibling of AGENTS.md
landmine #8, confirmed observed on Radarr).

Sonarr shares the *arr SQLite architecture with Radarr: a Series row pointing at
a deleted quality profile can break the API just like Radarr's movie/profile
orphan did on 2026-08-31. Check the SQLite DB directly, read-only, for:

  * quality-profile orphans  - Series.QualityProfileId missing or NULL in
    QualityProfiles.
  * root-folder orphans      - Series.Path not equal to or under any configured
    RootFolders.Path (a deleted root folder that Series still point into).

Read-only and safe to run while Sonarr is live. Exit codes:
  0  every Series references an existing quality profile and root folder
  1  one or more orphan references found
  2  the Sonarr DB could not be located or read (operational; treat as skip)

Usage:
  python3 scripts/check_sonarr_refs.py
  python3 scripts/check_sonarr_refs.py --db /path/to/sonarr.db
  SONARR_DB=/path/to/sonarr.db python3 scripts/check_sonarr_refs.py
"""

import argparse
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "config" / "sonarr" / "sonarr.db"

_PROFILE_SELECT = """
SELECT s.Id, s.Title, s.QualityProfileId
FROM Series s
LEFT JOIN QualityProfiles q ON q.Id = s.QualityProfileId
WHERE q.Id IS NULL
ORDER BY s.Id
"""

_ROOT_SELECT = """
SELECT s.Id, s.Title, s.Path
FROM Series s
WHERE NOT EXISTS (
    SELECT 1 FROM RootFolders r
    WHERE s.Path = r.Path OR s.Path LIKE r.Path || '/%'
)
ORDER BY s.Id
"""


def _connect(db_path):
    uri = f"file:{urllib.parse.quote(str(db_path))}?mode="
    last = None
    for mode in ("ro", "immutable"):
        try:
            return sqlite3.connect(uri + mode, uri=True, timeout=15)
        except (sqlite3.Error, OSError) as exc:
            last = exc
    raise last


def find_quality_profile_orphans(db_path) -> list:
    """Return [(id, title, profile_id)] for Series with a missing/NULL profile."""
    con = _connect(db_path)
    try:
        return con.execute(_PROFILE_SELECT).fetchall()
    finally:
        con.close()


def find_root_folder_orphans(db_path) -> list:
    """Return [(id, title, path)] for Series whose Path is not under a root."""
    con = _connect(db_path)
    try:
        return con.execute(_ROOT_SELECT).fetchall()
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("SONARR_DB", str(DEFAULT_DB)))
    args = ap.parse_args()
    path = Path(args.db)
    if not path.is_file():
        print(f"sonarr DB not found at {path}; skipping (set SONARR_DB or --db)")
        return 2
    try:
        profiles = find_quality_profile_orphans(path)
        roots = find_root_folder_orphans(path)
    except (sqlite3.Error, OSError) as exc:
        print(f"CHECK FAILED: could not read sonarr DB {path}: {exc}")
        return 2

    problems = 0
    if profiles:
        print(f"QUALITY PROFILE ORPHANS ({len(profiles)}):")
        for sid, title, prof in profiles:
            print(f"  series {sid} '{title}' -> missing quality profile {prof}")
        problems += 1
    if roots:
        print(f"ROOT FOLDER ORPHANS ({len(roots)}):")
        for sid, title, spath in roots:
            print(f"  series {sid} '{title}' path '{spath}' not under any root folder")
        problems += 1

    if problems:
        print(f"CHECK FAILED: {problems} orphan category/categories; fix in Sonarr "
              "(reassign quality profile / move under an existing root folder).")
        return 1
    print("OK: every series references an existing quality profile and root folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())