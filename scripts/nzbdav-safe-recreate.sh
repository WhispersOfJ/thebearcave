#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — guarded nzbdav recreate wrapper
# ============================================================================
# Wraps every path that recreates the nzbdav container so the non-persistent
# queue landmine cannot bite via a bare `docker compose up -d nzbdav` /
# `docker compose restart nzbdav` that bypasses scripts/update-nzbdav.sh.
#
# Run the queue guard (scripts/check_nzbdav_queue.py) first; only if the
# queue is at/under threshold does it forward the remaining args to
# `docker compose`. --force skips the guard (DANGEROUS — queued NZBs are
# wiped and blocklisted on recreate).
#
# Install as a shell alias or function so `docker compose ... nzbdav` routes
# here, or call directly:
#   ./scripts/nzbdav-safe-recreate.sh up -d nzbdav
#   ./scripts/nzbdav-safe-recreate.sh up -d --force-recreate nzbdav   # guarded
#   ./scripts/nzbdav-safe-recreate.sh restart nzbdav
#
# Exit codes: 0 = recreate completed; 1 = queue guard tripped (no recreate);
#             2 = docker compose itself failed after the guard passed.
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

# Load repository settings so the queue guard works from a clean shell too.
# Compose loads .env for interpolation independently, but the Python guard
# reads FRONTEND_BACKEND_API_KEY from its process environment.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

FORCE=false
compose_args=()
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) compose_args+=("$arg") ;;
    esac
done

if [ ${#compose_args[@]} -eq 0 ]; then
    echo "Usage: $0 <docker compose args> [--force]" >&2
    exit 1
fi

# Only guard operations that touch the nzbdav service; pure queries
# (ps, config, logs) pass through ungated.
needs_guard=false
for a in "${compose_args[@]}"; do
    case "$a" in
        up|restart|start|stop|rm|down) needs_guard=true ;;
    esac
done

# The service being targeted — if it's not nzbdav, no guard needed.
targets_nzbdav=false
for a in "${compose_args[@]}"; do
    case "$a" in
        nzbdav|nzbdav_rclone) targets_nzbdav=true ;;
    esac
done

if [ "$needs_guard" = true ] && [ "$targets_nzbdav" = true ] && [ "$FORCE" = false ]; then
    echo "[guard] checking nzbdav queue before recreate..."
    if ! python3 scripts/check_nzbdav_queue.py; then
        echo "[guard] refusing to recreate — queue is non-empty." >&2
        echo "[guard] wait for downloads, clear the queue, or pass --force to accept data loss." >&2
        exit 1
    fi
fi

echo "[guard] OK — forwarding to: docker compose ${compose_args[*]}"
if ! docker compose "${compose_args[@]}"; then
    echo "[guard] docker compose failed" >&2
    exit 2
fi
echo "[guard] done."
