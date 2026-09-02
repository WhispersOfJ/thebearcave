#!/usr/bin/env python3
"""Verify the stack's nightly maintenance actually happened, print a digest.

TODO.md project #1. The stack's unattended maintenance jobs fail silently:
the nightly disk reclaim (04:00 cron), the dotfiles commit+push (daily user
timer), the DB bloat gates (AGENTS.md landmine #9), and the nzbdav queue
(recreate-safety). This digest runs each morning and answers one question:
did everything that should have run, run — and pass?

Checks (one line each in the digest):

  * reclaim log  - ~/.stack-disk-reclaim.log must exist with an mtime newer
    than the most recent 04:00 boundary (the nightly cron fires then).
  * user timers  - `systemctl --user --failed` must list no units.
  * dotfiles     - local main must not be ahead of origin/main (ahead == the
    nightly push failed; the 17-day silent-failure class from 2026-09-02).
    Requires network; an unreachable origin is a soft WARN, not a FAIL.
  * radarr db    - delegated to scripts/check_radarr_db_size.py (page-size /
    footprint / MediaInfo bloat; landmine #9 gate).
  * sonarr db    - the same page/footprint checks run against sonarr.db via
    check_radarr_db_size.py --db --blob-table EpisodeFiles, so the MediaInfo
    row measures Sonarr's real EpisodeFiles blobs (the same gate
    stack-sonarr-prune remediates).
  * nzbdav queue - delegated to scripts/check_nzbdav_queue.py (recreate
    safety: queue must be empty). API unreachable == soft WARN.

Exit codes:
  0  every check passed (or soft-warned)
  1  at least one FAIL line

Decision logic lives in pure helpers (check_reclaim_log, check_timers,
check_dotfiles, db-gate parsing) so the offline unit test
(scripts/test_maintenance_digest.py) exercises them without systemd, git,
or the live stack.

Usage:
  python3 scripts/maintenance_digest.py
  python3 scripts/maintenance_digest.py --reclaim-log PATH --dotfiles DIR
"""

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECLAIM_LOG = Path.home() / ".stack-disk-reclaim.log"
DEFAULT_DOTFILES = Path.home() / ".dotfiles"
RECLAIM_HOUR = 4


# ---------------------------------------------------------------------------
# Findings model
# ---------------------------------------------------------------------------

class Finding:
    """One digest line. level: 'ok' | 'warn' | 'fail'."""

    def __init__(self, check: str, level: str, message: str):
        self.check = check
        self.level = level
        self.message = message

    def render(self) -> str:
        tag = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}[self.level]
        return f"  {tag}  {self.check:<14} {self.message}"

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Finding({self.check!r}, {self.level!r}, {self.message!r})"


# ---------------------------------------------------------------------------
# Reclaim log freshness
# ---------------------------------------------------------------------------

def latest_0400(now: _dt.datetime) -> _dt.datetime:
    """The most recent 04:00 boundary at or before *now* (naive-agnostic:
    compares wall-clock fields only)."""
    candidate = now.replace(hour=RECLAIM_HOUR, minute=0, second=0, microsecond=0)
    if now < candidate:
        candidate -= _dt.timedelta(days=1)
    return candidate


