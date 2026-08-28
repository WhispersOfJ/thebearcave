#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Safe InfiniDysk (nzbdav) Update
# ============================================================================
# Updates the InfiniDysk container to whatever image tag docker-compose.yml
# pins, with the two landmines handled:
#
#   1. Queue guard (docs/services/nzbdav.md): recreating the container wipes
#      queued NZBs and silently blocklists the affected items. This script
#      refuses to touch the container unless the queue is empty.
#   2. Mount cascade (docs/landmines.md): nzbdav_rclone is the FUSE mount
#      owner; restarting it breaks dependents. docker compose's health-gated
#      `restart: true` deps cascade the restart automatically — this script
#      waits for every affected container to come back healthy and verifies
#      the mount actually serves content before declaring success.
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
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            log_error "Unknown option: $arg (supported: --dry-run, --force)"
            exit 1
            ;;
    esac
done

# Containers that must be healthy again before we call the update done.
DEPENDENTS=(radarr sonarr plex unpackerr cleanuparr)
WAIT_MAX_SECONDS=300
POLL_SECONDS=5

cd "$(dirname "$0")/.." || exit 1

# ============================================================================
# Preflight
# ============================================================================

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
log_success "Preflight OK (docker up, nzbdav + nzbdav_rclone running)"

# ============================================================================
# Queue guard — the whole point of this script
# ============================================================================

log_info "Checking InfiniDysk queue (recreate wipes queued NZBs and blocklists items)..."

queue_json=$(curl -sf --max-time 15 \
    "http://localhost:3000/api?mode=queue&output=json&apikey=${FRONTEND_BACKEND_API_KEY}" || echo "")

if [ -z "$queue_json" ]; then
    log_error "Queue API unreachable — refusing to proceed blind. Check nzbdav health first."
    exit 1
fi

queue_count=$(printf '%s' "$queue_json" | python3 -c "
import sys, json
try:
    q = json.load(sys.stdin).get('queue', {})
    slots = q.get('slots', [])
    print(len(slots) if slots else q.get('noofslots', 0))
except Exception:
    print(-1)
")

if [ -z "$queue_count" ]; then
    log_error "Could not run the queue check (python3 missing?) — refusing to proceed"
    exit 1
fi

if [ "$queue_count" -lt 0 ]; then
    log_error "Could not parse queue API response — refusing to proceed"
    exit 1
fi

if [ "$queue_count" -gt 0 ]; then
    if [ "$FORCE" = true ]; then
        log_warning "--force set: proceeding with ${queue_count} queued item(s). Queued NZBs WILL be lost and blocklisted."
    else
        log_error "Queue is NOT empty (${queue_count} item(s)). Aborting."
        log_error "Wait for downloads to finish, clear the queue, or re-run with --force if you accept the data loss."
        exit 1
    fi
else
    log_success "Queue is empty — safe to recreate"
fi

if [ "$DRY_RUN" = true ]; then
    log_info "Dry run — stopping before pull/recreate. Current image: $(docker inspect nzbdav --format '{{.Config.Image}}')"
    exit 0
fi

# ============================================================================
# Pull + recreate (compose cascades rclone + dependents via restart: true)
# ============================================================================

log_info "Pulling image for nzbdav..."
if ! docker compose pull nzbdav; then
    log_error "Pull failed — no changes made"
    exit 1
fi

log_info "Recreating nzbdav (compose will cascade the FUSE mount owner + dependents)..."
docker compose up -d nzbdav

# ============================================================================
# Health waits
# ============================================================================

wait_healthy() {
    local name=$1 deadline
    deadline=$((SECONDS + WAIT_MAX_SECONDS))
    while [ "$SECONDS" -lt "$deadline" ]; do
        local status
        status=$(docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")
        if [ "$status" = "healthy" ]; then
            log_success "$name healthy"
            return 0
        fi
        sleep "$POLL_SECONDS"
    done
    log_error "$name did not become healthy within ${WAIT_MAX_SECONDS}s (last status: ${status:-unknown})"
    return 1
}

log_info "Waiting for the downloader and mount owner..."
wait_healthy nzbdav || exit 1
wait_healthy nzbdav_rclone || exit 1

# The mount must actually serve content, not just report healthy — the
# healthcheck passes between crash-loops too.
log_info "Verifying the FUSE mount serves content..."
if timeout 15 docker exec nzbdav_rclone ls /mnt/remote/nzbdav >/dev/null 2>&1; then
    log_success "FUSE mount serving content"
else
    log_error "FUSE mount not serving — restart dependents per docs/operations/troubleshooting.md"
    exit 1
fi

log_info "Waiting for dependents: ${DEPENDENTS[*]}..."
for svc in "${DEPENDENTS[@]}"; do
    wait_healthy "$svc" || exit 1
done

# ============================================================================
# Post-update verification
# ============================================================================

post_queue=$(curl -sf --max-time 15 \
    "http://localhost:3000/api?mode=queue&output=json&apikey=${FRONTEND_BACKEND_API_KEY}" || echo "")
if [ -n "$post_queue" ]; then
    log_success "Queue API responding on the new build"
else
    log_error "Queue API not responding after update — check: docker logs nzbdav"
    exit 1
fi

if timeout 10 curl -sf http://localhost:3000/healthz >/dev/null; then
    log_success "healthz OK"
else
    log_error "healthz failed after update"
    exit 1
fi

echo ""
log_success "InfiniDysk updated: $(docker inspect nzbdav --format '{{.Config.Image}}') ($(docker inspect nzbdav --format '{{.Image}}' | cut -c8-19))"
log_info "Rollback if needed: flip the tag back in docker-compose.yml, then re-run this script."
