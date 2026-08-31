#!/usr/bin/env python3
"""Check that secrets never drift into the git tree.

Backs up the SECURITY.md / docs/security.md promise that secrets are never
committed. Fails when a sensitive path — the real `.env`, the `secrets/`
directory, or the rclone remote-credentials file
(`config/nzbdav-rclone/rclone.conf`) — is *tracked by git*, or when the
.gitignore rules protecting them are removed (which would let an accidental
`git add -A` stage them).

Only queries git (read-only). In CI the checkout is a fresh clone, so a
tracked sensitive file means it reached the repo tree; on the host, an
untracked-but-present `.env` is the expected setup and does not fail.

Exit codes: 0 clean, 1 drift found, 2 not a git repository (skip).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SENSITIVE_PATHS = [
    ".env",
    "secrets/",
    "config/nzbdav-rclone/rclone.conf",
]


def is_git_repo(repo_root: Path = ROOT) -> bool:
    """True when repo_root is inside a git working tree."""
    r = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def tracked_files(repo_root: Path, path: str) -> list[str]:
    """Tracked files matching the given path (empty when none)."""
    r = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", path],
        capture_output=True, text=True,
    )
    return [line for line in r.stdout.splitlines() if line]


def is_ignored(repo_root: Path, path: str) -> bool:
    """True when the path is covered by a gitignore rule (git check-ignore)."""
    r = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "-q", "--", path],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def assess(repo_root: Path = ROOT) -> list[str]:
    """Return a list of drift errors; empty means the tree is clean."""
    errors: list[str] = []
    for path in SENSITIVE_PATHS:
        tracked = tracked_files(repo_root, path)
        if tracked:
            errors.append(f"{path} is tracked by git (committed secrets): {', '.join(tracked)}")
    for path in SENSITIVE_PATHS:
        if not is_ignored(repo_root, path):
            errors.append(f"{path} is not covered by .gitignore (accidental staging risk)")
    return errors


def main() -> int:
    if not is_git_repo():
        print(f"[skip] {ROOT} is not a git working tree; nothing to check.")
        return 2

    errors = assess()
    if errors:
        for error in errors:
            print(f"  [error] {error}")
        print(f"{len(errors)} secret-drift error(s) — fix before merging.")
        return 1

    print("OK: .env, secrets/, and rclone.conf are untracked and gitignored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
