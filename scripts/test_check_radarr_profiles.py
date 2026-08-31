#!/usr/bin/env python3
"""Regression test for scripts/check_radarr_profiles.py.

Verifies the orphaned-quality-profile guard cannot silently bit-rot:

  * an empty DB reports no dangling references
  * a movie referencing an existing profile is not flagged
  * a movie referencing a deleted profile IS flagged (with the right row data)
  * a movie with a NULL profile IS flagged

Runs against the importable pure logic on a throwaway SQLite DB (no live
Radarr needed), so it works on the CI runner. Run by validate.yml and
nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_radarr_profiles.py`. Exits 0 when every assertion
holds, 1 otherwise.
"""

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_radarr_profiles.py"

spec = importlib.util.spec_from_file_location("check_radarr_profiles", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_db(seed) -> str:
    """Create a throwaway radarr-schema DB with the given seed rows."""
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    f.close()
    con = sqlite3.connect(f.name)
    con.execute("CREATE TABLE QualityProfiles (Id INTEGER PRIMARY KEY, Name TEXT)")
    con.execute("CREATE TABLE MovieMetadata (Id INTEGER PRIMARY KEY, Title TEXT, TmdbId INTEGER)")
    con.execute("CREATE TABLE Movies (Id INTEGER PRIMARY KEY, Path TEXT, QualityProfileId INTEGER, MovieMetadataId INTEGER)")
    for pid, name in seed.get("profiles", []):
        con.execute("INSERT INTO QualityProfiles (Id, Name) VALUES (?, ?)", (pid, name))
    for mid, title, tmdb in seed.get("metadata", []):
        con.execute("INSERT INTO MovieMetadata (Id, Title, TmdbId) VALUES (?, ?, ?)", (mid, title, tmdb))
    for mid, path, prof, meta in seed.get("movies", []):
        con.execute("INSERT INTO Movies (Id, Path, QualityProfileId, MovieMetadataId) VALUES (?, ?, ?, ?)",
                    (mid, path, prof, meta))
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

    clean = make_db({
        "profiles": [(16, "Anything")],
        "metadata": [(1, "Nichijou: My Ordinary Life Episode 0", 1547090)],
        "movies": [(60309, "/data/movies/A.mkv", 16, 1)],
    })
    expect("clean DB: no dangling refs", mod.find_dangling(clean), [])

    dan = make_db({
        "profiles": [(16, "Anything")],
        "metadata": [(1, "Nichijou: My Ordinary Life Episode 0", 1547090),
                     (2, "Some Movie", 999)],
        "movies": [(60309, "/data/movies/A.mkv", 16, 1),
                   (60310, "/data/movies/B.mkv", 17, 2)],  # 17 no longer exists
    })
    got = mod.find_dangling(dan)
    want = [(60310, "/data/movies/B.mkv", 17, 999, "Some Movie")]
    expect("dangling profile IS flagged with full row", got, want)

    nullprof = make_db({
        "profiles": [(16, "Anything")],
        "metadata": [(1, "Ghost", 1)],
        "movies": [(1, "/data/movies/ghost.mkv", None, 1)],  # NULL profile
    })
    rows = mod.find_dangling(nullprof)
    expect("NULL profile IS flagged", len(rows) == 1 and rows[0][2] is None, True)

    import os
    for p in (clean, dan, nullprof):
        os.unlink(p)

    if failures == 0:
        print("test_check_radarr_profiles: all assertions passed")
        return 0
    print(f"test_check_radarr_profiles: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
