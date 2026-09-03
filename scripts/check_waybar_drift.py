#!/usr/bin/env python3
"""Check that the live waybar/sway dotfiles match the tracked canonical copies.

The stack-tui waybar module (custom/stack) was written directly into
~/.config/waybar and only later tracked in-repo under
services/bash-functions/waybar/ (feat/waybar-stack-tui-module). Two copies
of the same file drift silently: edit the live one and the repo goes stale,
merge a repo change and the bar never picks it up (waybar does not hot-read
its config; sway for_window rules live in ~/.config/sway).

This is the mechanical version: the tracked waybar/ directory is the source
of truth, the live XDG paths are the deployed state, and every tracked file
must exist byte-identical at its live target:

  config            -> ~/.config/waybar/config
  style.css         -> ~/.config/waybar/style.css
  scripts/<name>    -> ~/.config/waybar/scripts/<name>
  sway/<name>.conf  -> ~/.config/sway/<name>.conf   (sourced via `include`)

A drift report ends with a sync-reminder line (the cp commands) because the
fix is mechanical — and after editing a live bind-mounted/served config the
waybar restart reminder applies (AGENTS.md landmine #1: the process keeps
serving the old file until restarted).

Exit 0 = every tracked file matches its live copy; 1 = drift (or a tracked
file missing its live counterpart — same remediation); 2 = cannot assess
(no live waybar config at all — headless host/CI, use --offline there).
The check_* family's soft-exit: preflight and the maintenance digest read 2
as a SKIP/WARN, CI runs this with --offline.

Usage:
  python3 scripts/check_waybar_drift.py            # live diff
  python3 scripts/check_waybar_drift.py --offline  # CI/no-desktop: print OK
"""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "services" / "bash-functions" / "waybar"

# Tracked relative path -> live path relative to $HOME.
LIVE_MAP = {
    "config": ".config/waybar/config",
    "style.css": ".config/waybar/style.css",
    "sway/stack-tui.conf": ".config/sway/stack-tui.conf",
}


def live_target(rel: str, home: Path) -> Path:
    """Live absolute path for one tracked file; scripts/ keeps its layout."""
    if rel.startswith("scripts/"):
        return home / ".config" / "waybar" / rel
    return home / LIVE_MAP[rel]


def tracked_files(canonical: Path) -> list[str]:
    """Relative paths of tracked dotfiles (config, style, scripts, sway/)."""
    files: list[str] = []
    for pattern in ("config", "style.css", "scripts/*.sh", "sway/*.conf"):
        files.extend(str(p.relative_to(canonical)) for p in canonical.glob(pattern))
    return sorted(files)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def find_drift(pairs: dict[str, tuple[bytes | None, bytes | None]]) -> list[dict]:
    """Compare (canonical, live) byte pairs per tracked file. Pure.

    None means "missing". Findings carry a kind (content / live-missing /
    canonical-missing) so the CLI report and the unit tests can pin each
    drift class exactly.
    """
    drift: list[dict] = []
    for rel in sorted(pairs):
        canon, live = pairs[rel]
        if canon is None:
            drift.append({"file": rel, "kind": "canonical-missing"})
            continue
        if live is None:
            drift.append({"file": rel, "kind": "live-missing"})
        elif canon != live:
            drift.append({"file": rel, "kind": "content",
                          "canonical": _sha(canon), "live": _sha(live)})
    return drift


def collect_pairs(canonical: Path, home: Path) -> dict[str, tuple[bytes | None, bytes | None]]:
    """Read the tracked files and their live counterparts off disk."""
    pairs: dict[str, tuple[bytes | None, bytes | None]] = {}
    for rel in tracked_files(canonical):
        canon = canonical / rel
        live = live_target(rel, home)
        pairs[rel] = (
            canon.read_bytes() if canon.is_file() else None,
            live.read_bytes() if live.is_file() else None,
        )
    return pairs


def sync_hint(files: list[str], home: Path) -> str:
    """The cp commands that remediate every reported drift at once."""
    waybar = [f for f in files if not f.startswith("sway/")]
    sway = [f for f in files if f.startswith("sway/")]
    lines = ["hint: sync with:"]
    if waybar:
        lines.append(f"  cp -r {CANONICAL}/{'{config,style.css,scripts}'} "
                     f"{home}/.config/waybar/")
    if sway:
        lines.append(f"  cp {CANONICAL}/sway/*.conf {home}/.config/sway/")
    lines.append("hint: then restart waybar / swaymsg reload (bind-mount rule)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--offline" in argv:
        print("OK (offline mode — live dotfile diff skipped)")
        return 0

    home = Path.home()
    if not (home / ".config" / "waybar").is_dir():
        print("CHECK SKIPPED: no live waybar config on this host (headless?)")
        return 2

    drift = find_drift(collect_pairs(CANONICAL, home))
    if not drift:
        n = len(tracked_files(CANONICAL))
        print(f"OK: {n} tracked waybar/sway dotfile(s) match the live copies.")
        return 0

    print(f"CHECK FAILED: {len(drift)} tracked dotfile(s) drifted from the "
          "live copies:")
    for d in drift:
        if d["kind"] == "content":
            print(f"  [content] {d['file']}: canonical {d['canonical']} "
                  f"!= live {d['live']}")
        else:
            print(f"  [{d['kind']}] {d['file']}")
    print(sync_hint([d["file"] for d in drift], home))
    return 1


if __name__ == "__main__":
    sys.exit(main())
