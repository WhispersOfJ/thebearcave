#!/usr/bin/env python3
"""Fail when a Grafana dashboard JSON is malformed, envelope-wrapped, or
references an undeclared datasource variable.

Grafana file provisioning expects the dashboard *model* at the top level of
each JSON file in the provisioning directory: title, panels, uid, and so on.
The Grafana HTTP API returns a different shape — {"dashboard": {...},
"meta": {...}} — and a file saved from that response loads as a dashboard with
an empty title, which the provisioning provider rejects with "Dashboard title
cannot be empty" on every rescan (the stage-4-cve-tracking incident).

Datasource variables: panels reference the provisioned Prometheus through
${DS_PROMETHEUS}. Grafana only auto-creates DS_* variables for dashboards
saved through the UI/API — a file-provisioned dashboard that uses ${DS_...}
without declaring it in "templating" fails every panel with "Datasource
${DS_...} was not found" (the stack-command-center incident).

This check validates every JSON file in config/grafana/dashboards/:

  * parses as JSON,
  * is an object (not an array/string),
  * has a non-empty string "title",
  * has a "panels" (or legacy "rows") key,
  * is NOT wrapped in the API envelope (no top-level "dashboard"/"meta"),
  * declares every ${DS_...} it references in "templating".

Run by scripts/preflight.sh and .github/workflows/config-check.yml.

Usage:
  python3 scripts/check_grafana_dashboards.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "config" / "grafana" / "dashboards"

# ${DS_PROMETHEUS} and friends anywhere in the model (panel datasource uids,
# annotation datasource refs, variable definitions, …). The negative lookbehind
# skips Grafana's $$ escape ($${DS_...} renders as a literal ${DS_...} string,
# not a datasource reference).
DS_VAR_RE = re.compile(r"(?<!\$)\$\{(DS_[A-Z0-9_]+)\}")


def check_dashboard(path: Path) -> list[str]:
    """Return a list of problem strings for one dashboard file (empty = OK)."""
    problems: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON ({exc})"]

    if not isinstance(data, dict):
        return [f"{path.name}: top level is {type(data).__name__}, expected a JSON object"]

    if isinstance(data.get("dashboard"), dict):
        problems.append(
            f'{path.name}: wrapped in the Grafana API envelope (top-level "dashboard" key) — '
            "unwrap to the dashboard model"
        )
    if "meta" in data:
        problems.append(
            f'{path.name}: wrapped in the Grafana API envelope (top-level "meta" key) — '
            "unwrap to the dashboard model"
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append(f'{path.name}: missing or empty "title"')

    if "panels" not in data and "rows" not in data:
        problems.append(
            f'{path.name}: missing "panels" (or legacy "rows") — not a dashboard model'
        )

    referenced = set(DS_VAR_RE.findall(json.dumps(data)))
    # templating may be null/absent or list may be null on hand-edited dashboards
    # — treat both as "no variables declared" instead of crashing.
    templating = data.get("templating") or {}
    declared = {
        var.get("name") for var in (templating.get("list") or []) if isinstance(var, dict)
    }
    for var in sorted(referenced - declared):
        problems.append(
            f'{path.name}: references ${{{var}}} but does not declare it in '
            '"templating" (Grafana only auto-creates DS_* variables for '
            "UI-saved dashboards — add a datasource variable named "
            f"{var} to templating.list)"
        )

    return problems


def main() -> int:
    if not DASHBOARD_DIR.exists():
        print(f"OK: {DASHBOARD_DIR} not present (nothing to check).")
        return 0

    files = sorted(DASHBOARD_DIR.glob("*.json"))
    if not files:
        print(f"OK: no dashboard JSON files in {DASHBOARD_DIR.name}.")
        return 0

    problems: list[str] = []
    for path in files:
        problems.extend(check_dashboard(path))

    if not problems:
        print(
            f"OK: all {len(files)} Grafana dashboard(s) are valid dashboard models "
            "(title + panels present, no API envelope, datasource variables declared)."
        )
        return 0

    print(f"CHECK FAILED: {len(problems)} problem(s) in {DASHBOARD_DIR.name}/:")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
