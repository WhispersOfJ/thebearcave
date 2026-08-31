#!/usr/bin/env python3
"""Guard against Radarr DB bloat (AGENTS.md landmine #9).

A long-lived radarr.db balloons (MediaInfo blobs, history) toward the process
memory cap and OOMs the container. The named failure we cleared in 2026-08-31
shipped a 1 GB radarr.db (322 MB sitting in MovieFiles.MediaInfo alone). This
check flags the DB on track to regrow into that failure, before it is silent:

  * page_size sanity  - the DB must be a sane SQLite page size (power of two in
    [512, 65536]). A nonsense value indicates a corrupted or manually-mishandled
    header.
  * page footprint    - page_count * page_size exceeds a high-water mark
    (default 900 MiB), i.e. heading toward the ~1 GB OOM cap for a 20k-movie
    library.
  * MediaInfo bloat   - the MovieFiles.MediaInfo column (the primary blob
    source) exceeds a threshold (default 200 MiB) and is prime suspect for the
    footprint growth.

Read-only and safe to run while Radarr is live. Exit codes:
  0  radarr.db is healthy
  1  bloat / invalid page size detected
  2  the Radarr DB could not be located or read (operational; treat as skip)

Usage:
  python3 scripts/check_radarr_db_size.py
  REDARR_DB=/path/to/radarr.db python3 scripts/check_radarr_db_size.py
  python3 scripts/check_radarr_db_size.py --max-footprint 900 --max-mediainfo 200
"""

import argparse
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "config" / "radarr" / "radarr.db"

DEFAULT_MAX_FOOTPRINT_MB = 900  # page footprint (page_count*page_size), MiB
DEFAULT_MAX_MEDIAINFO_MB = 200  # total MovieFiles.MediaInfo blob bytes, MiB


def is_power_of_two(n: int) -> bool:
    """True when n is a positive power of two (page sizes are power-of-two)."""
    return n >= 1 and (n & (n - 1)) == 0


def assess(page_size: int, footprint_bytes: int, media_info_bytes: int,
           max_footprint_bytes: int, max_media_bytes: int) -> list:
    """Return the list of detected problems (empty == healthy).

    Pure logic, no DB access, so it is trivially unit-testable on the CI runner.
    """
    problems = []
    if not (is_power_of_two(page_size) and 512 <= page_size <= 65536):
        problems.append(
            f"invalid SQLite page size {page_size!r} (expected a power of two in [512, 65536])")
    if footprint_bytes > max_footprint_bytes:
        problems.append(
            f"page footprint {_mb(footprint_bytes)} exceeds {_mb(max_footprint_bytes)} "
            "high-water mark (radarr.db on track to OOM the container)")
    if media_info_bytes > max_media_bytes:
        problems.append(
            f"MovieFiles.MediaInfo blobs total {_mb(media_info_bytes)} exceeds "
            f"{_mb(max_media_bytes)} (prime bloat suspect: prune via "
            "UPDATE MovieFiles SET MediaInfo = NULL; VACUUM)")
    return problems


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.0f} MiB"


def read_metrics(db_path) -> dict:
    """Read page_size / page_count / freelist_count / MediaInfo bytes read-only,
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
        page_size = con.execute("PRAGMA page_size").fetchone()[0]
        page_count = con.execute("PRAGMA page_count").fetchone()[0]
        freelist = con.execute("PRAGMA freelist_count").fetchone()[0]
        media = 0
        has_movies = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='MovieFiles'"
        ).fetchone()
        if has_movies:
            media = con.execute(
                "SELECT COALESCE(SUM(LENGTH(MediaInfo)), 0) FROM MovieFiles"
            ).fetchone()[0]
        return {
            "page_size": page_size,
            "page_count": page_count,
            "freelist": freelist,
            "footprint_bytes": page_size * page_count,
            "media_bytes": media,
        }
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("RADARR_DB", str(DEFAULT_DB)))
    ap.add_argument("--max-footprint", type=float,
                    default=float(os.environ.get("RADARR_MAX_FOOTPRINT_MB", DEFAULT_MAX_FOOTPRINT_MB)))
    ap.add_argument("--max-mediainfo", type=float,
                    default=float(os.environ.get("RADARR_MAX_MEDIAINFO_MB", DEFAULT_MAX_MEDIAINFO_MB)))
    args = ap.parse_args()
    path = Path(args.db)
    if not path.is_file():
        print(f"radarr DB not found at {path}; skipping (set RADARR_DB or --db)")
        return 2
    try:
        m = read_metrics(path)
    except (sqlite3.Error, OSError) as exc:
        print(f"CHECK FAILED: could not read radarr DB {path}: {exc}")
        return 2

    max_fp = int(args.max_footprint * 1024 * 1024)
    max_me = int(args.max_mediainfo * 1024 * 1024)
    problems = assess(m["page_size"], m["footprint_bytes"], m["media_bytes"], max_fp, max_me)

    print(f"page_size={m['page_size']} page_count={m['page_count']} "
          f"freelist={m['freelist']} footprint={_mb(m['footprint_bytes'])} "
          f"mediainfo={_mb(m['media_bytes'])}")
    if not problems:
        print("OK: radarr.db page size and footprint within healthy limits.")
        return 0
    for p in problems:
        print(f"  BLOAT: {p}")
    print(f"CHECK FAILED: {len(problems)} radarr.db size problem(s); "
          "see AGENTS.md landmine #9 (prune blobs and VACUUM).")
    return 1


if __name__ == "__main__":
    sys.exit(main())