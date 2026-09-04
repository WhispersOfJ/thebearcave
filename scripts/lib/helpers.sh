#!/usr/bin/env bash
# Shared helpers for The Bear Cave setup modules.
#
# These modules are bash-only (arrays, [[ ]], process substitution). When
# sourced from a non-bash shell (for example `newgrp -c` on a zsh login),
# zsh leaks `local value; value=$(...)` loop values to stdout — including
# secret values read from .env. Refuse loudly instead of running degraded.
if [ -z "${BASH_VERSION:-}" ]; then
    echo "error: scripts/lib/* must be sourced from bash (found ${ZSH_VERSION:-non-bash})" >&2
    # return-if-sourced / exit-if-executed idiom; shellcheck flags the exit
    # branch as unreachable, but it fires when the file is executed directly.
    # shellcheck disable=SC2317
    return 1 2>/dev/null || exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# shellcheck disable=SC2034 # consumed by the modules that source this file
SECRETS_DIR="secrets"
# shellcheck disable=SC2034
ENV_FILE=".env"
# shellcheck disable=SC2034
ENV_TEMPLATE=".env.template"

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

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
