#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Setup Script
# ============================================================================
# Initializes Docker secrets, validates configuration, and prepares the
# stack for first deployment.
#
# Usage:
#   ./scripts/setup.sh                    # Interactive setup
#   ./scripts/setup.sh --non-interactive  # Non-interactive (uses defaults)
#   ./scripts/setup.sh --validate-only    # Only validate existing config
#   ./scripts/setup.sh --sync-github-secrets  # Sync .env → GitHub Actions secrets
# ============================================================================
#
# GitHub secret sync: release-please needs RELEASE_PLEASE_TOKEN as a repo
# Actions secret — the local .env is never visible to CI. This script syncs
# the value (piped, never echoed) automatically in --non-interactive mode, on
# request in interactive mode, or via --sync-github-secrets.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Constants
SECRETS_DIR="secrets"
ENV_FILE=".env"
ENV_TEMPLATE=".env.template"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependency() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command '$1' not found. Please install it first."
        exit 1
    fi
}

generate_secret() {
    local length=${1:-32}
    openssl rand -hex "$length" 2>/dev/null || head -c "$length" /dev/urandom | xxd -p | tr -d '\n' | head -c "$((length * 2))"
}

# rclone.conf passwords must be rclone-obfuscated, not plaintext.
# Generate with: rclone obscure "your-password-here"
# The template at services/nzbdav-rclone/rclone.conf.template has a
# placeholder — the actual rclone.conf is gitignored and must be
# configured manually after running: rclone obscure <password>

# ============================================================================
# Validation Functions
# ============================================================================

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
        "CONTROL_PANEL_SECRET_KEY" "CONTROL_PANEL_ADMIN_PASSWORD"
        "CONTROL_PANEL_SERVICE_API_KEY"
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
        "services/control-panel/django"
        "services/nzbdav-exporter"
        "media/movies"
        "media/shows"
        "data/loki"
        "data/prometheus"
        "data/grafana"
        "data/metacache"
        "logs/control-panel"
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

# ============================================================================
# Secrets Functions
# ============================================================================

create_secrets_dir() {
    log_info "Creating secrets directory..."
    
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
    
    log_success "Secrets directory created"
}

generate_secrets() {
    log_info "Generating Docker secrets..."
    
    local secrets=(
        "plex_token"
        "radarr_api_key"
        "sonarr_api_key"
        "prowlarr_api_key"
        "tmdb_key"
        "tvdb_key"
        "frontend_backend_api_key"
        "nzbdav_webdav_user"
        "nzbdav_webdav_pass"
        "nzbdav_rclone_rc_pass"
        "nzbdav_profile_token"
        "nzbdav_usenet_host"
        "nzbdav_usenet_user"
        "nzbdav_usenet_pass"
        "nzbdav_usenet_backup_host"
        "nzbdav_usenet_backup_user"
        "nzbdav_usenet_backup_pass"
        "ws_api_key"
        "ws_system_secret"
        "control_panel_secret_key"
        "control_panel_admin_password"
        "control_panel_service_api_key"
        "metacache_api_key"
        "discord_webhook_url"
        "omdb_key"
        "mdblist_key"
        "fanart_key"
        "grafana_admin_password"
    )
    
    for secret in "${secrets[@]}"; do
        local secret_file="$SECRETS_DIR/$secret"
        
        if [ ! -f "$secret_file" ]; then
            local value
            value=$(generate_secret 32)
            echo -n "$value" > "$secret_file"
            chmod 600 "$secret_file"
            log_info "Generated secret: $secret"
        else
            log_info "Secret already exists: $secret"
        fi
    done
    
    log_success "All secrets generated"
}

# ============================================================================
# GitHub Secrets Sync
# ============================================================================

