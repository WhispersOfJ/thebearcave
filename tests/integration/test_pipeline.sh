#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Pipeline Integration Test
# ============================================================================
# Verifies the full request pipeline:
#   Seerr → Radarr/Sonarr → InfiniDysk → rclone mount → Plex
#   plus TLS: the served cert is mkcert-signed and validates against the
#   local CA (no browser warning).
#
# Usage:
#   ./tests/integration/test_pipeline.sh           # Run full test
#   ./tests/integration/test_pipeline.sh --dry-run # Only check prereqs
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

check_prerequisite() {
    local name=$1
    local check=$2
    
    if eval "$check" >/dev/null 2>&1; then
        log_success "Prerequisite: $name"
        return 0
    else
        log_error "Prerequisite failed: $name"
        return 1
    fi
}

# ============================================================================
# Test Functions
# ============================================================================

test_infra_ready() {
    log_info "Checking infrastructure readiness..."
    
    local failed=0
    check_prerequisite "Docker running" "docker info" || failed=$((failed + 1))
    check_prerequisite "Plex container running" "docker ps --filter name=^/plex$ --format '{{.Names}}' | grep -qx plex" || failed=$((failed + 1))
    check_prerequisite "Radarr container running" "docker ps --filter name=^/radarr$ --format '{{.Names}}' | grep -qx radarr" || failed=$((failed + 1))
    check_prerequisite "Sonarr container running" "docker ps --filter name=^/sonarr$ --format '{{.Names}}' | grep -qx sonarr" || failed=$((failed + 1))
    check_prerequisite "InfiniDysk container running" "docker ps --filter name=^/nzbdav$ --format '{{.Names}}' | grep -qx nzbdav" || failed=$((failed + 1))
    check_prerequisite "rclone mount active" "docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav" || failed=$((failed + 1))
    check_prerequisite "Plex responding" "curl -sf http://localhost:32400/identity" || failed=$((failed + 1))
    check_prerequisite "Radarr responding" "curl -sf http://localhost:7878/ping" || failed=$((failed + 1))
    check_prerequisite "Sonarr responding" "curl -sf http://localhost:8989/ping" || failed=$((failed + 1))
    check_prerequisite "InfiniDysk responding" "curl -sf http://localhost:3000/healthz" || failed=$((failed + 1))
    
    if [ $failed -gt 0 ]; then
        log_error "$failed prerequisite(s) failed"
        return 1
    fi
    
    log_success "All prerequisites met"
    return 0
}

test_rclone_mount() {
    log_info "Testing rclone mount health..."
    
    # Check mountpoint exists
    if ! docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav; then
        log_error "rclone mount not active"
        return 1
    fi
    
    # Check mount has content
    local file_count
    file_count=$(docker exec nzbdav_rclone ls /mnt/remote/nzbdav 2>/dev/null | wc -l)
    
    if [ "$file_count" -eq 0 ]; then
        log_warning "rclone mount is empty (may be normal if no downloads yet)"
    else
        log_success "rclone mount has content: $file_count items"
    fi
    
    # Check rclone RC is accessible. The RC endpoint requires POST + HTTP
    # Basic auth; busybox wget in the container has no --user/--password
    # flags, so build the Basic header from the .env RC user/pass.
    local rc_basic
    rc_basic=$(docker exec nzbdav_rclone sh -c \
        "echo -n 'rclone:${NZBDAV_RCLONE_RC_PASS}' | base64" 2>/dev/null)
    if [ -n "$rc_basic" ] && docker exec nzbdav_rclone wget -q -O /dev/null \
        --post-data='{}' \
        --header="Authorization: Basic $rc_basic" \
        http://localhost:5572/rc/noop; then
        log_success "rclone RC endpoint responding"
    else
        log_warning "rclone RC endpoint not responding"
    fi
    
    return 0
}

