#!/usr/bin/env bash
# GitHub Actions secret sync for The Bear Cave.
# Sources: scripts/lib/helpers.sh

# RELEASE_PLEASE_TOKEN lives in .env for local convenience, but GitHub Actions
# can only read it as a repository Actions secret — the local .env is never
# visible to CI. Keep the two in sync.
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
        echo "  repo Actions secret manually."
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
