#!/usr/bin/env python3
"""Verify each running container's mounts match its compose definition and
that FUSE-backed mounts are not holding stale handles.

`docker compose config --quiet` validates that the compose file is coherent,
but it cannot see what a *running* container was actually created with. A
container can sit on stale mounts — a mount removed or repointed in compose but
never recreated, or a bind mount resolved against a dead FUSE instance — while
the compose file looks fine. This is exactly how plex lost its /data/shows
mount in the anime-consolidation incident.

Two failure modes are checked:

  1. Drift — compare every running container's actual mounts (`docker inspect`)
     against the resolved compose definition (`docker compose config --format
     json`). A container is flagged when a mount is missing, present-but-
     undeclared, or resolved to a different source/target. Two benign
     differences are normalized away so they don't false-positive:

       * named volumes: Docker prepends the project name (`thebearcave_voldata`
         <=> declared `voldata`)
       * bind sources: Docker strips a trailing slash (`/dev/disk/` <=>
         `/dev/disk`)

  2. Stale FUSE handles — a container can hold a bind mount into an old, dead
     FUSE instance after the mount owner (nzbdav_rclone) was recreated without
     a cascade restart. The mounts match compose and the files look present,
     but reads fail with "Transport endpoint is not connected". For every
     running container that mounts the FUSE tree (/mnt/remote[/nzbdav]) this
     check runs `stat -L` on the mountpoint *inside the container* (stat, not
     ls — directory listings can succeed via cached dentries) and flags any
     ENOTCONN-class error. Fix is a plain `docker compose restart <service>`.

Run by scripts/preflight.sh (docker-gated) and locally via
`python3 scripts/check_mount_drift.py`. Exit 0 = every running container
matches its compose definition and no stale FUSE handle was found; 1 = a
divergence, a stale handle, or docker unavailable.

Usage:
  python3 scripts/check_mount_drift.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# FUSE-backed bind sources and the mountpoint inside them that must answer.
FUSE_MOUNTS = {
    "/mnt/remote/nzbdav": "",        # target itself is the FUSE mountpoint
    "/mnt/remote": "/nzbdav",        # FUSE mountpoint lives under the target
}
# Kernel errors when a FUSE transport is dead (see the fuse-mount-cascade-
# restart-diagnosis skill: ENOTCONN / "Transport endpoint is not connected").
STALE_SIGNATURES = (
    "transport endpoint is not connected",
    "socket not connected",
    "enotconn",
    "stale file handle",
)

PROBE_TIMEOUT = 10


def run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


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


def probe_stale(name: str, target: str) -> str | None:
    """Return an error string when <name>'s handle on <target> is stale.

    Runs `stat -L` inside the container (not ls — cached dentries can mask a
    dead transport). Returns None when the handle is healthy, stat is missing
    from the image, or the probe is inconclusive (timeout); otherwise the
    kernel error text.
    """
    try:
        proc = run(["docker", "exec", name, "stat", "-L", target], timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode == 0:
        return None
    out = (proc.stdout + proc.stderr).lower()
    if any(sig in out for sig in STALE_SIGNATURES):
        text = (proc.stderr.strip() or proc.stdout.strip()).splitlines()[-1]
        return text[:160]
    return None


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
    stale: list[tuple[str, str, str]] = []  # (service, probe_path, error)
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
        raw_mounts = json.loads(insp_proc.stdout)[0].get("Mounts", [])

        # --- drift: declared vs actual mount sets ---------------------------
        actual = []
        for m in raw_mounts:
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
        if missing or extra or mismatched:
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

        # --- stale-handle probe: FUSE mountpoints must answer stat ----------
        for m in raw_mounts:
            if m.get("Type") != "bind":
                continue
            src = (m.get("Source", "") or "").rstrip("/")
            suffix = FUSE_MOUNTS.get(src)
            if suffix is None:
                continue
            target = m.get("Destination", "") + suffix
            error = probe_stale(name, target)
            if error:
                stale.append((svc, target, error))

    print()
    if stale:
        for svc, path, error in stale:
            print(f"=== STALE HANDLE: {svc} ({path}) ===")
            print(f"  {error}")
            print("  Fix: docker compose restart <service> (re-establishes the bind/FUSE handle).")
        print()
    if diverged or stale:
        problems = []
        if diverged:
            problems.append(f"{len(diverged)} mount divergence(s): {', '.join(diverged)}")
        if stale:
            problems.append(f"{len(stale)} stale FUSE handle(s): {', '.join(s for s, _, _ in stale)}")
        print(f"CHECK FAILED: {'; '.join(problems)}")
        print("Drift fix: docker compose up -d --force-recreate <service> (split any merged mounts first).")
        return 1

    print(f"OK: all {len(names)} running container(s) match their compose mounts; no stale FUSE handles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())