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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/helpers.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/validate.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/secrets.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/github.sh"

# ============================================================================
# Setup Modes
# ============================================================================

interactive_setup() {
    log_info "Starting interactive setup..."

    echo ""
    echo "=========================================="
    echo "  The Bear Cave — Initial Setup"
    echo "=========================================="
    echo ""

    if [ ! -f "$ENV_FILE" ]; then
        log_warning ".env file not found."
        echo ""
        read -r -p "Create .env from template? (Y/n): " create_env
        if [ "${create_env:-Y}" != "n" ]; then
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            log_success "Created .env from template"
            echo ""
            echo "Please edit .env with your actual values before continuing."
            echo ""
            read -r -p "Press Enter after editing .env..."
        fi
    fi

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

    echo ""
    read -r -p "Generate Docker secrets? (Y/n): " gen_secrets
    if [ "${gen_secrets:-Y}" != "n" ]; then
        create_secrets_dir
        generate_secrets
    fi

    generate_recyclarr_secrets

    echo ""
    read -r -p "Sync RELEASE_PLEASE_TOKEN to GitHub Actions secret? (Y/n): " sync_gh
    if [ "${sync_gh:-Y}" != "n" ]; then
        sync_github_secrets
    fi

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

    if [ ! -f "$ENV_FILE" ]; then
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        log_warning "Created .env from template. Please edit with actual values."
    fi

    validate_docker
    validate_env_file
    validate_compose
    validate_directories

    create_secrets_dir
    generate_secrets
    generate_recyclarr_secrets
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
    cd "$SCRIPT_DIR/.." || exit 1

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
