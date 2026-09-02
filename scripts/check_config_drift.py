#!/usr/bin/env python3
"""Check that every running stack container's image matches its compose pin.

docker compose config --quiet validates that the compose file is coherent,
but it cannot see what a *running* container was actually created from. A
container keeps running its original image after the compose pin changes —
a tag bump, a digest repin, a registry move — until someone recreates it.
Both found by hand on 2026-09-02:

  * unpackerr running 0.15.2 while compose pins v0.16.1
  * plex on an older digest than compose's @sha256 pin

This is the mechanical version: compose config is the source of truth for
the pins; `docker inspect`'s Config.Image says what each running container
was created from. (Not `docker ps`'s Image field — it collapses digest
refs to short IDs like 8cf616c1806c, which makes nothing comparable.)

Running containers are matched to services by their
`com.docker.compose.service` container label, never by compose project-name
derivation: the project name falls out of the compose file's directory, so
running this from a task worktree would otherwise address a project with no
containers and report a vacuous OK. Containers without that service label
(docker run by hand, unrelated tools) are invisible to the check.

Comparison semantics:

  * both refs carry a digest  — equal iff both name+tag AND digest match
  * only the PIN has a digest — the running container satisfies the pin
    only if its name+tag match AND it was itself created from that exact
    digest; a digest pin with no digest on the running ref is drift (the
    mutable-tag case — the digest pin exists precisely to exclude it)
  * only the RUNNING ref has a digest — created from a tag pin is a match
    when name+tag agree (the digest was the tag's value at creation; pull
    currency is not this check's job)
  * neither                   — plain name:tag comparison

A drift report ends with a recreate-reminder line: the command to apply the
pins plus the oldest date the drifted pins entered the compose file (`git
log -S`) — dependabot re-pins the docker images weekly and merging never
recreates containers, so pinned-but-never-recreated services are the
expected drift class (2026-08-31: unpackerr 0.15.2/v0.16.1 and the plex
digest bump, both found drifting on 2026-09-02).

Name normalization: case-folded; a missing tag defaults to `latest` (what
the registries resolve it to anyway). Tag parsing is slash-aware so a
registry port (`localhost:5000/app`) is not mistaken for a tag.

Services from compose that are not running are noted, not flagged — drift
is about running state vs the pin, and the recreate guard is the digest's
job. Containers running that no compose service pins are out of scope
(non-stack tools; this check owns the compose project).

Run by scripts/preflight.sh (docker-gated), the maintenance digest
(scripts/maintenance_digest.py, rc-2 soft semantics) and locally via
`python3 scripts/check_config_drift.py`. Exit 0 = every running compose
service matches its pin (or nothing is running); 1 = drift; 2 = cannot
assess (docker/compose unavailable) — the check_* family's soft-exit,
which the digest reads as a WARN rather than a FAIL.

Usage:
  python3 scripts/check_config_drift.py            # live docker
  python3 scripts/check_config_drift.py --offline  # CI/no-docker: print OK
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST_RE = re.compile(r"^(?P<name>.+)@(?P<digest>sha256:[0-9a-f]{64})$")


def split_ref(ref: str) -> tuple[str, str | None]:
    """(name-with[-or-without]-tag, digest-or-None) for one image ref.

    Lower-cases and strips whitespace (image names are case-insensitive).
    """
    ref = ref.strip().lower()
    m = DIGEST_RE.match(ref)
    if m:
        return m.group("name"), m.group("digest")
    return ref, None


def norm_ref(ref: str) -> tuple[str, str, str | None]:
    """Normalize one ref into (repository, tag, digest) — comparable.

    Defaults a missing tag to `latest`. The tag separator is the last
    colon *after* the last slash, so `localhost:5000/app` (registry port)
    is parsed as repository + no tag, while `repo/app:v1` gets tag `v1`.
    """
    name, digest = split_ref(ref)
    slash = name.rfind("/")
    colon = name.rfind(":")
    if colon != -1 and colon > slash:
        repo, tag = name[:colon], name[colon + 1:]
    else:
        repo, tag = name, "latest"
    return repo, tag, digest


def images_match(pinned: str, running: str) -> tuple[bool, str]:
    """True when the running ref satisfies the compose pin; else (False, why).

    ``why`` names the aspect that drifted (tag/digest/pin-not-satisfied).
    """
    pr, pt, pd = norm_ref(pinned)
    rr, rt, rd = norm_ref(running)

    if pr != rr or pt != rt:
        return False, "name/tag"
    if pd is not None:
        if rd is None:
            return False, "digest pin not satisfied (running ref has no digest)"
        if pd != rd:
            return False, "digest"
    return True, ""


def check_drift(pins: dict[str, str],
                running: dict[str, str]) -> list[dict[str, str]]:
    """Compare compose pins (service -> image) against running containers'
    creation refs (service -> Config.Image). Returns drift findings.

    Pure and fixture-testable: no docker involved (the CLI layer does the
    live fetching). ``running`` maps compose service names to container
    image refs; a service absent from ``running`` is not running.
    """
    drift: list[dict[str, str]] = []
    for svc, pinned in pins.items():
        image = running.get(svc)
        if image is None:
            continue  # not running — informational, not drift
        ok, why = images_match(pinned, image)
        if not ok:
            drift.append({
                "service": svc,
                "pinned": pinned,
                "running": image,
                "why": why,
            })
    return drift


def hint_for(drift_services: list[str], pin_changed: str | None) -> str:
    """The recreate-reminder line printed under a drift report.

    ``drift_services`` sorted; ``pin_changed`` is the oldest date the drifted
    pins entered the compose file (None when unknown) — the reminder then
    says how stale the mismatch is, e.g. dependabot bumped the pin Aug 31
    and nothing recreated the container since.
    """
    svc = " ".join(sorted(drift_services))
    base = f"hint: apply the pins with: docker compose up -d --no-deps {svc}"
    if pin_changed:
        base += f" (pins last changed {pin_changed})"
    return base


def pin_changed_on(repo: Path, image: str) -> str | None:
    """Oldest date a compose pin string entered the file (via git log -S).

    None when git is unavailable or the string is not in the file's history.
    Used to make a drift reminder actionable: dependabot bumped the pin on
    that date; the container has been stale since.
    """
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True, timeout=30,
                                 cwd=str(repo))
    except (OSError, subprocess.TimeoutExpired):
        shallow = None
    if shallow is not None and shallow.returncode == 0 \
            and shallow.stdout.strip() == "true":
        # A depth-1 clone (CI default, feature branches) cannot resolve the
        # introducing commit — git log -S would blame today's synthetic
        # merge ref for the pin. Report unknown rather than a wrong date.
        return None
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%ad", "--date=short", "-S", image, "--",
             "docker-compose.yml"],
            capture_output=True, text=True, timeout=30, cwd=str(repo))
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [line.strip() for line in proc.stdout.splitlines()
             if line.strip()]
    return lines[-1] if lines else None  # last line == earliest change


def run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def compose(args: list[str]) -> subprocess.CompletedProcess:
    return run(["docker", "compose", *args])


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--offline" in argv:
        print("OK (offline mode — live drift check skipped)")
        return 0

    cfg_proc = compose(["config", "--format", "json"])
    if cfg_proc.returncode != 0:
        print("CHECK SKIPPED: cannot assess container drift:")
        print(cfg_proc.stderr.strip().splitlines()[-1]
              if cfg_proc.stderr.strip() else "  docker unavailable?")
        return 2
    cfg = json.loads(cfg_proc.stdout)
    pins = {
        name: svc["image"] for name, svc in cfg["services"].items()
        if svc.get("image")
    }

    # Match running containers to services by their compose service label
    # (cwd-independent; see the module docstring for why this beats project
    # name derivation). docker ps's JSON gives Labels as a flat string.
    def labels(s: str) -> dict[str, str]:
        return dict(kv.split("=", 1) for kv in s.split(",") if "=" in kv)

    ps_proc = run(["docker", "ps", "--format", "json"])
    by_name: dict[str, str] = {}  # container name -> service
    if ps_proc.returncode == 0:
        for line in ps_proc.stdout.splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            svc = labels(c.get("Labels", "")).get("com.docker.compose.service")
            if svc in pins:
                by_name[c["Names"]] = svc

    # Batch one `docker inspect` for every matched running container; the
    # Config.Image field is the creation ref (docker ps truncates digests).
    # Containers are keyed by NAME, not ID: docker ps reports the 12-char
    # short ID while inspect carries the 64-char Id, so ID matching breaks.
    running: dict[str, str] = {}
    if by_name:
        insp_proc = run(["docker", "inspect", *by_name])
        if insp_proc.returncode == 0 and insp_proc.stdout.strip():
            for item in json.loads(insp_proc.stdout):
                svc = by_name.get(item.get("Name", "").lstrip("/"))
                if svc:
                    running[svc] = item.get("Config", {}).get("Image", "")

    for svc in pins:
        if svc not in by_name:
            print(f"  [not-running] {svc}")
    drift = check_drift(pins, running)

    if not drift:
        compared = len([s for s in pins if s in running])
        if compared == 0:
            print("OK: no running stack containers to compare (nothing drifted)")
        else:
            print(f"OK: {compared} running container(s) match their compose pins.")
        return 0

    print(f"CHECK FAILED: {len(drift)} running container(s) drifted from "
          f"their compose pin:")
    for d in drift:
        print(f"  [drift] {d['service']}: pinned {d['pinned']} != "
              f"running {d['running']} ({d['why']})")

    # Recreate-reminder: say what to run and how stale the pins are
    # (dependabot bumps the image pins weekly and nothing recreates the
    # containers — the 2026-08-31 unpackerr/plex drift class).
    dates = []
    for d in drift:
        when = pin_changed_on(ROOT, d["pinned"])
        if when:
            dates.append(when)
    oldest = min(dates) if dates else None
    print(hint_for([d["service"] for d in drift], oldest))
    return 1


if __name__ == "__main__":
    sys.exit(main())
