#!/usr/bin/env python3
"""Regression test for scripts/check_compose_mounts.py.

Verifies the guard cannot silently bit-rot:

  * a compose file with volume entries merged onto one line exits 1
  * a clean control fixture exits 0
  * the real docker-compose.yml exits 0

Run by .github/workflows/validate.yml (and locally via
`python3 scripts/test_check_compose_mounts.py`). Exits 0 when every
assertion holds, 1 otherwise.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check_compose_mounts.py"
FIXTURES = ROOT / "tests" / "check_compose_mounts"
MERGED = FIXTURES / "merged.yml"
CLEAN = FIXTURES / "clean.yml"
REAL = ROOT / "docker-compose.yml"


def run_checker(path: Path) -> int:
    if not path.exists():
        print(f"FAIL: missing fixture {path}")
        return -2
    proc = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
    return proc.returncode


def main() -> int:
    failures = 0

    merged_rc = run_checker(MERGED)
    if merged_rc == 1:
        print("OK: merged fixture rejected (exit 1)")
    else:
        print(f"FAIL: merged fixture expected exit 1, got {merged_rc}")
        failures += 1

    clean_rc = run_checker(CLEAN)
    if clean_rc == 0:
        print("OK: clean control accepted (exit 0)")
    else:
        print(f"FAIL: clean control expected exit 0, got {clean_rc}")
        failures += 1

    real_rc = run_checker(REAL)
    if real_rc == 0:
        print("OK: real docker-compose.yml accepted (exit 0)")
    else:
        print(f"FAIL: real docker-compose.yml expected exit 0, got {real_rc}")
        failures += 1

    if failures:
        print(f"\n{len(failures)} assertion(s) failed")
        return 1
    print("\nall check_compose_mounts tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())