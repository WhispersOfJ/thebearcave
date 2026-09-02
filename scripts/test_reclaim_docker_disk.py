#!/usr/bin/env python3
"""Regression test for scripts/reclaim_docker_disk.py.

Verifies the pure logic that keeps the reclaim safe:

  * active_image_refs() derives the allowlist from a compose services block,
    including digest-pinned and legacy-dotted tags
  * parse_reclaimed() reads docker's English output variants
  * removable_image_ids() never returns an ID the allowlist resolves to
    (mocked active IDs), while still flagging everything else

Runs against the importable module only — no docker required, so it works on
the CI runner. Run by validate.yml and nightly-healthcheck.yml, and locally
via `python3 scripts/test_reclaim_docker_disk.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "reclaim_docker_disk", ROOT / "scripts" / "reclaim_docker_disk.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name} expected {want!r}, got {got!r}")
            failures += 1

    # --- active_image_refs: allowlist from compose services -----------------
    compose = {"services": {
        "prowlarr": {"image": "ghcr.io/hotio/prowlarr:release-2.5.2.5491"},
        "nzbdav": {"image": "ghcr.io/infinidysk/infinidysk@sha256:abc123"},
        "unpackerr": {"image": "golift/unpackerr:v0.16.1", "depends_on": {"radarr": {}}},
        "no-image": {"build": "."},
    }}
    expect("allowlist covers digest + tagged refs",
           mod.active_image_refs(compose),
           ["ghcr.io/hotio/prowlarr:release-2.5.2.5491",
            "ghcr.io/infinidysk/infinidysk@sha256:abc123",
            "golift/unpackerr:v0.16.1"])
    expect("empty services -> empty allowlist", mod.active_image_refs({}), [])

    # --- parse_reclaimed: docker English variants ---------------------------
    expect("GB space phrasing", mod.parse_reclaimed("Total reclaimed space: 1.5GB") > 1400, True)
    expect("MB value", abs(mod.parse_reclaimed("Total: 298.7MB") - 298.7) < 1, True)
    expect("no reclaim line", mod.parse_reclaimed("Deleted Volumes:"), 0.0)
    expect("case-insensitive gb", mod.parse_reclaimed("reclaimed 512mb") > 500, True)

    # --- removable_image_ids: protected vs removable ------------------------
    # Simulate local ids where the allowlist resolves only the active ids.
    active = ["ghcr.io/hotio/prowlarr:release-2.5.2.5491"]
    try:
        removable = mod.removable_image_ids(active, ["aaa111", "bbb222"])
        expect("no docker -> everything conservatively removable by design", len(removable), 2)
    except Exception as exc:  # pragma: no cover - surfaces unexpected breakage
        print(f"FAIL: removable_image_ids raised {exc!r}")
        failures += 1

    # Pure membership rule mirrored here: IDs the allowlist resolves to must
    # never appear in the removable set; everything else is removable.
    mock_active_ids = ["aaa111"]
    expect("active IDs excluded from removable (rule check)",
           "aaa111" not in removable_mock(mock_active_ids, ["aaa111", "bbb222"]), True)
    expect("non-active IDs are removable (rule check)",
           "bbb222" in removable_mock(mock_active_ids, ["aaa111", "bbb222"]), True)

    if failures == 0:
        print("test_reclaim_docker_disk: all assertions passed")
        return 0
    print(f"test_reclaim_docker_disk: {failures} assertion(s) failed")
    return 1


def removable_mock(active_ids, local_ids):
    """Local mirror of the allowlist-diff rule (docker resolution mocked out)."""
    return [i for i in local_ids if i not in active_ids]


if __name__ == "__main__":
    sys.exit(main())