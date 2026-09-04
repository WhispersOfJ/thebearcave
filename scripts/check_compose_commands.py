#!/usr/bin/env python3
"""Guard: no '#' comment text inside compose service command strings.

A service `command:` folded scalar is handed to the container runtime as one
string. When the image entrypoint is `/bin/sh -c` (e.g. nzbdav_rclone),
`#` inside that string is treated by the shell as a comment start and
silently truncates the rest of the command — in 2026 this dropped rclone's
entire `--rc` server block plus the vfs/timeout tuning flags, disabling RC
(so nzbdav's vfs/forget invalidation failed and *arr imports of fresh
downloads raced a stale VFS dir cache). Tuning rationale must live in YAML
comments ABOVE the block, never inside it.

Also pins the two nzbdav_rclone contract flags whose loss is invisible at
startup (the mount still works, RC silently does not): --rc-addr and
--vfs-cache-max-size must both survive rendering.

Usage:
  python3 scripts/check_compose_commands.py   # exit 0 = clean, 1 = violation
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"

# The rclone RC listener is a hard dependency of nzbdav (vfs/forget cache
# invalidation) and the vfs-cache cap is the analysis-load tuning; their
# loss is silent at container start, so pin them explicitly.
RCLONE_REQUIRED_FLAGS = (
    "--rc-addr=:5572",
    "--vfs-cache-max-size=300G",
)


def service_commands(compose_text: str) -> dict[str, str]:
    """Return {service: joined command string} for services with a command."""
    data = yaml.safe_load(compose_text)
    out = {}
    for name, svc in (data.get("services") or {}).items():
        cmd = svc.get("command")
        if cmd is None:
            continue
        if isinstance(cmd, list):
            cmd = " ".join(str(c) for c in cmd)
        out[name] = str(cmd)
    return out


def find_comment_injection(commands: dict[str, str]) -> list[str]:
    """Services whose rendered command contains a bare '#' (shell comment)."""
    return [
        f"{name}: '#' appears inside the command string (shell truncation bug)"
        for name, cmd in commands.items()
        if "#" in cmd
    ]


def check_rclone_flags(commands: dict[str, str]) -> list[str]:
    """Missing required nzbdav_rclone command flags (only when present)."""
    if "nzbdav_rclone" not in commands:
        return []
    cmd = commands["nzbdav_rclone"]
    return [
        f"nzbdav_rclone: missing {flag} in command"
        for flag in RCLONE_REQUIRED_FLAGS
        if flag not in cmd
    ]


def main() -> int:
    compose_text = COMPOSE.read_text(encoding="utf-8")
    commands = service_commands(compose_text)
    problems = find_comment_injection(commands) + check_rclone_flags(commands)
    if problems:
        print("Compose command guard violations:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"OK: {len(commands)} service command(s) clean, no shell truncation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
