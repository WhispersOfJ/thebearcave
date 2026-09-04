#!/usr/bin/env bash
# Install a daily systemd user timer that snapshots the repo to Dropbox via
# scripts/backup_dropbox.py (streaming tar — nothing kept on disk).
#
# The service runs as the invoking user (the stack runs as this user), reads
# the Dropbox credentials from ~/.config/thebearcave-dropbox.env, and logs to
# the user journal:
#     journalctl --user -u thebearcave-dropbox-backup.service -e
#
# Fail-closed: refuses to install when the target repo cannot actually run
# the backup (missing engine, missing python3/requests, missing/incomplete
# credentials file) — never wire a timer that fails silently every night.
#
# Usage:
#   scripts/install-dropbox-backup-timer.sh                 # install (idempotent)
#   scripts/install-dropbox-backup-timer.sh --repo DIR      # target another checkout
#   scripts/install-dropbox-backup-timer.sh --remove        # remove the timer
#   scripts/install-dropbox-backup-timer.sh --check         # report installed state
#   scripts/install-dropbox-backup-timer.sh -h|--help
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UNIT_PREFIX="thebearcave-dropbox-backup"
SERVICE="$UNIT_PREFIX.service"
TIMER="$UNIT_PREFIX.timer"
SCHEDULE="*-*-* 02:30:00"
CREDS_FILE="$HOME/.config/thebearcave-dropbox.env"
UNIT_DIR="$HOME/.config/systemd/user"

usage() {
    cat <<'EOF'
Install/remove the daily thebearcave Dropbox backup user timer (02:30).

usage: install-dropbox-backup-timer.sh [options]

options:
  --repo DIR   target checkout (default: the repo this script lives in)
  --remove     remove the installed timer + service units
  --check      report whether the timer is installed (exit 0/1)
  -h, --help   show this help
EOF
}

repo="$ROOT"
action="install"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo) repo="${2:?--repo needs a path}"; shift 2 ;;
        --remove) action="remove"; shift ;;
        --check) action="check"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown option: $1 (see --help)" >&2; exit 2 ;;
    esac
done

if ! command -v systemctl >/dev/null 2>&1; then
    echo "error: systemctl not found — systemd required for user timers" >&2
    exit 1
fi

engine="$repo/scripts/backup_dropbox.py"

# ---------------------------------------------------------------------------
# Credentials file — create a template on first install, never store secrets
# in the repo.
# ---------------------------------------------------------------------------
ensure_creds_file() {
    if [ -f "$CREDS_FILE" ]; then
        return 0
    fi
    mkdir -p "$(dirname "$CREDS_FILE")"
    cat > "$CREDS_FILE" <<'EOF'
# Dropbox credentials for the thebearcave backup timer (0600, never commit).
# Create an app at https://www.dropbox.com/developers/apps → Scoped access →
# Full Dropbox → enable files.content.write, then either:
#
#   Simple: generate a long-lived access token (Settings → Access token)
DROPBOX_ACCESS_TOKEN=
#
#   Or the OAuth2 refresh trio (recommended for long-lived unattended use):
# DROPBOX_REFRESH_TOKEN=
# DROPBOX_APP_KEY=
# DROPBOX_APP_SECRET=
EOF
    chmod 600 "$CREDS_FILE"
    echo "created credential template: $CREDS_FILE — fill in a token, then re-run"
}

creds_ready() {
    [ -f "$CREDS_FILE" ] || return 1
    # shellcheck disable=SC1090
    . "$CREDS_FILE"
    if [ -n "${DROPBOX_ACCESS_TOKEN:-}" ]; then
        return 0
    fi
    if [ -n "${DROPBOX_REFRESH_TOKEN:-}" ] && [ -n "${DROPBOX_APP_KEY:-}" ] \
        && [ -n "${DROPBOX_APP_SECRET:-}" ]; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Fail-closed validation: the timer must be able to run once installed.
# ---------------------------------------------------------------------------
validate() {
    if [ ! -d "$repo" ]; then
        echo "error: target repo not found: $repo" >&2
        exit 1
    fi
    if [ ! -f "$engine" ]; then
        echo "error: engine not found at $engine — wrong --repo?" >&2
        exit 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "error: python3 not found" >&2
        exit 1
    fi
    if ! python3 -c 'import requests' 2>/dev/null; then
        echo "error: python 'requests' not installed (Arch: pacman -S python-requests)" >&2
        exit 1
    fi
    if ! creds_ready; then
        ensure_creds_file
        echo "error: credentials not ready in $CREDS_FILE" >&2
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Temp-file discipline for unit writes (mirrors the reclaim-cron installer).
# ---------------------------------------------------------------------------
_tmp=""
_rm_tmp() {
    if [ -n "$_tmp" ]; then
        rm -f "$_tmp"
    fi
    return 0
}
trap _rm_tmp EXIT

install_units() {
    validate

    mkdir -p "$UNIT_DIR"

    _tmp="$(mktemp)"
    cat > "$_tmp" <<EOF
[Unit]
Description=The Bear Cave daily Dropbox snapshot (streaming tar)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo
ExecStart=/usr/bin/python3 scripts/backup_dropbox.py
EnvironmentFile=%h/.config/thebearcave-dropbox.env
Nice=10
EOF
    install -m 644 "$_tmp" "$UNIT_DIR/$SERVICE"

    cat > "$_tmp" <<EOF
[Unit]
Description=Daily The Bear Cave Dropbox snapshot (02:30)

[Timer]
OnCalendar=$SCHEDULE
Persistent=true

[Install]
WantedBy=timers.target
EOF
    install -m 644 "$_tmp" "$UNIT_DIR/$TIMER"
    _tmp=""

    systemctl --user daemon-reload
    systemctl --user enable --now "$TIMER"
    echo "installed: $TIMER (runs daily at ${SCHEDULE#*-*-* })"
    echo "  service logs: journalctl --user -u $SERVICE -e"
    echo "  credentials:  $CREDS_FILE"
    echo "  next run:     systemctl --user list-timers $TIMER"
}

remove_units() {
    systemctl --user disable --now "$TIMER" 2>/dev/null || true
    rm -f "$UNIT_DIR/$SERVICE" "$UNIT_DIR/$TIMER"
    systemctl --user daemon-reload
    echo "removed: $TIMER and $SERVICE (credentials at $CREDS_FILE kept)"
}

check_state() {
    local installed=1
    if [ -f "$UNIT_DIR/$TIMER" ] && systemctl --user is-enabled "$TIMER" >/dev/null 2>&1; then
        installed=0
    fi
    if [ "$installed" -eq 0 ]; then
        echo "installed:"
        systemctl --user list-timers "$TIMER" --no-pager 2>/dev/null || true
        if ! creds_ready; then
            echo "warning: credentials missing/incomplete at $CREDS_FILE — next run will fail"
        fi
        exit 0
    fi
    echo "not installed (unit $TIMER not enabled)"
    exit 1
}

case "$action" in
    install) install_units ;;
    remove) remove_units ;;
    check) check_state ;;
esac
