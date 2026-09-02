#!/usr/bin/env python3
"""Regression test for scripts/drain_sonarr_queue.py.

Verifies the pure import-file building logic cannot silently bit-rot:

  * empty preview -> ([], "empty preview")
  * a resolvable sonarr candidate builds a ManualImport file entry
    carrying seriesId/episodeIds/quality/languages and the downloadId
  * a radarr candidate builds the same shape with movieId/movieIds
  * a candidate missing its parent or children is an all-or-nothing
    failure (falls back to queue removal instead of a partial import)
  * the per-app default API base carries the /api/v3 prefix and the
    queue endpoint joins onto it (regression: paths used to hit the bare
    origin, which returns the HTML front page and never parses as JSON —
    the drain tool could not reach the API at all)

Runs against importable pure-Python logic (no live Sonarr/Radarr
needed), so it works on the CI runner. Run by .github/workflows/validate.yml
and locally via `python3 scripts/test_drain_sonarr_queue.py`. Exits 0
when every assertion holds, 1 otherwise.
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


def sonarr_candidate():
    return {
        "path": "/data/shows/Show/Season 1/Show S01E01.mkv",
        "series": {"id": 7},
        "episodes": [{"id": 101}, {"id": 102}],
        "quality": {"quality": {"name": "HDTV-720p"}},
        "languages": [{"id": 1, "name": "English"}],
    }


def radarr_candidate():
    return {
        "path": "/data/movies/Movie (2020)/Movie (2020) Bluray-1080p.mkv",
        "movie": {"id": 42},
        "quality": {"quality": {"name": "Bluray-1080p"}},
        "languages": [{"id": 1, "name": "English"}],
    }


def main():
    # Empty preview.
    files, err = mod.build_import_files("sonarr", [], "dl-1")
    check("empty preview reports error", files == [] and err == "empty preview")

    # A fully-resolved sonarr candidate.
    preview = [sonarr_candidate()]
    files, err = mod.build_import_files("sonarr", preview, "dl-2")
    check("resolvable sonarr candidate builds one file entry",
          err is None and len(files) == 1)
    if files:
        entry = files[0]
        check("sonarr entry carries seriesId/episodeIds/downloadId",
              entry["seriesId"] == 7
              and entry["episodeIds"] == [101, 102]
              and entry["downloadId"] == "dl-2")
        check("sonarr entry preserves path/quality/languages",
              entry["path"].endswith("S01E01.mkv")
              and entry["quality"] == preview[0]["quality"]
              and entry["languages"] == preview[0]["languages"])

    # A fully-resolved radarr candidate (movieId/movieIds, no episodeIds).
    preview = [radarr_candidate()]
    files, err = mod.build_import_files("radarr", preview, "dl-5")
    check("resolvable radarr candidate builds one file entry",
          err is None and len(files) == 1)
    if files:
        entry = files[0]
        check("radarr entry carries movieId/movieIds and no episode fields",
              entry["movieId"] == 42
              and entry["movieIds"] == [42]
              and "seriesId" not in entry
              and "episodeIds" not in entry
              and entry["downloadId"] == "dl-5")

    # One unresolved candidate fails the whole import (all-or-nothing).
    bad = [sonarr_candidate(), {"path": "/x/y.mkv", "series": {}, "episodes": []}]
    files, err = mod.build_import_files("sonarr", bad, "dl-3")
    check("unresolved sonarr candidate fails the whole import",
          files == [] and err and "unresolved" in err)

    # Missing children alone is also all-or-nothing.
    no_eps = [{"path": "/x/y.mkv", "series": {"id": 3}, "episodes": []}]
    files, err = mod.build_import_files("sonarr", no_eps, "dl-4")
    check("missing episodes fails the whole import", files == [] and err)

    # Radarr without a movie is all-or-nothing too.
    no_movie = [{"path": "/x/y.mkv", "movie": {}}]
    files, err = mod.build_import_files("radarr", no_movie, "dl-6")
    check("radarr without a movie fails the whole import", files == [] and err)

    # --- URL construction regression (missing /api/v3 prefix) ---
    check("sonarr default base carries the /api/v3 prefix",
          mod.DEFAULT_URLS["sonarr"].endswith("/api/v3"))
    check("radarr default base carries the /api/v3 prefix",
          mod.DEFAULT_URLS["radarr"].endswith("/api/v3"))

    # Stub _request and remove_item so drain() captures the queue URL.
    captured = {}

    def fake_request(base_url, api_key, path, method="GET", body=None,
                     timeout=None):
        captured["url"] = f"{base_url}{path}"
        return {"records": [], "totalRecords": 0}

    orig_request = mod._request
    orig_remove = mod.remove_item
    mod._request = fake_request
    mod.remove_item = lambda *a, **k: None
    try:
        for app, base in (("sonarr", "http://localhost:8989/api/v3"),
                          ("radarr", "http://localhost:7878/api/v3")):
            captured.clear()
            code, _ = mod.drain(app, base, "k", 5, "completed", apply=False)
            check(f"{app} queue URL targets its /api/v3 base",
                  code == 0 and captured.get("url") ==
                  f"{base}/queue?page=1&pageSize=200&status=completed")
            check(f"{app} queue URL never targets the bare origin",
                  ".8989/queue?" not in captured.get("url", "")
                  and ".7878/queue?" not in captured.get("url", ""))
    finally:
        mod._request = orig_request
        mod.remove_item = orig_remove

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
