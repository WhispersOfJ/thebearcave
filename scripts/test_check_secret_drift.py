#!/usr/bin/env python3
"""Regression test for scripts/check_secret_drift.py.

Verifies the guard cannot silently bit-rot:

  * a clean repo (sensitive paths gitignored, nothing tracked) passes
  * a tracked .env IS flagged
  * a tracked file under secrets/ IS flagged
  * a tracked rclone.conf IS flagged
  * a removed gitignore rule IS flagged (even with nothing tracked)
  * a non-repo directory reports is_git_repo() == False

Runs against throwaway temp git repos (no live tree needed), so it works on
the CI runner. Run by validate.yml and nightly-healthcheck.yml, and locally
via `python3 scripts/test_check_secret_drift.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_secret_drift.py"

spec = importlib.util.spec_from_file_location("check_secret_drift", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GOOD_IGNORE = """\
.env
secrets/
config/nzbdav-rclone/rclone.conf
"""


def make_repo(gitignore: str, files: dict[str, str], force_add: list[str] = ()) -> Path:
    """Create a throwaway git repo seeded with files; optionally force-add ignored ones."""
    tmp = Path(tempfile.mkdtemp(prefix="secret-drift-"))
    (tmp / ".gitignore").write_text(gitignore)
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    subprocess.run(["git", "-C", str(tmp), "init", "-q"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(tmp), "add", ".gitignore"], check=True,
                   capture_output=True)
    if force_add:
        subprocess.run(["git", "-C", str(tmp), "add", "-f", *force_add],
                       check=True, capture_output=True)
    return tmp


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name} expected {want!r}, got {got!r}")
            failures += 1

    repos = []

    clean = make_repo(GOOD_IGNORE, {".env": "SECRET=1"})
    repos.append(clean)
    expect("clean repo: no drift", mod.assess(clean), [])

    tracked_env = make_repo(GOOD_IGNORE, {".env": "SECRET=1"}, force_add=[".env"])
    repos.append(tracked_env)
    got = mod.assess(tracked_env)
    expect("tracked .env flagged", any(".env is tracked" in e for e in got), True)

    tracked_secrets = make_repo(GOOD_IGNORE,
                                {"secrets/x.key": "secret"},
                                force_add=["secrets/"])
    repos.append(tracked_secrets)
    got = mod.assess(tracked_secrets)
    expect("tracked secrets/ flagged", any("secrets/ is tracked" in e for e in got), True)

    tracked_rclone = make_repo(
        GOOD_IGNORE,
        {"config/nzbdav-rclone/rclone.conf": "pass = obscured"},
        force_add=["config/nzbdav-rclone/rclone.conf"],
    )
    repos.append(tracked_rclone)
    got = mod.assess(tracked_rclone)
    expect("tracked rclone.conf flagged",
           any("rclone.conf is tracked" in e for e in got), True)

    # .gitignore rule removed; file present but untracked -> staging risk
    no_rule = make_repo("# nothing protects rclone\n",
                        {"config/nzbdav-rclone/rclone.conf": "pass = obscured"})
    repos.append(no_rule)
    got = mod.assess(no_rule)
    expect("missing gitignore rule flagged",
           any("not covered by .gitignore" in e and "rclone.conf" in e for e in got), True)

    # no-rule repo must NOT claim anything is tracked
    expect("missing-rule repo has no tracked complaint",
           any("is tracked" in e for e in got), False)

    not_repo = Path(tempfile.mkdtemp(prefix="secret-drift-norepo-"))
    repos.append(not_repo)
    expect("non-repo detected", mod.is_git_repo(not_repo), False)

    for repo in repos:
        shutil.rmtree(repo, ignore_errors=True)

    if failures == 0:
        print("test_check_secret_drift: all assertions passed")
        return 0
    print(f"test_check_secret_drift: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
