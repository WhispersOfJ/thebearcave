#!/usr/bin/env bash
# One-command pre-push validation gate for the eight-service stack.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# Guard scripts need the runtime key when preflight runs from a shell that has
# not exported the repository environment (for example a systemd timer or CI).
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

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

if command -v ruff >/dev/null 2>&1; then
  check "ruff" ruff check . --exclude archive/ --exclude "**/migrations"
else
  warn_skip "ruff" "ruff"
fi

check "py_compile" python3 -m py_compile scripts/*.py

if [ -e "$ROOT/.git" ]; then
  check "secret drift" python3 scripts/check_secret_drift.py
else
  warn_skip "secret drift" "no .git (not a git checkout)"
fi

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

if command -v docker >/dev/null 2>&1; then
  check "compose config" docker compose config --quiet
  check "mount drift" python3 scripts/check_mount_drift.py
else
  warn_skip "compose config" "docker"
  warn_skip "mount drift" "docker"
fi

if [ -f "$ROOT/config/radarr/radarr.db" ] || [ -n "${RADARR_DB:-}" ]; then
  check "radarr quality profiles" python3 scripts/check_radarr_profiles.py
  check "radarr db size" python3 scripts/check_radarr_db_size.py
else
  warn_skip "radarr quality profiles" "no radarr.db (radarr not configured here)"
  warn_skip "radarr db size" "no radarr.db (radarr not configured here)"
fi

if [ -f "$ROOT/config/sonarr/sonarr.db" ] || [ -n "${SONARR_DB:-}" ]; then
  check "sonarr references" python3 scripts/check_sonarr_refs.py
else
  warn_skip "sonarr references" "no sonarr.db (sonarr not configured here)"
fi

if [ -f "$ROOT/config/prowlarr/prowlarr.db" ] || [ -n "${PROWLARR_DB:-}" ]; then
  check "prowlarr references" python3 scripts/check_prowlarr_refs.py
else
  warn_skip "prowlarr references" "no prowlarr.db (prowlarr not configured here)"
fi

check "compose mounts" python3 scripts/check_compose_mounts.py
check "mcp baseline" python3 scripts/check_mcp.py --baseline
check "python env transports" python3 scripts/check_python_env_transports.py

if [ -n "${NZBDAV_QUEUE_OFFLINE:-}" ]; then
  check "nzbdav queue" python3 scripts/check_nzbdav_queue.py --offline
else
  check "nzbdav queue" python3 scripts/check_nzbdav_queue.py --allow-unreachable
fi

if [ -n "${BIND_MOUNT_OFFLINE:-}" ]; then
  check "bind-mount staleness" python3 scripts/check_bind_mount_staleness.py --offline
elif command -v docker >/dev/null 2>&1; then
  check "bind-mount staleness" python3 scripts/check_bind_mount_staleness.py
else
  warn_skip "bind-mount staleness" "docker"
fi

echo
if [ "$failures" -eq 0 ] && [ "$warnings" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
elif [ "$failures" -eq 0 ]; then
  echo "ALL CHECKS PASSED ($warnings skipped: missing local tool, CI still gates)"
else
  echo "$failures check(s) FAILED, $warnings skipped"
fi
exit "$([ "$failures" -eq 0 ] && echo 0 || echo 1)"
