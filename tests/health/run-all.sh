#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Health Check Runner
# ============================================================================
# Runs health checks for all services and reports status.
#
# Usage:
#   ./tests/health/run-all.sh              # Run all health checks
#   ./tests/health/run-all.sh --verbose    # Verbose output
#   ./tests/health/run-all.sh --service X  # Check specific service
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# State
VERBOSE=false
SERVICE=""
TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

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

check_container() {
    local container_name=$1
    local service_name=${2:-$1}
    local health_url=${3:-}
    local health_port=${4:-}
    
    TOTAL=$((TOTAL + 1))
    
    # Check if container exists and is running
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not_found")
    
    if [ "$status" = "running" ]; then
        # Check health status if available
        local health_status
        health_status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no_healthcheck{{end}}' "$container_name" 2>/dev/null || echo "unknown")
        
        if [ "$health_status" = "healthy" ] || [ "$health_status" = "no_healthcheck" ]; then
            log_success "$service_name ($container_name) — $status, health: $health_status"
            PASSED=$((PASSED + 1))
            return 0
        else
            log_warning "$service_name ($container_name) — $status, health: $health_status"
            PASSED=$((PASSED + 1))
            return 0
        fi
    elif [ "$status" = "not_found" ]; then
        log_error "$service_name ($container_name) — container not found"
        FAILED=$((FAILED + 1))
        return 1
    else
        log_error "$service_name ($container_name) — status: $status"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

check_port() {
    local service_name=$1
    local port=$2
    
    if curl -sf "http://localhost:$port" >/dev/null 2>&1 || \
       curl -sf "http://localhost:$port/" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_health_endpoint() {
    local service_name=$1
    local url=$2
    
    if curl -sf "$url" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Service Health Checks
# ============================================================================

check_prowlarr() {
    check_container "prowlarr" "Prowlarr"
}

check_radarr() {
    check_container "radarr" "Radarr"
}

check_sonarr() {
    check_container "sonarr" "Sonarr"
}

check_nzbdav() {
    check_container "nzbdav" "InfiniDysk"
}

check_nzbdav_rclone() {
    check_container "nzbdav_rclone" "nzbdav-rclone"
}

check_seerr() {
    check_container "seerr" "Seerr"
}

check_plex() {
    check_container "plex" "Plex"
}

check_metacache() {
    check_container "metacache" "Metacache"
}

check_control_panel() {
    check_container "control-panel" "Control Panel"
}

check_unpackerr() {
    check_container "unpackerr" "Unpackerr"
}

check_cleanuparr() {
    check_container "cleanuparr" "Cleanuparr"
}

check_watchstate() {
    check_container "watchstate" "WatchState"
}

check_loki() {
    check_container "loki" "Loki"
}

check_promtail() {
    check_container "promtail" "Promtail"
}

check_grafana() {
    check_container "grafana" "Grafana"
}

check_nzbdav_exporter() {
    check_container "nzbdav-exporter" "nzbdav-exporter"
}

check_prometheus() {
    check_container "prometheus" "Prometheus"
}

check_node_exporter() {
    check_container "node-exporter" "Node Exporter"
}

check_cadvisor() {
    check_container "cadvisor" "cAdvisor"
}

check_arr_dashboard() {
    check_container "arr-dashboard" "ARR Dashboard"
}

check_landing_page() {
    check_container "landing-page" "Landing Page"
}

check_traefik() {
    check_container "traefik" "Traefik"
}

# ============================================================================
# Main
# ============================================================================

main() {
    cd "$(dirname "$0")/../.." || exit 1
    
    echo ""
    echo "=========================================="
    echo "  The Bear Cave — Health Checks"
    echo "=========================================="
    echo ""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --verbose)
                VERBOSE=true
                shift
                ;;
            --service)
                SERVICE="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    # Run checks
    if [ -n "$SERVICE" ]; then
        # Check specific service
        case "$SERVICE" in
            prowlarr) check_prowlarr ;;
            radarr) check_radarr ;;
            sonarr) check_sonarr ;;
            nzbdav) check_nzbdav ;;
            nzbdav-rclone) check_nzbdav_rclone ;;
            seerr) check_seerr ;;
            plex) check_plex ;;
            metacache) check_metacache ;;
            control-panel) check_control_panel ;;
            unpackerr) check_unpackerr ;;
            cleanuparr) check_cleanuparr ;;
            watchstate) check_watchstate ;;
            loki) check_loki ;;
            promtail) check_promtail ;;
            grafana) check_grafana ;;
            nzbdav-exporter) check_nzbdav_exporter ;;
            prometheus) check_prometheus ;;
            node-exporter) check_node_exporter ;;
            cadvisor) check_cadvisor ;;
            arr-dashboard) check_arr_dashboard ;;
            landing-page) check_landing_page ;;
            traefik) check_traefik ;;
            *)
                log_error "Unknown service: $SERVICE"
                exit 1
                ;;
        esac
    else
        # Check all services
        check_prowlarr
        check_radarr
        check_sonarr
        check_nzbdav
        check_nzbdav_rclone
        check_seerr
        check_plex
        check_metacache
        check_control_panel
        check_unpackerr
        check_cleanuparr
        check_watchstate
        check_loki
        check_promtail
        check_grafana
        check_nzbdav_exporter
        check_prometheus
        check_node_exporter
        check_cadvisor
        check_arr_dashboard
        check_landing_page
        check_traefik
    fi
    
    # Summary
    echo ""
    echo "=========================================="
    echo "  Summary"
    echo "=========================================="
    echo ""
    echo "Total:  $TOTAL"
    echo -e "Passed: ${GREEN}$PASSED${NC}"
    echo -e "Failed: ${RED}$FAILED${NC}"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        log_success "All health checks passed!"
        exit 0
    else
        log_error "Some health checks failed."
        exit 1
    fi
}

main "$@"
