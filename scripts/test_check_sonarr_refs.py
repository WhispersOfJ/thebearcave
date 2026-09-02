#!/usr/bin/env python3
"""Regression test for scripts/check_sonarr_refs.py.

Verified cases (throwaway SQLite DB, no live Sonarr):
  * clean DB - valid profile + under-root series -> no orphans in either category
  * a Series referencing a deleted quality profile IS flagged
  * a Series with a NULL quality profile IS flagged
  * a Series whose Path is not under any configured root folder IS flagged
  * a Series inside a valid root folder is NOT flagged

Run by validate.yml and nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_sonarr_refs.py`. Exits 0 on success, 1 otherwise.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_sonarr_refs.py"

spec = importlib.util.spec_from_file_location("check_sonarr_refs", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_db(profiles, roots, series) -> str:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    f.close()
    con = sqlite3.connect(f.name)
    con.execute("CREATE TABLE QualityProfiles (Id INTEGER PRIMARY KEY, Name TEXT)")
    con.execute("CREATE TABLE RootFolders (Id INTEGER PRIMARY KEY, Path TEXT)")
    con.execute("CREATE TABLE Series (Id INTEGER PRIMARY KEY, Title TEXT, "
                "QualityProfileId INTEGER, Path TEXT)")
    for pid, name in profiles:
        con.execute("INSERT INTO QualityProfiles (Id, Name) VALUES (?, ?)", (pid, name))
    for rid, path in roots:
        con.execute("INSERT INTO RootFolders (Id, Path) VALUES (?, ?)", (rid, path))
    for sid, title, prof, path in series:
        con.execute("INSERT INTO Series (Id, Title, QualityProfileId, Path) "
                    "VALUES (?, ?, ?, ?)", (sid, title, prof, path))
    con.commit()
    con.close()
    return f.name


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name} expected {want!r}, got {got!r}")
            failures += 1

    clean = make_db(
        [(1, "HD")],
        [(1, "/data/shows")],
        [(10, "Breaking Bad", 1, "/data/shows/Breaking Bad"),  # under root
         (11, "Better Call Saul", 1, "/data/shows/Better Call Saul")],
    )
    expect("clean DB: no profile orphans", mod.find_quality_profile_orphans(clean), [])
    expect("clean DB: no root orphans", mod.find_root_folder_orphans(clean), [])

    dangling = make_db(
        [(1, "HD")],
        [(1, "/data/shows")],
        [(10, "Breaking Bad", 1, "/data/shows/Breaking Bad"),
         (11, "Old Show", 2, "/data/shows/Old Show")],  # profile 2 deleted
    )
    expect("deleted quality profile IS flagged",
           mod.find_quality_profile_orphans(dangling), [(11, "Old Show", 2)])

    nullprof = make_db(
        [(1, "HD")],
        [(1, "/data/shows")],
        [(10, "Ghost", None, "/data/shows/Ghost")],
    )
    rows = mod.find_quality_profile_orphans(nullprof)
    expect("NULL quality profile IS flagged", len(rows) == 1 and rows[0][2] is None, True)

    rootdangling = make_db(
        [(1, "HD")],
        [(1, "/data/shows")],
        [(10, "Good", 1, "/data/shows/Good"),
         (11, "Old", 1, "/data/retired/Old"),        # under a deleted root
         (12, "Sneaky", 1, "/data/shows2/not-a-root")],  # sibling prefix trap
    )
    expect("series under deleted root IS flagged", mod.find_root_folder_orphans(rootdangling),
           [(11, "Old", "/data/retired/Old"), (12, "Sneaky", "/data/shows2/not-a-root")])

    for p in (clean, dangling, nullprof, rootdangling):
        os.unlink(p)

    if failures == 0:
        print("test_check_sonarr_refs: all assertions passed")
        return 0
    print(f"test_check_sonarr_refs: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
