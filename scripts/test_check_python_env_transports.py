#!/usr/bin/env python3
"""Regression test for scripts/check_python_env_transports.py.

Verifies the guard cannot silently bit-rot:

  * a fixture functions dir with only scalar env transports (LIMIT/URL/KEY/
    ID/ENDPOINT/APP/PLEX_URL/TOKEN) and non-transport lines passes
  * a fixture line with SERIES_MAP=... python3 fails and names the file:line
  * a lowercase data-sized transport (series_map=... python3) also fails

Runs against throwaway temp dirs (no live tree needed), so it works on the
CI runner. Run by validate.yml and nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_python_env_transports.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_python_env_transports.py"

spec = importlib.util.spec_from_file_location(
    "check_python_env_transports", CHECKER_PATH
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SCALAR_FIXTURE = """\
local limit="${2:-10}"
count="$(STATE="$2" URL="$url" python3 -c "")"
echo "$result" | LIMIT="$limit" python3 -c ""
echo "$item" | URL="$url" KEY="$key" ID="$id" ENDPOINT="$endpoint" APP="$app" python3 -c ""
echo "$sections" | PLEX_URL="$plex_url" TOKEN="$token" python3 -c ""
"""

BAD_FIXTURE = 'echo "$result" | SERIES_MAP="$series_map" LIMIT="$limit" python3 -c ""\n'
BAD_LOWER_FIXTURE = 'echo "$a" | series_map="$m" python3 -c ""\n'


def run_on(fixture: str) -> tuple[int, str]:
    """Run the check against a temp dir containing one fixture file."""
    tmp = Path(tempfile.mkdtemp(prefix="env-transport-"))
    try:
        (tmp / "stack-fixture.sh").write_text(fixture, encoding="utf-8")
        mod.FUNC_DIR = tmp
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = mod.main()
        return rc, err.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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

    rc, _ = run_on(SCALAR_FIXTURE)
    expect("scalar-only fixtures pass", rc == 0, detail=f"rc={rc}")

    rc, err = run_on(BAD_FIXTURE)
    expect(
        "SERIES_MAP transport fails",
        rc == 1 and "SERIES_MAP" in err,
        detail=err.strip(),
    )
    expect("failure names file:line", "stack-fixture.sh:1" in err, detail=err.strip())

    rc, err = run_on(BAD_LOWER_FIXTURE)
    expect(
        "lowercase data transport fails",
        rc == 1 and "series_map" in err,
        detail=err.strip(),
    )

    if failures == 0:
        print("test_check_python_env_transports: all assertions passed")
        return 0
    print(f"test_check_python_env_transports: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
