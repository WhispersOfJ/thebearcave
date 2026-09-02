#!/usr/bin/env python3
"""Reclaim Docker disk space: dangling volumes, dangling images, build cache,
stopped containers, and with --aggressive every image not referenced by
docker-compose.yml.

Why not just `docker volume prune`? Docker's prune silently skips labeled
compose volumes (2026-09-02: 9 volumes / 12.5 GiB left behind that
`docker volume ls -qf dangling=true` reported unused — explicit `docker
volume rm` worked where prune refused). This script removes exactly the
dangling set.

Why an allowlist for --aggressive? The same 2026-09-02 sweep found 60+
images (~30 GiB) outside the compose set — retired-stack history, tooling
pulls, experiment images — silently accumulated. Everything not referenced
by the active compose services is cache and re-pullable. The allowlist is
derived live from `docker compose config` (not hardcoded), so retiring or
adding a service never requires updating this script.

Docker operations are executed only when not --dry-run. Exits:
  0  reclaim completed (or nothing to do)
  1  a step failed / docker unavailable
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RECLAIM_RE = re.compile(r"(?:reclaimed\s+(?:space:\s+)?|Total:\s*)([0-9.]+[KMG]?B?)", re.I)
MB_RE = re.compile(r"([0-9.]+)([KMG]?)B?", re.I)
_UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}


def parse_reclaimed(text: str) -> float:
    """Extract the first reclaimed space figure as MiB from a docker output
    line set (e.g. 'Total reclaimed space: 1.5GB' or 'Total: 298.7MB')."""
    m = RECLAIM_RE.search(text)
    if not m:
        return 0.0
    n = MB_RE.match(m.group(1))
    if not n:
        return 0.0
    return float(n.group(1)) * _UNITS[n.group(2).upper()] / (1024**2)


def active_image_refs(compose: dict) -> list:
    """Image references from a parsed docker-compose services block."""
    refs = []
    for svc in (compose.get("services") or {}).values():
        img = svc.get("image")
        if img:
            refs.append(img)
    return sorted(refs)


def container_image_ids() -> set:
    """Short IDs of images backing any local container, whatever its state.

    Compose pins can drift ahead of what is actually running (e.g. a pinned
    image not yet pulled while the old tag still runs); this layer guarantees
    the image behind a live container is never reclaimable."""
    held = set()
    out = subprocess.run(["docker", "ps", "-aq"], capture_output=True,
                         text=True, timeout=30)
    for cid in out.stdout.split():
        r = subprocess.run(["docker", "inspect", "--format", "{{.Image}}", cid],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            held.add(r.stdout.strip().split(":")[-1][:12])
    return held


def removable_image_ids(active_refs: list, local_images: list) -> list:
    """Local image IDs neither referenced by a compose ref nor by any local
    container (short-ID normalized).

    Compose refs resolve one at a time: a ref with no local image (e.g. an
    upgrade pin not yet pulled) is skipped rather than failing the whole
    allowlist, so a missing image can never blank the protected set."""
    resolved = set()
    for ref in active_refs:
        out = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", ref],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            # Normalize to the 12-char short ID docker image ls reports.
            resolved.add(out.stdout.strip().split(":")[-1][:12])
    protected = resolved | container_image_ids()
    return sorted({i for i in local_images if i not in protected})


def docker(args: list, dry_run: bool, cwd=None, check=True) -> subprocess.CompletedProcess:
    """Run docker; print the command under --dry-run without executing."""
    if dry_run:
        print(f"  [dry-run] docker {' '.join(args)}")
        return subprocess.CompletedProcess(args, 0)
    return subprocess.run(["docker"] + args, capture_output=True, text=True,
                          timeout=300, cwd=cwd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be removed without touching anything")
    ap.add_argument("--aggressive", action="store_true",
                    help="also remove every image not referenced by docker-compose.yml")
    ap.add_argument("--keep-cache-gb", type=int, default=2,
                    help="build-cache storage to keep, GiB (default: %(default)s)")
    args = ap.parse_args()

    if not args.dry_run:
        probe = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                               capture_output=True, text=True, timeout=30)
        if probe.returncode != 0:
            print("docker is not available on this host; nothing reclaimed.")
            return 1

    total_mb = 0.0
    failures = 0

    def step(name: str, cmd: list, cwd=None):
        nonlocal total_mb, failures
        res = docker(cmd, args.dry_run, cwd=cwd)
        text = (res.stdout or "") + (res.stderr or "")
        rc = res.returncode
        if rc != 0:
            failures += 1
            print(f"  FAIL  {name} (exit {rc}): {text.strip()[:300]}")
        else:
            reclaimed = parse_reclaimed(text)
            total_mb += reclaimed
            print(f"  {name}: reclaimed {reclaimed:.1f} MiB"
                  + (" (dry-run)" if args.dry_run else ""))

    print("== Docker disk reclaim ==" + (" (dry run)" if args.dry_run else ""))

    # Dangling volumes — explicit rm works around docker prune's skip quirk.
    # The listing is read-only and reported identically in dry-run mode.
    vol_list = subprocess.run(
        ["docker", "volume", "ls", "-qf", "dangling=true"],
        capture_output=True, text=True, timeout=60).stdout.split()
    for v in vol_list:
        res = docker(["volume", "rm", v], args.dry_run)
        if res.returncode != 0:
            failures += 1
            print(f"  FAIL  volume rm {v}: {res.stderr.strip()[:200]}")
    if vol_list:
        print(f"  volumes: {len(vol_list)} dangling removed"
              + (" (dry-run)" if args.dry_run else ""))
    else:
        print("  volumes: none dangling")

    step("dangling images", ["image", "prune", "-f"])
    step("build cache", ["builder", "prune", "-f", "--keep-storage", f"{args.keep_cache_gb}G"])
    step("stopped containers", ["container", "prune", "-f"])

    if args.aggressive:
        # Fail closed: an unreadable compose config must never degenerate into
        # an empty allowlist (that would flag the running services' images).
        try:
            cfg = subprocess.run(
                ["docker", "compose", "config", "--format", "json"],
                capture_output=True, text=True, timeout=60, cwd=os.getcwd(),
            )
            compose = json.loads(cfg.stdout) if cfg.returncode == 0 else None
        except (ValueError, subprocess.SubprocessError):
            compose = None
        if compose is None:
            print("  FAIL  aggressive mode needs a readable docker-compose.yml + .env "
                  "(docker compose config failed); refusing image removal.")
            failures += 1
        else:
            active = active_image_refs(compose)
            local = subprocess.run(
                ["docker", "image", "ls", "--format", "{{.ID}}"],
                capture_output=True, text=True, timeout=60).stdout.split()
            removable = removable_image_ids(active, local)
            if removable:
                res = docker(["image", "rm", "-f"] + removable, args.dry_run)
                print(f"  non-compose images ({len(removable)}): "
                      + ("dry-run" if args.dry_run else "removed"))
                if res.returncode != 0:
                    failures += 1
                    print(f"    {res.stderr.strip()[:300]}")
            else:
                print("  non-compose images: none removable")

    print(f"\nTotal reclaimed: {total_mb:.0f} MiB")
    if not args.dry_run:
        df = subprocess.run(["docker", "system", "df"], capture_output=True,
                            text=True, timeout=60)
        print(df.stdout)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())