# RELEASE_PLEASE_TOKEN lives in .env for local convenience, but GitHub Actions
# can only read it as a repository Actions secret — the local .env is never
# visible to CI. Keep the two in sync. The value is piped to `gh secret set`
# from stdin so it is never echoed, logged, or exposed in the process list.
#
# Why it matters: release-please opens the release PR with this token so the
# PR triggers validate.yml. PRs opened with the default GITHUB_TOKEN are
# skipped by GitHub's recursion guard, so the release PR would ship without CI.
sync_github_secrets() {
    log_info "Syncing GitHub Actions secrets from .env..."

    if ! command -v gh &> /dev/null; then
        log_warning "GitHub CLI (gh) not found — skipping secret sync."
        echo "  RELEASE_PLEASE_TOKEN (if set) only works as a GitHub Actions secret."
        echo "  Install gh (https://cli.github.com) and re-run, or set it manually:"
        echo "  Settings → Secrets and variables → Actions → New repository secret."
        return 0
    fi

    local token
    token=$(grep -E "^RELEASE_PLEASE_TOKEN=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)

    if [ -z "$token" ]; then
        log_warning "RELEASE_PLEASE_TOKEN is not set in $ENV_FILE."
        echo "  release-please needs it so release PRs run validate.yml; add"
        echo "  RELEASE_PLEASE_TOKEN=ghp_... to .env and re-run, or set it as a"
        echo "  repo Actions secret manually. Without it, release-please falls"
        echo "  back to GITHUB_TOKEN (works, but release PRs skip CI)."
        return 0
    fi

    if ! gh repo view &> /dev/null; then
        log_warning "Not inside a GitHub repository (or gh is not authenticated) — skipping secret sync."
        return 0
    fi

    printf '%s' "$token" | gh secret set RELEASE_PLEASE_TOKEN
    log_success "RELEASE_PLEASE_TOKEN synced to the GitHub Actions secret."
    return 0
}

# ============================================================================
# Main Setup Functions
# ============================================================================

interactive_setup() {
    log_info "Starting interactive setup..."
    
    echo ""
    echo "=========================================="
    echo "  The Bear Cave — Initial Setup"
    echo "=========================================="
    echo ""
    
    # Check if .env exists
    if [ ! -f "$ENV_FILE" ]; then
        log_warning ".env file not found."
        echo ""
        read -p "Create .env from template? (Y/n): " create_env
        if [ "${create_env:-Y}" != "n" ]; then
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            log_success "Created .env from template"
            echo ""
            echo "Please edit .env with your actual values before continuing."
            echo ""
            read -p "Press Enter after editing .env..."
        fi
    fi
    
    # Validate
    echo ""
    log_info "Running validation checks..."
    echo ""
    
    local validation_failed=0
    
    validate_docker || validation_failed=1
    validate_env_file || validation_failed=1
    validate_compose || validation_failed=1
    validate_directories || validation_failed=1
    
    if [ $validation_failed -eq 1 ]; then
        log_error "Validation failed. Please fix the issues above and run setup again."
        exit 1
    fi
    
    # Generate secrets
    echo ""
    read -p "Generate Docker secrets? (Y/n): " gen_secrets
    if [ "${gen_secrets:-Y}" != "n" ]; then
        create_secrets_dir
        generate_secrets
    fi

    # Sync GitHub secrets
    echo ""
    read -p "Sync RELEASE_PLEASE_TOKEN to GitHub Actions secret? (Y/n): " sync_gh
    if [ "${sync_gh:-Y}" != "n" ]; then
        sync_github_secrets
    fi

    # Final status
    echo ""
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Review and update .env with your actual values"
    echo "  2. Start the stack: docker compose up -d"
    echo "  3. Verify health: ./tests/health/run-all.sh"
    echo ""
}

non_interactive_setup() {
    log_info "Starting non-interactive setup..."
    
    # Create .env if missing
    if [ ! -f "$ENV_FILE" ]; then
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        log_warning "Created .env from template. Please edit with actual values."
    fi
    
    # Run validation
    validate_docker
    validate_env_file
    validate_compose
    validate_directories
    
    # Generate secrets
    create_secrets_dir
    generate_secrets

    # Sync GitHub secrets automatically (non-interactive mode does everything)
    sync_github_secrets

    log_success "Non-interactive setup complete"
}

validate_only() {
    log_info "Running validation only..."
    
    validate_docker
    validate_env_file
    validate_compose
    validate_directories
    
    log_success "All validations passed"
}

# ============================================================================
# Main
# ============================================================================

main() {
    cd "$(dirname "$0")/.." || exit 1
    
    case "${1:-}" in
        --non-interactive)
            non_interactive_setup
            ;;
        --validate-only)
            validate_only
            ;;
        --sync-github-secrets)
            sync_github_secrets
            ;;
        *)
            interactive_setup
            ;;
    esac
}

main "$@"
