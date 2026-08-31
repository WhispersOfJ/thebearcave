#!/usr/bin/env python3
"""Regression test for scripts/drain_sonarr_queue.py.

Verifies the pure import-file building logic cannot silently bit-rot:

  * empty preview -> ([], "empty preview")
  * a resolvable candidate builds a ManualImport file entry carrying
    seriesId/episodeIds/quality/languages and the queue downloadId
  * a candidate missing series or episodes is an all-or-nothing failure
    (falls back to queue removal instead of a partial import)

Runs against importable pure-Python logic (no live Sonarr needed), so it
works on the CI runner. Run by .github/workflows/validate.yml and locally
via `python3 scripts/test_drain_sonarr_queue.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "drain_sonarr_queue.py"

# Import the tool as a module (it has no package-relative imports).
spec = importlib.util.spec_from_file_location("drain_sonarr_queue", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = 0


def check(label, cond):
    global failures
    if cond:
        print(f"  [PASS] {label}")
    else:
        failures += 1
        print(f"  [FAIL] {label}")


def main():
    # Empty preview.
    files, err = mod.build_import_files([], "dl-1")
    check("empty preview reports error", files == [] and err == "empty preview")

    # A fully-resolved candidate.
    preview = [{
        "path": "/data/shows/Show/Season 1/Show S01E01.mkv",
        "series": {"id": 7},
        "episodes": [{"id": 101}, {"id": 102}],
        "quality": {"quality": {"name": "HDTV-720p"}},
        "languages": [{"id": 1, "name": "English"}],
    }]
    files, err = mod.build_import_files(preview, "dl-2")
    check("resolvable candidate builds one file entry",
          err is None and len(files) == 1)
    if files:
        entry = files[0]
        check("entry carries seriesId/episodeIds/downloadId",
              entry["seriesId"] == 7
              and entry["episodeIds"] == [101, 102]
              and entry["downloadId"] == "dl-2")
        check("entry preserves path/quality/languages",
              entry["path"].endswith("S01E01.mkv")
              and entry["quality"] == preview[0]["quality"]
              and entry["languages"] == preview[0]["languages"])

    # One unresolved candidate fails the whole import (all-or-nothing).
    bad = [preview[0], {"path": "/x/y.mkv", "series": {}, "episodes": []}]
    files, err = mod.build_import_files(bad, "dl-3")
    check("unresolved candidate fails the whole import",
          files == [] and err and "unresolved" in err)

    # Missing episodes alone is also all-or-nothing.
    no_eps = [{"path": "/x/y.mkv", "series": {"id": 3}, "episodes": []}]
    files, err = mod.build_import_files(no_eps, "dl-4")
    check("missing episodes fails the whole import", files == [] and err)

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