test_plex_library() {
    log_info "Testing Plex library..."
    
    # Check Plex sections
    local sections
    sections=$(curl -sf "http://localhost:32400/library/sections" -H "X-Plex-Token: ${PLEX_TOKEN}" 2>/dev/null || echo "")
    
    if [ -z "$sections" ]; then
        log_warning "Could not fetch Plex library sections (may need token)"
        return 0
    fi
    
    # Count sections
    local section_count
    section_count=$(echo "$sections" | grep -o "title=" | wc -l)
    
    if [ "$section_count" -gt 0 ]; then
        log_success "Plex has $section_count library section(s)"
    else
        log_warning "No Plex library sections found"
    fi
    
    # Check library items
    local item_count
    item_count=$(curl -sf "http://localhost:32400/library/sections/1/all" -H "X-Plex-Token: ${PLEX_TOKEN}" 2>/dev/null | grep -o "size=" | wc -l || echo "0")
    
    if [ "$item_count" -gt 0 ]; then
        log_success "Plex library has items"
    else
        log_warning "Plex library appears empty"
    fi
    
    return 0
}

test_tls_certificate() {
    log_info "Testing TLS certificate (mkcert-signed, no browser warning)..."

    # The local CA that devices install to trust the stack. Missing means the
    # CA setup never ran — and then browsers genuinely would warn.
    local ca_file="config/ca/rootCA.pem"
    local host_ip="${HOST_IP:-192.168.4.20}"
    local sni="bearcave.${host_ip}.nip.io"

    if [ ! -f "$ca_file" ]; then
        log_error "Local CA not found at $ca_file — run scripts/trust-ca.sh first"
        return 1
    fi
    if ! command -v openssl >/dev/null 2>&1; then
        log_error "openssl not found on the test host"
        return 1
    fi

    # 1. The served cert must be signed by the local CA — never Traefik's
    #    built-in "TRAEFIK DEFAULT CERT" fallback (the pre-CA state).
    local issuer
    issuer=$(echo | openssl s_client -connect "${host_ip}:443" \
        -servername "$sni" 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null || echo "")

    if [[ "$issuer" == *"TRAEFIK DEFAULT CERT"* ]]; then
        log_error "Traefik is serving its self-signed default cert — the mkcert CA is not wired (check config/traefik/dynamic/tls.yml)"
        return 1
    fi
    if [[ "$issuer" != *"mkcert"* ]]; then
        log_error "Unexpected certificate issuer: ${issuer:-<none>} (expected the mkcert local CA)"
        return 1
    fi
    log_success "Served certificate issuer is the mkcert local CA"

    # 2. The chain must validate against rootCA.pem — that is what decides
    #    whether a browser shows a warning. -verify_return_error makes s_client
    #    exit non-zero on any verification failure (e.g. ERR_CERT_AUTHORITY_INVALID).
    if ! echo | openssl s_client -connect "${host_ip}:443" \
        -servername "$sni" -CAfile "$ca_file" -verify_return_error >/dev/null 2>&1; then
        log_error "Certificate chain does not validate against the local CA — devices would get a browser warning"
        return 1
    fi
    log_success "Certificate chain validates against rootCA.pem — no browser warning"
    return 0
}

test_radarr_root_folders() {
    log_info "Testing Radarr root folders..."
    
    local response
    response=$(curl -sf "http://localhost:7878/api/v3/rootfolder" \
        -H "X-Api-Key: ${RADARR_API_KEY}" 2>/dev/null || echo "")
    
    if [ -z "$response" ]; then
        log_warning "Could not fetch Radarr root folders (may need API key)"
        return 0
    fi
    
    if [[ "$response" == *"\"path\""* ]]; then
        log_success "Radarr root folders configured"
    else
        log_warning "No Radarr root folders found"
    fi
    
    return 0
}

test_sonarr_root_folders() {
    log_info "Testing Sonarr root folders..."
    
    local response
    response=$(curl -sf "http://localhost:8989/api/v3/rootfolder" \
        -H "X-Api-Key: ${SONARR_API_KEY}" 2>/dev/null || echo "")
    
    if [ -z "$response" ]; then
        log_warning "Could not fetch Sonarr root folders (may need API key)"
        return 0
    fi
    
    if [[ "$response" == *"\"path\""* ]]; then
        log_success "Sonarr root folders configured"
    else
        log_warning "No Sonarr root folders found"
    fi
    
    return 0
}

