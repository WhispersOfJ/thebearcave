#!/usr/bin/env python3
"""Check that GitHub Actions secret usage stays in sync with the manifest.

Run by .github/workflows/secret-guard.yml on every push/PR. Exits non-zero
(fails CI) when:

  1. A workflow references secrets.<NAME> that is not declared in
     .github/required-secrets.json (the manifest is the source of truth for
     which secrets workflows may use).
  2. A declared secret maps to an env_var that is missing from
     .env.template (so operators know what to put in .env, and
     scripts/setup.sh knows what to sync).

Warns (but does not fail) when a declared secret is never referenced by any
workflow — a dead manifest entry that should be cleaned up.

Usage:
  python3 scripts/check_secret_manifest.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
MANIFEST_PATH = ROOT / ".github" / "required-secrets.json"
ENV_TEMPLATE_PATH = ROOT / ".env.template"

# GitHub secrets are only referenced inside expressions (${{ secrets.NAME }});
# anchoring on the expression avoids matching plain text like "required-secrets.json".
SECRET_RE = re.compile(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)")


def collect_used_secrets() -> dict[str, list[str]]:
    """Map every referenced secret name to the workflows using it."""
    used: dict[str, list[str]] = {}
    if not WORKFLOWS_DIR.is_dir():
        return used
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for match in SECRET_RE.finditer(wf.read_text()):
            used.setdefault(match.group(1), []).append(wf.name)
    return used


def collect_env_template_vars() -> set[str]:
    """Return the set of variable names declared in .env.template."""
    if not ENV_TEMPLATE_PATH.exists():
        return set()
    vars_found: set[str] = set()
    for line in ENV_TEMPLATE_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            vars_found.add(line.split("=", 1)[0])
    return vars_found


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"[error] manifest not found: {MANIFEST_PATH}")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text())
    declared = {entry["name"]: entry for entry in manifest["secrets"]}
    used = collect_used_secrets()
    env_vars = collect_env_template_vars()

    errors: list[str] = []

    # Rule 1: every referenced secret must be declared.
    for name in sorted(used):
        if name not in declared:
            where = ", ".join(used[name])
            errors.append(
                f"secrets.{name} is referenced by {where} but is not declared "
                f"in .github/required-secrets.json"
            )

    # Rule 2: declared env_vars must exist in .env.template.
    for name, entry in sorted(declared.items()):
        env_var = entry.get("env_var")
        if env_var and env_var not in env_vars:
            errors.append(
                f"manifest secret {name} maps to env_var {env_var}, which is "
                f"missing from .env.template"
            )

    # Warnings: declared but never used.
    for name in sorted(declared):
        if name not in used:
            print(f"  [warn] secrets.{name} is declared but never referenced by any workflow")

    if errors:
        print(f"{len(errors)} secret manifest error(s):")
        for error in errors:
            print(f"  [error] {error}")
        return 1

    print(
        f"OK: {len(declared)} declared secret(s), {len(used)} referenced "
        f"by workflows, all in sync with .env.template."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
