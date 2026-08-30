#!/usr/bin/env python3
"""Verify each running container's mounts match its compose definition.

`docker compose config --quiet` validates that the compose file is coherent,
but it cannot see what a *running* container was actually created with. A
container can sit on stale mounts — a mount removed or repointed in compose but
never recreated, or a bind mount resolved against a dead FUSE instance — while
the compose file looks fine. This is exactly how plex lost its /data/shows
mount in the anime-consolidation incident.

This check compares, for every running container, its actual mounts
(`docker inspect`) against the resolved compose definition
(`docker compose config --format json`). It flags a container when a mount is
missing, present-but-undeclared, or resolved to a different source/target.
Two benign differences are normalized away so they don't false-positive:

  1. named volumes: Docker prepends the project name (`thebearcave_voldata`
     <=> declared `voldata`)
  2. bind sources: Docker strips a trailing slash (`/dev/disk/` <=> `/dev/disk`)

Run by scripts/preflight.sh (docker-gated) and locally via
`python3 scripts/check_mount_drift.py`. Exit 0 = every running container matches
its compose definition; 1 = a divergence (or docker unavailable).

Usage:
  python3 scripts/check_mount_drift.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def compose(args: list[str]) -> subprocess.CompletedProcess:
    return run(["docker", "compose", *args])


def normalize(typ: str, source: str, target: str, project: str) -> tuple[str, str, str]:
    """Make a mount point (type, source, target) comparable across docker CLIs.

    Bind sources arrive with either a trailing slash (from compose config) or
    without (from inspect); named-volume sources arrive project-prefixed from
    inspect but bare from config. Canonicalize both.
    """
    if typ == "volume":
        prefix = f"{project}_"
        if source.startswith(prefix):
            source = source[len(prefix):]
        return (typ, source, target)
    return (typ, source.rstrip("/"), target)


def to_tup(vol: object, project: str) -> tuple[str, str, str]:
    """Convert one resolved-compose volume entry into a comparable tuple."""
    if isinstance(vol, str):
        parts = vol.split(":")
        typ, src = "bind", parts[0]
        dst = parts[1] if len(parts) > 1 else ""
    else:
        typ = vol.get("type", "bind")
        src = vol.get("source", "")
        dst = vol.get("target", "")
    return normalize(typ, src, dst, project)


def main() -> int:
    cfg_proc = compose(["config", "--format", "json"])
    if cfg_proc.returncode != 0:
        print("CHECK FAILED: `docker compose config` errored:")
        print(cfg_proc.stderr.strip().splitlines()[-1] if cfg_proc.stderr.strip() else "  docker unavailable?")
        return 1

    cfg = json.loads(cfg_proc.stdout)
    services = cfg["services"]
    project = cfg.get("name", "thebearcave")

    ps_proc = compose(["ps", "--format", "json"])
    names = {}
    if ps_proc.returncode == 0:
        names = {
            p.get("Service"): p.get("Name")
            for p in (json.loads(line) for line in ps_proc.stdout.splitlines() if line.strip())
        }

    diverged: list[str] = []
    for svc, sconf in services.items():
        expected = [to_tup(v, project) for v in sconf.get("volumes", [])]
        name = names.get(svc)
        if not name:
            print(f"  [not-running] {svc} (no running container to compare)")
            continue

        insp_proc = run(["docker", "inspect", name])
        if insp_proc.returncode != 0:
            print(f"  [inspect-error] {svc} ({name})")
            diverged.append(svc)
            continue
        actual = []
        for m in json.loads(insp_proc.stdout)[0].get("Mounts", []):
            typ = m.get("Type")
            src = m.get("Name", "") if typ == "volume" else m.get("Source", "")
            actual.append(normalize(typ, src, m.get("Destination", ""), project))

        # Index by target so duplicate targets and ordering don't confuse.
        exp_by_target: dict[str, list] = {}
        for tup in expected:
            exp_by_target.setdefault(tup[2], []).append(tup)
        act_by_target: dict[str, list] = {}
        for tup in actual:
            act_by_target.setdefault(tup[2], []).append(tup)

        missing = [t for t in exp_by_target.keys() if t not in act_by_target]
        extra = [t for t in act_by_target.keys() if t not in exp_by_target]
        mismatched = [
            (t, exp_by_target[t], act_by_target[t])
            for t in exp_by_target.keys() & act_by_target.keys()
            if exp_by_target[t] != act_by_target[t]
        ]
        if not (missing or extra or mismatched):
            continue

        diverged.append(svc)
        print(f"\n=== DIVERGENCE: {svc} ({name}) ===")
        for target in missing:
            for typ, src, dst in exp_by_target[target]:
                print(f"  MISSING expected mount     : {typ} {src} -> {dst}")
        for target in extra:
            for typ, src, dst in act_by_target[target]:
                print(f"  EXTRA undeclared mount     : {typ} {src} -> {dst}")
        for target, exp, act in mismatched:
            print(f"  MISMATCH on {target:<20}: compose={exp} container={act}")

    print()
    if diverged:
        print(f"CHECK FAILED: {len(diverged)} container(s) diverge from compose: {', '.join(diverged)}")
        print("Fix: docker compose up -d --force-recreate <service> (split any merged mounts first).")
        return 1

    print(f"OK: all {len(names)} running container(s) match their compose mounts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())