def check_reclaim_log(path: Path, now: _dt.datetime | None = None) -> Finding:
    now = now or _dt.datetime.now()
    if not path.is_file():
        return Finding("reclaim log", "fail",
                       f"missing: {path} (04:00 cron never wrote it)")
    mtime = _dt.datetime.fromtimestamp(path.stat().st_mtime)
    if mtime < latest_0400(now):
        age_h = max(0, int((now - mtime).total_seconds() // 3600))
        return Finding("reclaim log", "fail",
                       f"stale: last written {age_h}h ago, before today's "
                       f"{latest_0400(now):%H:%M} run")
    return Finding("reclaim log", "ok",
                   f"written {mtime:%H:%M} (today's {latest_0400(now):%H:%M} run)")


# ---------------------------------------------------------------------------
# User timer state
# ---------------------------------------------------------------------------

def parse_failed_units(text: str) -> list[str]:
    """Unit names from `systemctl --user --failed --no-legend` output.

    Lines look like:  dotfiles-sync.service  loaded  failed  failed  ...
    or, for units whose file was removed, 'not-found failed failed'.
    """
    names = []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        name = fields[0]
        if name.endswith(".service") or name.endswith(".timer"):
            names.append(name)
    return names


def check_timers(failed_output: str, skipped_units: tuple = ()) -> list[Finding]:
    """Any failed user unit is a finding (skipped_units lets the caller
    whitelist units that fail by design, e.g. psd while a browser runs)."""
    failed = [u for u in parse_failed_units(failed_output)
              if u not in skipped_units]
    if not failed:
        return [Finding("user timers", "ok", "no failed user units")]
    return [Finding("user timers", "fail",
                    "failed: " + ", ".join(failed))]


# ---------------------------------------------------------------------------
# Dotfiles push state
# ---------------------------------------------------------------------------

def _git(dotfiles: Path, argv: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", f"--git-dir={dotfiles}", "--work-tree", str(Path.home())]
            + argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"git error: {exc}"


def check_dotfiles(dotfiles: Path) -> Finding:
    """Compare local main against the *fetched* remote tip (FETCH_HEAD).

    A bare dotfiles repo may lack a `remote.origin.fetch` refspec, so plain
    `git fetch origin` updates only FETCH_HEAD and leaves a stale
    refs/remotes/origin/main behind — comparing against origin/main then
    reports false 'ahead' counts (seen 2026-09-02). FETCH_HEAD is always
    written by the fetch and is the authoritative remote tip.
    """
    if not dotfiles.is_dir():
        return Finding("dotfiles", "fail", f"missing repo: {dotfiles}")
    rc, out = _git(dotfiles, ["fetch", "origin"])
    if rc != 0:
        return Finding("dotfiles", "warn",
                       f"origin unreachable; push state unverified ({out[:80]})")
    rc, out = _git(dotfiles, ["rev-list", "--count", "FETCH_HEAD..main"])
    if rc != 0:
        return Finding("dotfiles", "warn",
                       "no local main branch (fresh repo); skipped")
    try:
        ahead = int(out.splitlines()[-1])
    except (ValueError, IndexError):
        ahead = -1
    if ahead > 0:
        return Finding("dotfiles", "fail",
                       f"main is {ahead} commit(s) ahead of the remote "
                       "(nightly push did not land)")
    return Finding("dotfiles", "ok", "main matches the remote tip")


# ---------------------------------------------------------------------------
# DB gates + nzbdav queue (delegated to existing check scripts)
# ---------------------------------------------------------------------------

def run_script(script_name: str, args: list[str], repo_root: Path,
               timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / script_name)] + args,
        capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def check_db_gates(repo_root: Path) -> list[Finding]:
    """Radarr + Sonarr DB health via check_radarr_db_size.py (exit 0/1/2).

    Both DB paths are passed explicitly with --db (relative to repo_root, the
    *operational* checkout) because the delegated script resolves its own
    defaults against its file location — which is only right when the two
    live in the same checkout. The sonarr leg also passes
    --blob-table EpisodeFiles so its MediaInfo probe measures the real blob
    table (MovieFiles, the radarr default, is absent there and would read 0
    bytes); per-app footprint defaults resolve from the DB filename.
    """
    findings = []
    for label, rel, blob_table in (
            ("radarr db", "config/radarr/radarr.db", None),
            ("sonarr db", "config/sonarr/sonarr.db", "EpisodeFiles")):
        db_args = ["--db", str(repo_root / rel)]
        if blob_table:
            db_args += ["--blob-table", blob_table]
        rc, out = run_script("check_radarr_db_size.py", db_args, repo_root)
        tail = out.splitlines()[-1][:90] if out else "(no output)"
        if rc == 0:
            findings.append(Finding(label, "ok", tail))
        elif rc == 1:
            findings.append(Finding(label, "fail", tail))
        else:  # 2: DB not located/readable — soft warn on fresh installs
            findings.append(Finding(label, "warn", tail))
    return findings


def check_nzbdav_queue(repo_root: Path) -> Finding:
    rc, out = run_script("check_nzbdav_queue.py", ["--allow-unreachable"],
                         repo_root)
    tail = out.splitlines()[-1][:90] if out else "(no output)"
    if rc == 0:
        level, msg = "ok", tail
    elif rc == 2:
        level, msg = "warn", tail  # unreachable/API error — soft skip
    else:
        level, msg = "fail", tail
    return Finding("nzbdav queue", level, msg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reclaim-log", default=str(DEFAULT_RECLAIM_LOG))
    ap.add_argument("--dotfiles", default=str(DEFAULT_DOTFILES))
    ap.add_argument("--repo", default=str(ROOT),
                    help="operational checkout holding config/ (default: this repo)")
    ap.add_argument("--skip-user-unit", action="append", default=[],
                    help="whitelist a user unit that fails by design (repeatable)")
    args = ap.parse_args()

    findings = [check_reclaim_log(Path(args.reclaim_log))]

    # systemctl --user --failed --no-legend  (offline test injects text)
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "--failed", "--no-legend"],
            capture_output=True, text=True, timeout=30)
        failed_text = proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        failed_text = ""
    findings += check_timers(failed_text, tuple(args.skip_user_unit))

    repo_root = Path(args.repo)
    findings.append(check_dotfiles(Path(args.dotfiles)))
    findings += check_db_gates(repo_root)
    findings.append(check_nzbdav_queue(repo_root))

    print(f"Maintenance digest — {_dt.datetime.now():%Y-%m-%d %H:%M}")
    for f in findings:
        print(f.render())

    failed = [f for f in findings if f.level == "fail"]
    if failed:
        print(f"DIGEST FAIL: {len(failed)} finding(s); see lines above")
        return 1
    print("DIGEST OK: nightly maintenance verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
