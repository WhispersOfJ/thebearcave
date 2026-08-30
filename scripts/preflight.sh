#!/usr/bin/env bash
# One-command pre-push validation gate.
#
# Runs the same checks CI's validate job runs locally so problems are caught
# before the push instead of in a red GitHub Actions run:
#
#   1. ruff          — Python lint (CI-identical: ruff check . --exclude archive/ --exclude "**/migrations")
#   2. py_compile    — all scripts/*.py compile
#   3. actionlint    — every workflow in .github/workflows/
#   4. compose       — docker compose config --quiet
#   5. compose mounts — scripts/check_compose_mounts.py (no merged mount lines)
#   6. mount drift    — scripts/check_mount_drift.py (live mounts == compose def)
#   7. MCP baseline  — scripts/check_mcp.py --baseline (0 divergences vs .github/mcp-baseline.json)
#   8. grafana dashboards — scripts/check_grafana_dashboards.py (valid, un-wrapped dashboard JSON)
#
# Every check runs even if an earlier one fails, so one invocation reports
# everything that is broken. Exit 0 = all pass, 1 = any failure.
#
# If a tool is missing (actionlint is not on PATH by default; this repo's
# pinned build is often downloaded to /tmp/actionlint), the script warns and
# skips that check — CI still gates it. Override the actionlint path with
# ACTIONLINT=/path/to/actionlint.
#
# Usage:
#   scripts/preflight.sh

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

failures=0
warnings=0

check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  PASS  $name"
  else
    echo "  FAIL  $name"
    failures=$((failures + 1))
  fi
}

warn_skip() {
  echo "  SKIP  $1 (tool not found: $2)"
  warnings=$((warnings + 1))
}

echo "== pre-push validation ($(basename "$ROOT")) =="

# 1. Ruff (Python lint) — CI-identical invocation
if command -v ruff >/dev/null 2>&1; then
  check "ruff" ruff check . --exclude archive/ --exclude "**/migrations"
else
  warn_skip "ruff" "ruff"
fi

# 2. py_compile — every script compiles
check "py_compile" python3 -m py_compile scripts/*.py

# 3. Actionlint — workflow lint (resolve: ACTIONLINT env, PATH, /tmp fallback)
AL="${ACTIONLINT:-}"
if [ -z "$AL" ] && command -v actionlint >/dev/null 2>&1; then
  AL="$(command -v actionlint)"
fi
if [ -z "$AL" ] && [ -x /tmp/actionlint ]; then
  AL=/tmp/actionlint
fi
if [ -n "$AL" ]; then
  check "actionlint" "$AL" .github/workflows/*.yml
else
  warn_skip "actionlint" "actionlint (set ACTIONLINT=/path/to/actionlint)"
fi

# 4. Compose config — the stack must be coherent
if command -v docker >/dev/null 2>&1; then
  check "compose config" docker compose config --quiet
else
  warn_skip "compose config" "docker"
fi

# 5. Compose mounts — no volume/port/env entries merged onto one line
check "compose mounts" python3 scripts/check_compose_mounts.py

# 6. Mount drift — every running container's mounts match the compose definition
if command -v docker >/dev/null 2>&1; then
  check "mount drift" python3 scripts/check_mount_drift.py
else
  warn_skip "mount drift" "docker"
fi

# 7. MCP baseline — probe against .github/mcp-baseline.json
check "mcp baseline" python3 scripts/check_mcp.py --baseline

# 8. Grafana dashboards — every tracked dashboard JSON is a valid, un-wrapped model
check "grafana dashboards" python3 scripts/check_grafana_dashboards.py

echo
if [ "$failures" -eq 0 ] && [ "$warnings" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
elif [ "$failures" -eq 0 ]; then
  echo "ALL CHECKS PASSED ($warnings skipped: missing local tool, CI still gates)"
else
  echo "$failures check(s) FAILED, $warnings skipped"
fi
exit "$([ "$failures" -eq 0 ] && echo 0 || echo 1)"
