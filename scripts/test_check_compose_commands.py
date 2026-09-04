#!/usr/bin/env python3
"""Regression test for scripts/check_compose_commands.py.

Verifies the compose-command guard cannot silently bit-rot:

  * the real docker-compose.yml passes (no '#' inside any service command,
    and nzbdav_rclone keeps --rc-addr and --vfs-cache-max-size)
  * a fixture with '#' inside a service command fails and names the service
  * a fixture whose nzbdav_rclone command drops --rc-addr fails
  * a fixture without a command field passes (no false positive)

Runs against throwaway temp dirs plus the real compose file, so it works on
the CI runner. Run by validate.yml and nightly-healthcheck.yml, and locally
via `python3 scripts/test_check_compose_commands.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_compose_commands.py"

spec = importlib.util.spec_from_file_location("check_compose_commands", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CLEAN_FIXTURE = """
services:
  web:
    image: nginx
    command:
      - >
        exec nginx -g 'daemon off;'
  nzbdav_rclone:
    image: rclone/rclone:1.75.0
    command:
      - >
        exec rclone mount x: /mnt
        --rc
        --rc-addr=:5572
        --vfs-cache-max-size=300G
"""

COMMENT_FIXTURE = """
services:
  nzbdav_rclone:
    image: rclone/rclone:1.75.0
    command:
      - >
        exec rclone mount x: /mnt
        --rc-addr=:5572
        # 300G cap rationale written inside the block
        --vfs-cache-max-size=300G
"""

MISSING_FLAG_FIXTURE = """
services:
  nzbdav_rclone:
    image: rclone/rclone:1.75.0
    command:
      - >
        exec rclone mount x: /mnt
        --rc-addr=:5572
"""

NO_COMMAND_FIXTURE = """
services:
  web:
    image: nginx
"""


def run_fixture(fixture: str) -> tuple[int, str]:
    """Run the check against a temp dir containing one compose fixture."""
    tmp = Path(tempfile.mkdtemp(prefix="compose-cmd-"))
    try:
        (tmp / "docker-compose.yml").write_text(fixture, encoding="utf-8")
        mod.COMPOSE = tmp / "docker-compose.yml"
        rc = mod.main()
        return rc, ""
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

    # --- live tree ------------------------------------------------------
    mod.COMPOSE = ROOT / "docker-compose.yml"
    real_rc = mod.main()
    expect("real docker-compose.yml passes", real_rc == 0, detail=f"rc={real_rc}")

    commands = mod.service_commands((ROOT / "docker-compose.yml").read_text())
    expect("nzbdav_rclone command present", "nzbdav_rclone" in commands)
    expect(
        "nzbdav_rclone keeps --rc-addr",
        "--rc-addr=:5572" in commands.get("nzbdav_rclone", ""),
    )
    expect(
        "nzbdav_rclone keeps --vfs-cache-max-size",
        "--vfs-cache-max-size=300G" in commands.get("nzbdav_rclone", ""),
    )

    # --- fixtures -------------------------------------------------------
    rc, _ = run_fixture(CLEAN_FIXTURE)
    expect("clean fixture passes", rc == 0, detail=f"rc={rc}")

    rc, _ = run_fixture(COMMENT_FIXTURE)
    expect("comment-inside-command fails", rc == 1, detail=f"rc={rc}")

    rc, _ = run_fixture(MISSING_FLAG_FIXTURE)
    expect("missing --vfs-cache-max-size fails", rc == 1, detail=f"rc={rc}")

    rc, _ = run_fixture(NO_COMMAND_FIXTURE)
    expect("no-command fixture passes", rc == 0, detail=f"rc={rc}")

    if failures == 0:
        print("test_check_compose_commands: all assertions passed")
        return 0
    print(f"test_check_compose_commands: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
