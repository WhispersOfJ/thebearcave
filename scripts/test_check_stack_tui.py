#!/usr/bin/env python3
"""Contract test for services/bash-functions/scripts/stack-tui.

Pins stack-tui's behavior as a compact executable contract so the TUI can
never silently drift from the shared metadata parser or the CLI surface.
Runs fully offline on plain python3 (no urwid, no .env, no live stack), so
CI can run it. Invoke via `python3 scripts/test_check_stack_tui.py` (also
wired into validate.yml and nightly-healthcheck.yml). Exits 0 when every
assertion holds, 1 otherwise.

The contract:

  * the parsed surface: 96 stack-* functions, unique names, and the
    danger/args classification for representative boundary rows
  * `--list` stays byte-consistent with parse_functions for every function
  * every function has help text (or the "(no help comment)" placeholder,
    exactly 9 of which exist)
  * `--run` error boundaries (unknown name, missing name) and one live fire
    (`stack-help` — pure bash, no docker/API needed)
"""

import importlib.util
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TUI = ROOT / "services" / "bash-functions" / "scripts" / "stack-tui"

spec = importlib.util.spec_from_loader(
    "stack_tui", SourceFileLoader("stack_tui", str(TUI)))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# name -> (danger, args). Boundary rows: one per quadrant plus the functions
# with classification history (urllib-PUT mutation, out-of-body directive,
# mutating restart, read-only blocklist).
SPOT = {
    "stack-version":           (False, []),
    "stack-help":              (False, []),
    "stack-restart-all":       (True,  ["-y|--yes"]),
    "stack-arr-backlog":       (False, ["radarr|sonarr"]),
    "stack-arr-toggle-search": (True,  ["radarr|sonarr|all", "on|off"]),
    "stack-arr-blocklist":     (False, ["radarr|sonarr"]),
    "stack-plex":              (True,  ["refresh-libraries|empty-trash|analyze|scan"]),
    # Explicit "# danger: true" annotations — butler tasks with destructive
    # server-side effects (media/blob deletion, cache/log cleanup, updates).
    "stack-plex-garbage-collect-media": (True, []),
    "stack-plex-garbage-collect-blobs": (True, []),
    "stack-plex-clean-cache-files":     (True, []),
    "stack-plex-clean-log-files":       (True, []),
    "stack-plex-automatic-updates":     (True, []),
    "stack-plex-butler":                (True, []),
    "stack-plex-butler-all":            (True, []),
}

EXPECTED_COUNT = 98
EXPECTED_PLACEHOLDER_COUNT = 9


def cli(*args) -> tuple[int, str, str]:
    """Run the script with plain python3 (no urwid)."""
    proc = subprocess.run(["python3", str(TUI), *args], capture_output=True,
                          text=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    failures = 0

    def expect(name, got, want=True, detail=""):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            suffix = f" - {detail}" if detail else ""
            print(f"FAIL: {name} expected {want}, got {got}{suffix}")
            failures += 1

    funcs = mod.parse_functions()
    by_name = {f["name"]: f for f in funcs}

    # --- parsed surface ------------------------------------------------
    expect("surface count", len(funcs), EXPECTED_COUNT, f"got {len(funcs)}")
    expect("names unique", len(by_name), len(funcs))
    expect("all names stack-*",
           all(f["name"].startswith("stack-") for f in funcs))

    for name, (danger, args) in sorted(SPOT.items()):
        f = by_name[name]
        expect(f"spot {name} danger", f["danger"], danger)
        expect(f"spot {name} args", f["args"], args)

    ph = [f["name"] for f in funcs if f["help"] == ["(no help comment)"]]
    expect("every function has help text", all(f["help"] for f in funcs))
    expect("help placeholder count", len(ph), EXPECTED_PLACEHOLDER_COUNT,
           f"got {len(ph)}: {ph}")

    # --- --list parity with the parser ----------------------------------
    rc, out, err = cli("--list")
    expect("--list exits 0", rc, 0, err.strip())
    rows = {}
    for ln in out.splitlines():
        if not ln:
            continue
        name, _cat, danger, complete = ln.split("\t", 3)
        rows[name] = (danger == "danger", complete)
    expect("--list covers every function", set(rows), set(by_name))
    mismatch = [
        f"{name}: want {(f['danger'], f['complete'])}, got {rows.get(name)}"
        for name, f in by_name.items()
        if (f["danger"], f["complete"]) != rows.get(name)
    ]
    expect("--list matches parser", not mismatch, detail="; ".join(mismatch[:3]))

    # --- --run boundaries ------------------------------------------------
    rc, _o, err = cli("--run", "stack-no-such-function")
    expect("--run unknown fn rc", rc, 2, err.strip())
    expect("--run unknown fn message", "unknown function" in err,
           detail=err.strip())

    rc, _o, err = cli("--run")
    expect("--run missing name rc", rc, 2, err.strip())

    rc, _o, err = cli("--run", "stack-help")
    expect("--run stack-help rc", rc, 0, err.strip()[:200])

    if failures == 0:
        print("test_check_stack_tui: all assertions passed")
        return 0
    print(f"test_check_stack_tui: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
