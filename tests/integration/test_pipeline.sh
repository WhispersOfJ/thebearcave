#!/usr/bin/env bash
# The Bear Cave — active eight-service pipeline integration test.
# Verifies the non-destructive critical path: services, queue, WebDAV/FUSE,
# Plex libraries, and Radarr/Sonarr root folders.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; }

cd "$(dirname "$0")/../.."
if [ -f .env ]; then set -a; source .env; set +a; fi

check() {
    local name=$1; shift
    if "$@" >/dev/null 2>&1; then log_success "$name"; return 0; fi
    log_error "$name"; return 1
}

infra_ready() {
    local failed=0
    check "Docker running" docker info || failed=$((failed + 1))
    for svc in prowlarr radarr sonarr nzbdav nzbdav_rclone seerr plex unpackerr; do
        if docker ps --filter "name=^/${svc}$" --format '{{.Names}}' | grep -qx "$svc"; then
            log_success "$svc running"
        else
            log_error "$svc running"
            failed=$((failed + 1))
        fi
    done
    check "Prowlarr responding" curl -sf http://localhost:9696/ping || failed=$((failed + 1))
    check "Radarr responding" curl -sf http://localhost:7878/ping || failed=$((failed + 1))
    check "Sonarr responding" curl -sf http://localhost:8989/ping || failed=$((failed + 1))
    check "NzbDAV responding" curl -sf http://localhost:3000/healthz || failed=$((failed + 1))
    check "Plex responding" curl -sf http://localhost:32400/identity || failed=$((failed + 1))
    check "rclone mount active" docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav || failed=$((failed + 1))
    [ "$failed" -eq 0 ]
}

queue_empty() {
    local key=${FRONTEND_BACKEND_API_KEY:-}
    [ -n "$key" ] || { log_error "FRONTEND_BACKEND_API_KEY is not set"; return 1; }
    local response
    response=$(curl -sf --max-time 15 "http://localhost:3000/api?mode=queue&output=json&apikey=${key}") || return 1
    python3 -c 'import json,sys; q=json.load(sys.stdin).get("queue",{}); assert int(q.get("noofslots",0)) == 0 and not q.get("slots")' <<< "$response"
    log_success "NzbDAV queue is empty"
}

mount_content() {
    docker exec nzbdav_rclone ls /mnt/remote/nzbdav >/dev/null
    log_success "WebDAV/FUSE mount is readable"
}

plex_library() {
    local xml
    xml=$(curl -sf -H "X-Plex-Token: ${PLEX_TOKEN:-}" http://localhost:32400/library/sections)
    [[ "$xml" == *'title="Movies"'* ]] || { log_error "Plex Movies section missing"; return 1; }
    [[ "$xml" == *'title="Shows"'* ]] || { log_error "Plex Shows section missing"; return 1; }
    log_success "Plex reports Movies and Shows sections"
}

arr_roots() {
    local radarr_key=${RADARR_API_KEY:-} sonarr_key=${SONARR_API_KEY:-}
    local radarr sonarr
    radarr=$(curl -sf -H "X-Api-Key: $radarr_key" http://localhost:7878/api/v3/rootfolder)
    sonarr=$(curl -sf -H "X-Api-Key: $sonarr_key" http://localhost:8989/api/v3/rootfolder)
    [[ "$radarr" == *'"path": "/data/movies"'* && "$radarr" == *'"accessible": true'* ]] || { log_error "Radarr /data/movies root is inaccessible"; return 1; }
    [[ "$sonarr" == *'"path": "/data/shows"'* && "$sonarr" == *'"accessible": true'* ]] || { log_error "Sonarr /data/shows root is inaccessible"; return 1; }
    log_success "Radarr and Sonarr roots are accessible"
}

main() {
    local dry_run=false
    [ "${1:-}" = "--dry-run" ] && dry_run=true
    echo "=========================================="
    echo "  The Bear Cave — Pipeline Integration"
    echo "=========================================="
    infra_ready || exit 1
    if [ "$dry_run" = true ]; then log_info "Dry run — skipping live pipeline probes"; exit 0; fi
    queue_empty
    mount_content
    plex_library
    arr_roots
    log_success "Active pipeline checks passed"
}
main "$@"
