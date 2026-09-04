#!/usr/bin/env python3
"""Regression test for scripts/check_nzbdav_queue.py.

Verifies the queue guard cannot silently bit-rot:

  * an empty queue (slots=[], noofslots=0) reports depth 0 -> exit 0
  * a non-empty queue reports depth > threshold -> exit 1
  * a malformed/unparseable response -> exit 2 (not a silent pass)
  * --allow-unreachable turns an unreachable API into exit 0
  * the SABnzbd `noofslots` int shape is honored (not just slots list)

Runs against importable pure-Python logic (no live nzbdav needed), so it
works on the CI runner. Run by .github/workflows/validate.yml and locally
via `python3 scripts/test_check_nzbdav_queue.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_nzbdav_queue.py"

# Import the checker as a module (it has no package-relative imports).
spec = importlib.util.spec_from_file_location("check_nzbdav_queue", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _q(slots=None, noofslots=None):
    """Build a SABnzbd-shaped queue response."""
    q = {}
    if slots is not None:
        q["slots"] = slots
    if noofslots is not None:
        q["noofslots"] = noofslots
    return {"queue": q}


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name} (got {got})")
        else:
            print(f"FAIL: {name} expected {want}, got {got}")
            failures += 1

    # --- queue_depth parsing -------------------------------------------
    expect("empty slots list -> depth 0",
           mod.queue_depth(_q(slots=[])), 0)
    expect("non-empty slots list -> depth 3",
           mod.queue_depth(_q(slots=["a", "b", "c"])), 3)
    expect("noofslots int -> depth 5",
           mod.queue_depth(_q(noofslots=5)), 5)
    expect("slots int shape -> depth 2",
           mod.queue_depth(_q(slots=2)), 2)
    expect("missing both -> unparseable (-1)",
           mod.queue_depth(_q()), -1)
    expect("garbage top-level -> unparseable (-1)",
           mod.queue_depth({"notqueue": 1}), -1)

    # --- check() decision logic -----------------------------------------
    # Monkeypatch fetch_queue to return canned data (no live HTTP).
    real_fetch = mod.fetch_queue

    def fake_fetch_empty(*a, **kw):
        return _q(slots=[])

    def fake_fetch_busy(*a, **kw):
        return _q(slots=["n1", "n2"])

    def fake_fetch_garbage(*a, **kw):
        return {"bogus": "no queue key"}

    def fake_fetch_raise(*a, **kw):
        raise OSError("connection refused")

    # Empty queue -> exit 0
    mod.fetch_queue = fake_fetch_empty
    code, _ = mod.check("http://x", "key", 5, 0, False)
    expect("empty queue -> exit 0", code, 0)

    # Non-empty queue -> exit 1
    mod.fetch_queue = fake_fetch_busy
    code, _ = mod.check("http://x", "key", 5, 0, False)
    expect("non-empty queue -> exit 1", code, 1)

    # Threshold honored: 2 items, threshold 2 -> exit 0
    mod.fetch_queue = fake_fetch_busy
    code, _ = mod.check("http://x", "key", 5, 2, False)
    expect("queue within threshold -> exit 0", code, 0)

    # Garbage response -> exit 2
    mod.fetch_queue = fake_fetch_garbage
    code, _ = mod.check("http://x", "key", 5, 0, False)
    expect("unparseable response -> exit 2", code, 2)

    # Unreachable without --allow-unreachable -> exit 2
    mod.fetch_queue = fake_fetch_raise
    code, _ = mod.check("http://x", "key", 5, 0, False)
    expect("unreachable -> exit 2", code, 2)

    # Unreachable WITH --allow-unreachable -> exit 0
    code, _ = mod.check("http://x", "key", 5, 0, True)
    expect("unreachable + allow -> exit 0", code, 0)

    mod.fetch_queue = real_fetch

    # --- Compose healthcheck contract -----------------------------------
    compose = (ROOT / "docker-compose.yml").read_text()
    expect(
        "nzbdav healthcheck probes frontend and authenticated queue API",
        "curl -sf http://localhost:3000/healthz && curl -sf" in compose
        and "localhost:3000/api?mode=queue&output=json&apikey=$${FRONTEND_BACKEND_API_KEY}" in compose,
        True,
    )

    expect(
        "nzbdav healthcheck does not probe nonexistent backend port",
        "localhost:8080" not in compose,
        True,
    )

    # --- live entry point smoke (offline flag) --------------------------
    proc = __import__("subprocess").run(
        [sys.executable, str(CHECKER_PATH), "--offline"],
        capture_output=True, text=True)
    expect("--offline CLI -> exit 0", proc.returncode, 0)

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall check_nzbdav_queue tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
