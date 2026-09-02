#!/usr/bin/env python3
"""Regression test for scripts/check_arr_import_queue.py.

Verifies the stuck-queue classification cannot silently bit-rot:

  * a clean queue (no completed/warning/blocked items) -> exit 0
  * items held from import (importBlocked / importPending warnings,
    matching the 2026-09-02 230-item pile-up) count as stuck
  * an active download or an item without a warning is NOT stuck
  * stuck count over threshold -> exit 1 (the drain prompt)
  * an unreachable/malformed API -> exit 2 (soft WARN, never a silent
    pass)

Runs against importable pure-Python logic (no live Sonarr/Radarr
needed), so it works on the CI runner. Run by .github/workflows/validate.yml
and locally via `python3 scripts/test_check_arr_import_queue.py`. Exits 0
when every assertion holds, 1 otherwise.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_arr_import_queue.py"

spec = importlib.util.spec_from_file_location("check_arr_import_queue",
                                              CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def rec(**kw):
    """One queue record; defaults to a stuck-shaped completed item."""
    base = {"id": 1, "title": "Some.Show.S01E01.1080p.WEB-DL",
            "status": "completed", "trackedDownloadStatus": "warning",
            "trackedDownloadState": "importBlocked", "downloadId": "dl-1"}
    base.update(kw)
    return base


def queue(records):
    return {"page": 1, "pageSize": 200, "totalRecords": len(records),
            "records": records}


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name} — expected {want!r}, got {got!r}")
            failures += 1

    # --- stuck_items classification --------------------------------------
    empty = queue([])
    expect("empty queue -> no stuck", mod.stuck_items(empty), [])

    blocked = rec(trackedDownloadState="importBlocked")
    pending = rec(trackedDownloadState="importPending",
                  trackedDownloadStatus="warning")
    expect("importBlocked warning counts as stuck",
           len(mod.stuck_items(queue([blocked]))), 1)
    expect("importPending warning counts as stuck",
           len(mod.stuck_items(queue([pending]))), 1)
    expect("230-item pile-up counts all 230",
           len(mod.stuck_items(queue([blocked] * 219 + [pending] * 11))), 230)

    active = rec(status="downloading", trackedDownloadState="downloading",
                 trackedDownloadStatus="ok")
    no_warning = rec(trackedDownloadStatus="ok")
    expect("active download is not stuck",
           mod.stuck_items(queue([active])), [])
    expect("completed without warning is not stuck",
           mod.stuck_items(queue([no_warning])), [])
    expect("mixed queue counts only the stuck",
           len(mod.stuck_items(queue([active, blocked, no_warning]))), 1)

    # --- check() decision logic ------------------------------------------
    real_fetch = mod.fetch_queue

    def fake(data):
        return lambda *a, **kw: data

    def fake_raise(*a, **kw):
        raise OSError("connection refused")

    def fake_garbage(*a, **kw):
        return {"bogus": "no records key"}

    try:
        mod.fetch_queue = fake(queue([blocked] * 230))
        code, msg = mod.check("u", "k", 30, 10)
        expect("230 stuck > threshold 10 -> exit 1", code, 1)
        expect("fail message names the drain",
               "drain_sonarr_queue" in msg, True)

        mod.fetch_queue = fake(queue([blocked] * 3))
        code, msg = mod.check("u", "k", 30, 10)
        expect("3 stuck <= threshold 10 -> exit 0", code, 0)
        expect("under-threshold message carries count",
               "3 stuck" in msg, True)

        mod.fetch_queue = fake(queue([]))
        code, _ = mod.check("u", "k", 30, 10)
        expect("clean queue -> exit 0", code, 0)

        mod.fetch_queue = fake_raise
        code, msg = mod.check("u", "k", 30, 10)
        expect("unreachable API -> exit 2", code, 2)
        expect("unreachable message is descriptive",
               "unreachable" in msg, True)

        mod.fetch_queue = fake_garbage
        code, msg = mod.check("u", "k", 30, 10)
        expect("malformed response -> exit 2", code, 2)
        expect("malformed message is descriptive",
               "could not parse" in msg, True)
    finally:
        mod.fetch_queue = real_fetch

    # threshold boundary: exactly threshold is OK, threshold+1 fails
    try:
        mod.fetch_queue = fake(queue([blocked] * 10))
        expect("10 stuck at threshold 10 -> exit 0",
               mod.check("u", "k", 30, 10)[0], 0)
        mod.fetch_queue = fake(queue([blocked] * 11))
        expect("11 stuck vs threshold 10 -> exit 1",
               mod.check("u", "k", 30, 10)[0], 1)
    finally:
        mod.fetch_queue = real_fetch

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
