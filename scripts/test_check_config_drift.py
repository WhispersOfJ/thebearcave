#!/usr/bin/env python3
"""Regression test for scripts/check_config_drift.py.

Verifies the running-image-vs-compose-pin guard cannot silently bit-rot:

  * the two 2026-09-02 manual finds are reproduced as fixtures (unpackerr
    running 0.15.2 vs pinned v0.16.1; plex on an older digest than the
    @sha256 pin)
  * a clean stack (all pins satisfied) reports no drift
  * digest-only-vs-mutable-tag semantics are pinned exactly
  * normalization (tags, latest-default, registry ports, case) is stable

Runs against the importable pure logic with no docker and no live stack,
so it works on the CI runner. Run by validate.yml and
nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_config_drift.py`. Exits 0 when every assertion
holds, 1 otherwise.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_config_drift.py"

spec = importlib.util.spec_from_file_location("check_config_drift", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = 0


def expect(name, got, want):
    global failures
    if got == want:
        print(f"OK: {name}")
    else:
        print(f"FAIL: {name} expected {want!r}, got {got!r}")
        failures += 1


def drift_names(pins, running):
    return sorted(d["service"] for d in mod.check_drift(pins, running))


# --- normalization -------------------------------------------------------

expect("digest split", mod.split_ref("repo/app:v1@sha256:" + "a" * 64),
       ("repo/app:v1", "sha256:" + "a" * 64))
expect("no digest", mod.split_ref("Repo/App:v1"),
       ("repo/app:v1", None))
expect("default latest (no tag)", mod.norm_ref("ghcr.io/hotio/radarr"),
       ("ghcr.io/hotio/radarr", "latest", None))
expect("default latest (explicit)", mod.norm_ref("golift/unpackerr:latest"),
       ("golift/unpackerr", "latest", None))
expect("hyphenated repo (explicit / image)", mod.norm_ref("rclone/rclone:1.75.0"),
       ("rclone/rclone", "1.75.0", None))
expect("registry port not a tag", mod.norm_ref("localhost:5000/app"),
       ("localhost:5000/app", "latest", None))
expect("digest ref keeps tag and digest",
       mod.norm_ref("plexinc/pms-docker@sha256:" + "b" * 64),
       ("plexinc/pms-docker", "latest", "sha256:" + "b" * 64))
expect("case-folded", mod.norm_ref("GHCR.IO/Hotio/Radarr:Release-6.3.0.10514"),
       ("ghcr.io/hotio/radarr", "release-6.3.0.10514", None))

# --- comparison semantics ------------------------------------------------

PLEX_PIN = "plexinc/pms-docker@sha256:" + "9" * 64
PLEX_OLD = "plexinc/pms-docker@sha256:" + "8" * 64

# the two 2026-09-02 manual finds
expect("unpackerr tag drift (0.15.2 vs pinned v0.16.1)",
       drift_names({"unpackerr": "golift/unpackerr:v0.16.1"},
                   {"unpackerr": "golift/unpackerr:0.15.2"}),
       ["unpackerr"])
expect("plex digest drift (running older digest)",
       drift_names({"plex": PLEX_PIN}, {"plex": PLEX_OLD}),
       ["plex"])

# clean cases
expect("clean stack: no drift", drift_names(
    {
        "radarr": "ghcr.io/hotio/radarr:release-6.3.0.10514",
        "plex": PLEX_PIN,
        "unpackerr": "golift/unpackerr:v0.16.1",
    },
    {
        "radarr": "ghcr.io/hotio/radarr:release-6.3.0.10514",
        "plex": PLEX_PIN,
        "unpackerr": "golift/unpackerr:v0.16.1",
    }), [])
expect("pin satisfied despite running digest (tag pin)",
       drift_names({"unpackerr": "golift/unpackerr:v0.16.1"},
                   {"unpackerr": "golift/unpackerr:v0.16.1@sha256:" + "c" * 64}),
       [])
expect("latest vs explicit latest equal",
       drift_names({"seerr": "ghcr.io/seerr-team/seerr:latest"},
                   {"seerr": "ghcr.io/seerr-team/seerr"}), [])

# digest-pin discipline
expect("digest pin NOT satisfied by mutable-tag running ref",
       drift_names({"plex": PLEX_PIN}, {"plex": "plexinc/pms-docker:latest"}),
       ["plex"])
expect("digest mismatch wrong digest",
       drift_names({"nzbdav": "ghcr.io/infinidysk/infinidysk@sha256:" + "d" * 64},
                   {"nzbdav": "ghcr.io/infinidysk/infinidysk@sha256:" + "e" * 64}),
       ["nzbdav"])
expect("name/tag mismatch",
       drift_names({"sonarr": "ghcr.io/hotio/sonarr:release-4.0.19.2979"},
                   {"sonarr": "ghcr.io/hotio/sonarr:release-3.0.0.0"}),
       ["sonarr"])

# --- set semantics -------------------------------------------------------

expect("not-running services are not drift",
       drift_names({"plex": PLEX_PIN, "radarr": "ghcr.io/hotio/radarr:x"},
                   {"radarr": "ghcr.io/hotio/radarr:x"}),
       [])
expect("unmanaged running containers are ignored (no pin)",
       drift_names({"radarr": "ghcr.io/hotio/radarr:x"},
                   {"radarr": "ghcr.io/hotio/radarr:x",
                    "portainer": "portainer/portainer:latest"}),
       [])
expect("partial stack drift names only the drifted service",
       drift_names({"radarr": "ghcr.io/hotio/radarr:x",
                    "sonarr": "ghcr.io/hotio/sonarr:y",
                    "unpackerr": "golift/unpackerr:v0.16.1"},
                   {"radarr": "ghcr.io/hotio/radarr:x",
                    "sonarr": "ghcr.io/hotio/sonarr:OLD",
                    "unpackerr": "golift/unpackerr:v0.16.1"}),
       ["sonarr"])

# --- main() drift path end-to-end (faked docker) ------------------------
#
# The pure fixtures never execute main()'s drift branch; this one does, with
# canned docker output, so the report + recreate-hint rendering cannot rot.

def fake_docker(cmd, timeout=None):
    class P:
        returncode = 0
        stdout = ""
        stderr = ""
    if cmd[:2] == ["docker", "compose"]:
        P.stdout = json.dumps({
            "name": "thebearcave",
            "services": {
                "radarr": {"image": "ghcr.io/hotio/radarr:release-x"},
                "unpackerr": {"image": "golift/unpackerr:v0.16.1"},
            },
        })
    elif cmd[:2] == ["docker", "ps"]:
        P.stdout = "\n".join([
            json.dumps({"Labels": "com.docker.compose.service=radarr",
                        "Names": "radarr"}),
            json.dumps({"Labels": "com.docker.compose.service=unpackerr",
                        "Names": "unpackerr"}),
        ])
    elif cmd[:2] == ["docker", "inspect"]:
        P.stdout = json.dumps([
            {"Name": "/radarr",
             "Config": {"Image": "ghcr.io/hotio/radarr:release-x"}},
            {"Name": "/unpackerr",
             "Config": {"Image": "golift/unpackerr:0.15.2"}},
        ])
    return P

orig_run = mod.run
mod.run = fake_docker
try:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main([])
    text = buf.getvalue()
finally:
    mod.run = orig_run

expect("main() drift path exits 1", rc, 1)
expect("main() names the drifted service", "[drift] unpackerr" in text, True)
expect("main() prints the recreate hint",
       "hint: apply the pins with: docker compose up -d --no-deps unpackerr"
       in text, True)

# --- recreate-reminder hint ---------------------------------------------

expect("hint lists services sorted + pin date",
       mod.hint_for(["unpackerr", "plex"], "2026-08-31"),
       "hint: apply the pins with: docker compose up -d --no-deps "
       "plex unpackerr (pins last changed 2026-08-31)")
expect("hint without a pin date",
       mod.hint_for(["plex"], None),
       "hint: apply the pins with: docker compose up -d --no-deps plex")
expect("empty drift list stays valid",
       mod.hint_for([], None),
       "hint: apply the pins with: docker compose up -d --no-deps ")

# pin_changed_on against this repo's own history: the unpackerr v0.16.1
# pin entered docker-compose.yml on 2026-08-31 (dependabot) — the exact
# 2026-09-02 drift class this hint exists for. A shallow clone (CI default
# without the fetch-depth: 0 override in validate.yml/nightly-healthcheck)
# must degrade to None instead of misattributing the pin to today.
shallow_proc = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                              capture_output=True, text=True, cwd=str(ROOT))
if shallow_proc.returncode == 0 and shallow_proc.stdout.strip() == "true":
    expect("pin_changed_on degrades to None in a shallow checkout",
           mod.pin_changed_on(ROOT, "golift/unpackerr:v0.16.1"), None)
else:
    expect("pin_changed_on finds the dependabot bump date",
           mod.pin_changed_on(ROOT, "golift/unpackerr:v0.16.1"), "2026-08-31")
expect("pin_changed_on returns None for unknown strings",
       mod.pin_changed_on(ROOT, "nonexistent/registry/never:pinned"), None)

if failures == 0:
    print("test_check_config_drift: all assertions passed")
    sys.exit(0)
print(f"test_check_config_drift: {failures} assertion(s) failed")
sys.exit(1)
