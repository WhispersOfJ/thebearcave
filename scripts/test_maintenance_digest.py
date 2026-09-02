#!/usr/bin/env python3
"""Offline unit tests for scripts/maintenance_digest.py.

Exercises the pure decision logic (reclaim-log freshness, failed-unit
parsing, dotfiles-ahead semantics via a git-less fake) without systemd,
git remotes, or the live stack. The DB/queue delegations are tested at the
finding-classification level by faking run_script output.

Run:  python3 scripts/test_maintenance_digest.py
"""

import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maintenance_digest as md  # noqa: E402


def fake_reclaim_log(mtime: dt.datetime) -> Path:
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / ".stack-disk-reclaim.log"
    p.write_text("Total reclaimed space: 1.2 GB\n")
    os.utime(p, (mtime.timestamp(), mtime.timestamp()))
    return p


class TestReclaimLog(unittest.TestCase):
    def test_fresh_after_0400_passes(self):
        # log written 05:00 today; checked 09:00 today
        now = dt.datetime(2026, 9, 3, 9, 0)
        p = fake_reclaim_log(dt.datetime(2026, 9, 3, 5, 2))
        f = md.check_reclaim_log(p, now)
        self.assertEqual(f.level, "ok", f.render())

    def test_before_todays_0400_is_stale(self):
        # log written yesterday 04:30; the 04:00 run today never happened
        now = dt.datetime(2026, 9, 3, 9, 0)
        p = fake_reclaim_log(dt.datetime(2026, 9, 2, 4, 30))
        f = md.check_reclaim_log(p, now)
        self.assertEqual(f.level, "fail", f.render())
        self.assertIn("stale", f.message)

    def test_missing_log_fails(self):
        f = md.check_reclaim_log(Path("/nonexistent/nope.log"),
                                 dt.datetime(2026, 9, 3, 9, 0))
        self.assertEqual(f.level, "fail")
        self.assertIn("missing", f.message)

    def test_latest_0400_wraps_midnight(self):
        # 01:00 belongs to yesterday's 04:00 schedule
        now = dt.datetime(2026, 9, 3, 1, 0)
        self.assertEqual(md.latest_0400(now),
                         dt.datetime(2026, 9, 2, 4, 0))
        # 06:00 is today's
        self.assertEqual(md.latest_0400(dt.datetime(2026, 9, 3, 6, 0)),
                         dt.datetime(2026, 9, 3, 4, 0))


class TestTimers(unittest.TestCase):
    SAMPLE_FAILED = (
        "dotfiles-sync.service\tloaded\tfailed\tfailed\tDaily dotfiles sync\n"
        "stack-health-metrics.service\tnot-found\tfailed\tfailed\tstale unit\n"
    )

    def test_parses_failed_units(self):
        names = md.parse_failed_units(self.SAMPLE_FAILED)
        self.assertEqual(names, ["dotfiles-sync.service",
                                 "stack-health-metrics.service"])

    def test_empty_output_passes(self):
        fs = md.check_timers("")
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0].level, "ok")

    def test_failed_unit_is_finding(self):
        fs = md.check_timers(self.SAMPLE_FAILED)
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0].level, "fail")
        self.assertIn("dotfiles-sync.service", fs[0].message)

    def test_skip_whitelist(self):
        fs = md.check_timers(self.SAMPLE_FAILED,
                             skipped_units=("dotfiles-sync.service",))
        self.assertEqual(fs[0].level, "fail")  # other unit still failing
        fs = md.check_timers(self.SAMPLE_FAILED,
                             skipped_units=("dotfiles-sync.service",
                                            "stack-health-metrics.service"))
        self.assertEqual(fs[0].level, "ok")


class TestDotfiles(unittest.TestCase):
    """check_dotfiles shells to git; _git is monkeypatched per case."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp()) / ".dotfiles"
        self.repo.mkdir()

    def test_missing_repo_fails(self):
        f = md.check_dotfiles(Path("/nonexistent/.dotfiles"))
        self.assertEqual(f.level, "fail")

    def test_unreachable_is_warn_not_fail(self):
        md._git = lambda repo, argv, timeout=20: (128, "Could not resolve host")
        f = md.check_dotfiles(self.repo)
        self.assertEqual(f.level, "warn")

    def test_ahead_is_fail(self):
        md._git = lambda repo, argv, timeout=20: (0, "3")
        f = md.check_dotfiles(self.repo)
        self.assertEqual(f.level, "fail")
        self.assertIn("3 commit", f.message)

    def test_synced_is_ok(self):
        md._git = lambda repo, argv, timeout=20: (0, "0")
        f = md.check_dotfiles(self.repo)
        self.assertEqual(f.level, "ok")

    def test_no_origin_ref_is_warn(self):
        md._git = lambda repo, argv, timeout=20: (128, "unknown revision")
        f = md.check_dotfiles(self.repo)
        self.assertEqual(f.level, "warn")


class TestDelegatedChecks(unittest.TestCase):
    def test_db_gate_classification(self):
        # rc 0 -> ok; rc 1 -> fail; rc 2 -> warn. Both paths must pass an
        # explicit --db so resolution never depends on script location.
        seen = []
        def fake(script, args, repo_root, timeout=120):
            seen.append(args)
            if "sonarr.db" in args[1]:
                return (2, "radarr DB not found ... skipping")
            return (0, "OK: radarr.db page size and footprint within healthy limits.")
        orig = md.run_script
        md.run_script = fake
        try:
            fs = md.check_db_gates(Path("/repo"))
        finally:
            md.run_script = orig
        by = {f.check: f for f in fs}
        self.assertEqual(by["radarr db"].level, "ok")
        self.assertEqual(by["sonarr db"].level, "warn")
        self.assertTrue(all(a and a[0] == "--db" for a in seen),
                        "every db gate must pass an explicit --db")

    def test_queue_classification(self):
        def fake(script, args, repo_root, timeout=120):
            return (0, "PASS nzbdav queue: queue is empty (0 item(s))")
        orig = md.run_script
        md.run_script = fake
        try:
            f = md.check_nzbdav_queue(Path("/repo"))
        finally:
            md.run_script = orig
        self.assertEqual(f.level, "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