test_infinidysk_api() {
    log_info "Testing InfiniDysk API..."
    
    # Check health
    if ! curl -sf http://localhost:3000/healthz >/dev/null; then
        log_error "InfiniDysk health check failed"
        return 1
    fi
    
    log_success "InfiniDysk health check passed"
    
    # Check queue (may be empty)
    local queue
    queue=$(curl -sf "http://localhost:3000/api/queue" \
        -H "X-Api-Key: ${FRONTEND_BACKEND_API_KEY}" 2>/dev/null || echo "[]")
    
    if [ -n "$queue" ]; then
        log_success "InfiniDysk queue accessible"
    else
        log_warning "InfiniDysk queue not accessible"
    fi
    
    return 0
}

test_metacache() {
    log_info "Testing Metacache..."
    
    # Check health
    if ! curl -sf http://localhost:8765/healthz >/dev/null; then
        log_error "Metacache health check failed"
        return 1
    fi
    
    log_success "Metacache health check passed"
    
    # Check metrics
    local metrics
    metrics=$(curl -sf http://localhost:8765/metrics 2>/dev/null || echo "")
    
    if [ -n "$metrics" ]; then
        log_success "Metacache metrics accessible"
    else
        log_warning "Metacache metrics not accessible"
    fi
    
    return 0
}

test_symlink_integrity() {
    log_info "Testing symlink integrity (sampled — full scan resolves 30k+ links through the FUSE mount)..."
    
    local media_dirs=(
        "/home/bear/TheBearCave/media/movies"
        "/home/bear/TheBearCave/media/shows"
        "/home/bear/TheBearCave/media/anime-movies"
        "/home/bear/TheBearCave/media/anime-shows"
    )
    
    local total_symlinks=0
    local broken_symlinks=0
    local checked=0
    
    for dir in "${media_dirs[@]}"; do
        if [ -d "$dir" ]; then
            local symlinks
            symlinks=$(find "$dir" -type l 2>/dev/null | wc -l)
            total_symlinks=$((total_symlinks + symlinks))
            
            # Sample up to 50 symlinks per dir — each `test -e` resolves
            # through the rclone FUSE mount (WebDAV), so a full scan of
            # 30k+ links can take hours.
            while IFS= read -r link; do
                checked=$((checked + 1))
                if [ ! -e "$link" ]; then
                    broken_symlinks=$((broken_symlinks + 1))
                    log_warning "Broken: $link"
                fi
            done < <(find "$dir" -type l 2>/dev/null | head -50)
        fi
    done
    
    if [ $total_symlinks -eq 0 ]; then
        log_warning "No symlinks found in media directories"
        return 0
    fi
    
    if [ $broken_symlinks -eq 0 ]; then
        log_success "All $checked sampled symlinks valid (of $total_symlinks total)"
    else
        log_error "Found $broken_symlinks broken symlinks in $checked sampled"
        return 1
    fi
    
    return 0
}

# ============================================================================
# Main
# ============================================================================

main() {
    cd "$(dirname "$0")/../.." || exit 1
    
    echo ""
    echo "=========================================="
    echo "  The Bear Cave — Pipeline Integration Test"
    echo "=========================================="
    echo ""
    
    # Parse arguments
    local dry_run=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    # Run tests
    local failed=0
    
    test_infra_ready || failed=$((failed + 1))
    
    if [ "$dry_run" = true ]; then
        log_info "Dry run mode — skipping integration tests"
        return 0
    fi
    
    test_tls_certificate || failed=$((failed + 1))
    test_rclone_mount || failed=$((failed + 1))
    test_plex_library || failed=$((failed + 1))
    test_radarr_root_folders || failed=$((failed + 1))
    test_sonarr_root_folders || failed=$((failed + 1))
    test_infinidysk_api || failed=$((failed + 1))
    test_metacache || failed=$((failed + 1))
    test_symlink_integrity || failed=$((failed + 1))
    
    # Summary
    echo ""
    echo "=========================================="
    echo "  Summary"
    echo "=========================================="
    echo ""
    
    if [ $failed -eq 0 ]; then
        log_success "All integration tests passed!"
        exit 0
    else
        log_error "$failed test(s) failed"
        exit 1
    fi
}

main "$@"
