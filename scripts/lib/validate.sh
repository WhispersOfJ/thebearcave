#!/usr/bin/env bash
# Validation functions for The Bear Cave setup.
# Sources: scripts/lib/helpers.sh

validate_env_file() {
    log_info "Validating .env file..."

    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env file not found. Run: cp .env.template .env"
        return 1
    fi

    local required_vars=(
        "PUID" "PGID" "TZ" "HOST_IP"
        "PLEX_TOKEN" "FRONTEND_BACKEND_API_KEY"
        "RADARR_API_KEY" "SONARR_API_KEY" "PROWLARR_API_KEY"
        "NZBDAV_WEBDAV_USER" "NZBDAV_WEBDAV_PASS"
        "NZBDAV_RCLONE_RC_PASS" "NZBDAV_PROFILE_TOKEN"
        "NZBDAV_USENET_HOST" "NZBDAV_USENET_USER" "NZBDAV_USENET_PASS"
        "WS_API_KEY" "WS_SYSTEM_SECRET"
    )

    local missing=()
    local placeholder=()

    for var in "${required_vars[@]}"; do
        local value
        value=$(grep -E "^${var}=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || true)

        if [ -z "$value" ]; then
            missing+=("$var")
        elif [ "$value" = "changeme" ] || [[ "$value" == \$\{* ]]; then
            placeholder+=("$var")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required variables:"
        for var in "${missing[@]}"; do
            echo "  - $var"
        done
        return 1
    fi

    if [ ${#placeholder[@]} -gt 0 ]; then
        log_warning "Variables still set to placeholder values:"
        for var in "${placeholder[@]}"; do
            echo "  - $var"
        done
    fi

    log_success ".env file validation passed"
    return 0
}

validate_docker() {
    log_info "Validating Docker installation..."

    check_dependency "docker"
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Required command 'docker-compose' or 'docker compose' not found."
        return 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running or current user lacks permissions"
        return 1
    fi

    log_success "Docker validation passed"
    return 0
}

validate_compose() {
    log_info "Validating docker-compose.yml..."

    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found"
        return 1
    fi

    if ! docker compose config --quiet 2>/dev/null; then
        log_error "docker-compose.yml validation failed"
        return 1
    fi

    log_success "docker-compose.yml validation passed"
    return 0
}

validate_directories() {
    log_info "Validating directory structure..."

    local required_dirs=(
        "config"
        "services/plex/config"
        "services/nzbdav-rclone"
        "services/landing-page"
        "services/nzbdav-exporter"
        "media/movies"
        "media/shows"
        "data/loki"
        "data/prometheus"
        "data/grafana"
        "data/metacache"
    )

    local missing=()

    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            missing+=("$dir")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required directories:"
        for dir in "${missing[@]}"; do
            echo "  - $dir"
        done
        return 1
    fi

    log_success "Directory structure validation passed"
    return 0
}
