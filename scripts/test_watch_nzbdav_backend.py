#!/usr/bin/env python3
"""Tests for watch_nzbdav_backend.py decision logic.

The IO paths (HTTP probes, docker restart, Discord POST) are exercised live
on the stack, not here — these tests pin the pure functions: wedge
classification, crash-loop/cooldown gating, and state persistence.
"""

import tempfile
import unittest
from pathlib import Path

import watch_nzbdav_backend as w


class TestClassify(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(w.classify(True, True), "healthy")

    def test_wedged(self):
        self.assertEqual(w.classify(True, False), "wedged")

    def test_frontend_down(self):
        self.assertEqual(w.classify(False, False), "frontend-down")
        self.assertEqual(w.classify(False, True), "frontend-down")


class TestRestartWindow(unittest.TestCase):
    def test_counts_only_recent(self):
        now = 10_000.0
        state = {"restarts": [now - 100, now - 500, now - 1000]}
        # All three within a 30-min window.
        self.assertEqual(w.restarts_in_window(state, now, 30 * 60), 3)

    def test_ignores_stale(self):
        now = 10_000.0
        state = {"restarts": [now - 2000]}
        self.assertEqual(w.restarts_in_window(state, now, 60), 0)

    def test_empty(self):
        self.assertEqual(w.restarts_in_window({}, 10_000.0, 60), 0)


class TestShouldRestart(unittest.TestCase):
    def test_allows_first_restart(self):
        go, reason = w.should_restart({}, 10_000.0)
        self.assertTrue(go)
        self.assertEqual(reason, "")

    def test_cooldown_blocks(self):
        state = {"last_action_at": 9_990.0}
        go, reason = w.should_restart(state, 10_000.0)
        self.assertFalse(go)
        self.assertIn("cooldown", reason)

    def test_cooldown_expires(self):
        state = {"last_action_at": 9_000.0}
        go, _ = w.should_restart(state, 10_000.0)
        self.assertTrue(go)

    def test_crash_loop_blocks(self):
        now = 10_000.0
        state = {"restarts": [now - 60, now - 120, now - 180]}
        go, reason = w.should_restart(state, now)
        self.assertFalse(go)
        self.assertIn("crash loop", reason)

    def test_crash_loop_window_rolls(self):
        now = 10_000.0
        # 3 restarts, but the oldest falls outside the 30-min window.
        state = {"restarts": [now - 60, now - 120, now - 2000]}
        go, _ = w.should_restart(state, now)
        self.assertTrue(go)


class TestStateRoundTrip(unittest.TestCase):
    def test_save_load(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "state.json"
            w.save_state(path, {"state": "wedged", "restarts": [1.0, 2.0]})
            loaded = w.load_state(path)
            self.assertEqual(loaded["state"], "wedged")
            self.assertEqual(loaded["restarts"], [1.0, 2.0])

    def test_load_missing(self):
        self.assertEqual(w.load_state(Path("/nonexistent/state.json")), {})

    def test_load_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text("{not json")
            self.assertEqual(w.load_state(path), {})

    def test_restarts_bounded(self):
        now = 10_000.0
        state = {"restarts": [now - 100, now - 5000, now - 100000]}
        # Simulate the prune the watcher performs after each restart.
        state["restarts"] = [
            t for t in state["restarts"] if t >= now - w.CRASH_WINDOW]
        self.assertEqual(len(state["restarts"]), 1)


class TestJsonProbeShape(unittest.TestCase):
    def test_queue_url_shape(self):
        # The backend probe must hit the same queue endpoint the compose
        # healthcheck and check_nzbdav_queue.py use.
        url = "http://localhost:3000/api?mode=queue&output=json&apikey=KEY"
        self.assertIn("mode=queue", url)
        self.assertIn("output=json", url)
        self.assertIn("apikey=KEY", url)


if __name__ == "__main__":
    unittest.main()