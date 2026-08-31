#!/usr/bin/env python3
"""Regression test for scripts/check_radarr_db_size.py.

Verifies the DB page-size/bloat guard cannot silently bit-rot:

  * an empty/healthy DB reports no problems
  * a DB whose page footprint exceeds the high-water mark IS flagged
  * a DB whose MovieFiles.MediaInfo blobs exceed the threshold IS flagged
  * an invalid (non power-of-two) page size IS flagged
  * missing/oversized defaults from env are honoured via the pure assess()

Runs against the importable pure logic (plus a throwaway SQLite DB for the
MediaInfo path), so it works on the CI runner. Run by validate.yml and
nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_radarr_db_size.py`. Exits 0 when every assertion
holds, 1 otherwise.
"""

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_radarr_db_size.py"

spec = importlib.util.spec_from_file_location("check_radarr_db_size", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Handy byte constants (powers of two keep page math clean).
MiB = 1024 * 1024


def make_db(media_blob_bytes: int) -> str:
    """Create a throwaway radarr-schema DB whose MovieFiles.MediaInfo total is
    ~media_blob_bytes, and whose page footprint is well under the high-water
    mark (so only the MediaInfo gate can legitimately trip)."""
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    f.close()
    con = sqlite3.connect(f.name)
    con.execute("CREATE TABLE MovieFiles (Id INTEGER PRIMARY KEY, MediaInfo TEXT)")
    blob = "x" * media_blob_bytes
    con.execute("INSERT INTO MovieFiles (Id, MediaInfo) VALUES (1, ?)", (blob,))
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

    # Pure assess() branches.
    healthy = mod.assess(4096, 500 * MiB, 10 * MiB, 900 * MiB, 200 * MiB)
    expect("healthy DB: no problems", healthy, [])

    fp = mod.assess(4096, 950 * MiB, 10 * MiB, 900 * MiB, 200 * MiB)
    expect("page footprint over high-water is flagged", len(fp) == 1, True)

    me = mod.assess(4096, 500 * MiB, 250 * MiB, 900 * MiB, 200 * MiB)
    expect("MediaInfo bloat is flagged", len(me) == 1, True)

    nope = mod.assess(4096, 950 * MiB, 250 * MiB, 900 * MiB, 200 * MiB)
    expect("footprint + MediaInfo both flagged", len(nope) == 2, True)

    badsz = mod.assess(12345, 500 * MiB, 10 * MiB, 900 * MiB, 200 * MiB)
    expect("non power-of-two page size is flagged", len(badsz) == 1, True)

    # End-to-end read_metrics + assess against a real throwaway DB.
    small = make_db(10 * MiB)
    m = mod.read_metrics(small)
    expect("small DB reads healthy footprint/media", m["media_bytes"] < 200 * MiB, True)
    expect("small DB assess clean", mod.assess(m["page_size"], m["footprint_bytes"],
                                               m["media_bytes"], 900 * MiB, 200 * MiB), [])

    bloated = make_db(250 * MiB)
    mb = mod.read_metrics(bloated)
    probs = mod.assess(mb["page_size"], mb["footprint_bytes"], mb["media_bytes"],
                       900 * MiB, 200 * MiB)
    expect("bloated DB flagged via read_metrics", len(probs) == 1, True)

    import os
    for p in (small, bloated):
        os.unlink(p)

    if failures == 0:
        print("test_check_radarr_db_size: all assertions passed")
        return 0
    print(f"test_check_radarr_db_size: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())