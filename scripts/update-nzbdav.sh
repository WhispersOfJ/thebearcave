#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Safe InfiniDysk (nzbdav) Update
# ============================================================================
# Updates the pinned InfiniDysk image with the queue and FUSE mount landmines
# handled. Recreating nzbdav wipes queued NZBs, and restarting the FUSE owner
# invalidates bind handles held by media consumers.
#
# Usage:
#   ./scripts/update-nzbdav.sh            # guarded update
#   ./scripts/update-nzbdav.sh --dry-run  # preflight + queue check only
#   ./scripts/update-nzbdav.sh --force    # skip the queue guard (DANGEROUS)
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[FAIL]${NC} $1"; }

FORCE=false
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --force)   FORCE=true ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            log_error "Unknown option: $arg (supported: --dry-run, --force)"
            exit 1
            ;;
    esac
done

# Services that depend on the rclone FUSE mount and must be healthy again.
DEPENDENTS=(radarr sonarr plex unpackerr)
WAIT_MAX_SECONDS=300
POLL_SECONDS=5

cd "$(dirname "$0")/.." || exit 1

log_info "Preflight..."
if [ ! -f ".env" ]; then
    log_error ".env not found — run from the repo root (or after setup.sh)"
    exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${FRONTEND_BACKEND_API_KEY:-}" ]; then
    log_error "FRONTEND_BACKEND_API_KEY not set in .env — cannot query the queue API"
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    log_error "Docker is not running"
    exit 1
fi
for svc in nzbdav nzbdav_rclone; do
    if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$svc"; then
        log_error "$svc is not running — start the stack first"
        exit 1
    fi
done
log_success "Preflight OK (nzbdav + nzbdav_rclone running)"

log_info "Checking InfiniDysk queue (recreate wipes queued NZBs)..."
queue_json=$(curl -sf --max-time 15 \
    "http://localhost:3000/api?mode=queue&output=json&apikey=${FRONTEND_BACKEND_API_KEY}" || echo "")
if [ -z "$queue_json" ]; then
    log_error "Queue API unreachable — refusing to proceed blind."
    exit 1
fi
queue_count=$(printf '%s' "$queue_json" | python3 -c '
import json
import sys
try:
    queue = json.load(sys.stdin).get("queue", {})
    slots = queue.get("slots", [])
    print(len(slots) if slots else queue.get("noofslots", 0))
except Exception:
    print(-1)
')
if [ "$queue_count" -lt 0 ]; then
    log_error "Could not parse queue API response — refusing to proceed"
    exit 1
fi
if [ "$queue_count" -gt 0 ]; then
    if [ "$FORCE" = true ]; then
        log_warning "--force set: proceeding with ${queue_count} queued item(s); queued NZBs WILL be lost."
    else
        log_error "Queue is NOT empty (${queue_count} item(s)). Aborting."
        log_error "Wait for downloads to finish, clear the queue, or use --force."
        exit 1
    fi
else
    log_success "Queue is empty — safe to recreate"
fi

if [ "$DRY_RUN" = true ]; then
    log_info "Dry run — stopping before pull/recreate."
    exit 0
fi

log_info "Pulling the pinned InfiniDysk image..."
docker compose pull nzbdav
log_info "Recreating nzbdav and its FUSE dependency cascade..."
docker compose up -d nzbdav

wait_healthy() {
    local name=$1
    local status="unknown"
    local deadline=$((SECONDS + WAIT_MAX_SECONDS))
    while [ "$SECONDS" -lt "$deadline" ]; do
        status=$(docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null || echo missing)
        if [ "$status" = healthy ]; then
            log_success "$name healthy"
            return 0
        fi
        sleep "$POLL_SECONDS"
    done
    log_error "$name did not become healthy within ${WAIT_MAX_SECONDS}s (last status: $status)"
    return 1
}

wait_healthy nzbdav
wait_healthy nzbdav_rclone
log_info "Verifying the FUSE mount serves content..."
if timeout 15 docker exec nzbdav_rclone ls /mnt/remote/nzbdav >/dev/null 2>&1; then
    log_success "FUSE mount serving content"
else
    log_error "FUSE mount not serving"
    exit 1
fi
for svc in "${DEPENDENTS[@]}"; do
    wait_healthy "$svc"
done

if curl -sf --max-time 15 \
    "http://localhost:3000/api?mode=queue&output=json&apikey=${FRONTEND_BACKEND_API_KEY}" >/dev/null; then
    log_success "Queue API responding"
else
    log_error "Queue API not responding after update"
    exit 1
fi
if curl -sf --max-time 10 http://localhost:3000/healthz >/dev/null; then
    log_success "healthz OK"
else
    log_error "healthz failed after update"
    exit 1
fi

echo
docker inspect nzbdav --format 'InfiniDysk image: {{.Config.Image}}'
log_success "InfiniDysk update complete"
