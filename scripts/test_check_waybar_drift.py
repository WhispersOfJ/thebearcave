#!/usr/bin/env python3
"""Regression test for scripts/check_waybar_drift.py.

Verifies the live-vs-tracked dotfile guard cannot silently bit-rot:

  * every drift class is pinned: content mismatch, live copy missing,
    tracked file missing
  * a clean tree (byte-identical pairs) reports no drift
  * scripts/ keep their subdirectory layout; top-level files use LIVE_MAP
  * the CLI's --offline contract holds (rc 0, no live diff attempted)

Runs against the importable pure helpers with tmp_path trees — no real
~/.config touched — so it works on the CI runner. Run by validate.yml and
nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_waybar_drift.py`. Exits 0 when every assertion
holds, 1 otherwise.
"""

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_waybar_drift.py"

spec = importlib.util.spec_from_file_location("check_waybar_drift", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = 0


def expect(name, got, want):
    global failures
    if got == want:
        print(f"OK: {name}")
    else:
        print(f"FAIL: {name} expected {want!r}, got {got!r}")
        failures += 1


def make_tree(files: dict[str, bytes | None]) -> Path:
    """A canonical-shaped directory from {rel_path: bytes} (None = absent)."""
    root = Path(tempfile.mkdtemp())
    for rel, data in files.items():
        p = root / rel
        if data is None:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return root


CANON = {
    "config": b"{}\n",
    "style.css": b"* {}\n",
    "scripts/stack-tui-toggle.sh": b"#!/usr/bin/env bash\n",
    "sway/stack-tui.conf": b"for_window [app_id=\"stack_tui\"] floating enable\n",
}

# --- clean tree: every class reports no drift ------------------------------

pairs = {rel: (data, data) for rel, data in CANON.items()}
expect("clean tree", mod.find_drift(pairs), [])

# --- content drift (the class this check exists for) ------------------------

pairs = {rel: (data, data) for rel, data in CANON.items()}
pairs["style.css"] = (b"* {}\n", b"* { color: red }\n")
expect("content drift", mod.find_drift(pairs),
       [{"file": "style.css", "kind": "content",
         "canonical": mod._sha(b"* {}\n"), "live": mod._sha(b"* { color: red }\n")}])

# --- live copy missing (merge landed, sync forgotten) -----------------------

pairs = {rel: (data, data) for rel, data in CANON.items()}
pairs["config"] = (CANON["config"], None)
expect("live missing", mod.find_drift(pairs),
       [{"file": "config", "kind": "live-missing"}])

# --- tracked file missing (glob gap) ----------------------------------------

pairs = {rel: (data, data) for rel, data in CANON.items()}
pairs["scripts/stack-tui-toggle.sh"] = (None, CANON["scripts/stack-tui-toggle.sh"])
expect("canonical missing", mod.find_drift(pairs),
       [{"file": "scripts/stack-tui-toggle.sh", "kind": "canonical-missing"}])

# --- layout: scripts/ keep their subdirectory, sway/ map into ~/.config/sway

with tempfile.TemporaryDirectory() as home_str, tempfile.TemporaryDirectory() as can_str:
    home = Path(home_str)
    canonical = Path(can_str)
    for rel, data in CANON.items():
        p = canonical / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        live = mod.live_target(rel, home)
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(data)

    expect("tracked_files layout",
           mod.tracked_files(canonical), sorted(CANON))
    expect("live target for script",
           str(mod.live_target("scripts/stack-tui-toggle.sh", home)),
           str(home / ".config/waybar/scripts/stack-tui-toggle.sh"))
    expect("live target for sway rule",
           str(mod.live_target("sway/stack-tui.conf", home)),
           str(home / ".config/sway/stack-tui.conf"))

    drift = mod.find_drift(mod.collect_pairs(canonical, home))
    expect("clean collect_pairs", drift, [])

    # Content drift through the full disk path.
    (canonical / "style.css").write_bytes(b"/* changed */\n")
    drift = mod.find_drift(mod.collect_pairs(canonical, home))
    expect("disk-path content drift",
           [d["file"] for d in drift], ["style.css"])

# --- CLI contracts ----------------------------------------------------------

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = mod.main(["--offline"])
expect("offline rc", rc, 0)
expect("offline message", "offline mode" in buf.getvalue(), True)

# Real repo: tracked files must exist and the live host copies must match
# (skips softly on headless runners via the rc-2 path).
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = mod.main([])
if (Path.home() / ".config" / "waybar").is_dir():
    expect("live host tree", rc, 0)
else:
    expect("headless skip", rc, 2)

sys.exit(1 if failures else 0)
