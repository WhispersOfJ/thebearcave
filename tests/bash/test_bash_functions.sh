#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Bash Functions Smoke Test
# ============================================================================
# Verifies every bash stack-* function loads and its argument layer works.
# Mirrors tests/fish/test_fish_functions.sh for the bash port.
#
# Tiers:
#   load/define:  every functions/stack-*.sh parses and defines its command
#   helpers:      __helpers.sh loads and defines __arr_api, __plex_api, ...
#   docker guard: the guarded docker() wrapper is present and routes
#   completion:   one completion entry per stack-* command, parses
#   drift:        stack-help listing == readable stack-* file set;
#                 completion set == stack-* command set
#   guard:        mutating/arg-requiring commands invoked with no args on
#                 closed stdin must print usage and exit 0 or 1
#   live:         read-only commands invoked for real against the stack
#                 (skipped under --offline; needs .env + running services)
#
# Usage:
#   ./tests/bash/test_bash_functions.sh            # full suite (offline + live)
#   ./tests/bash/test_bash_functions.sh --offline  # static tiers only (CI-safe)
#   ./tests/bash/test_bash_functions.sh --dry-run  # alias of --offline
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

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BASH_DIR="$REPO_DIR/services/bash-functions"
FUNC_DIR="$BASH_DIR/functions"
COMP_FILE="$BASH_DIR/completions/stack-completions.sh"

cd "$REPO_DIR"

DRY_RUN=false
case "${1:-}" in
    "") ;;
    --offline|--dry-run) DRY_RUN=true ;;
    *) echo "Unknown option: $1 (usage: $0 [--offline|--dry-run])" >&2; exit 2 ;;
esac

passed=0
failed=0

# Source the full loader once into the running shell so the stack-*
# functions, fmt_* helpers, __helpers, and the docker wrapper are all
# defined for the subsequent per-function checks. Keep output quiet.
# Read by the sourced bearcave-bash.sh (fmt_* helpers check STACK_COLOR to
# decide color output); shellcheck cannot see into the sourced file.
# shellcheck disable=SC2034
<<<<<<< HEAD
# Read by the sourced bearcave-bash.sh (fmt_* helpers check STACK_COLOR to
# decide color output); shellcheck cannot see into the sourced file.
# shellcheck disable=SC2034
=======
>>>>>>> f115fd0 (test: pass CI shellcheck on bash smoke test (SC2034 annotated, SC2016 documented))
STACK_COLOR=false
# shellcheck disable=SC1091
source "$BASH_DIR/bearcave-bash.sh" >/dev/null 2>&1

# Assert a bash function with the given name is defined in the current shell.
#   assert_defined <name> <label>
assert_defined() {
    local name="$1" label="$2"
    if declare -F "$name" >/dev/null 2>&1; then
        passed=$((passed + 1))
        log_success "defines: $label"
    else
        failed=$((failed + 1))
        log_error "defines: $label (function missing)"
    fi
}

echo ""
echo "=========================================="
echo "  Bash Functions Smoke Test"
echo "=========================================="
echo ""

# Ensure bash is present (it is — this script is bash) but guard the loader.
if [ ! -f "$BASH_DIR/bearcave-bash.sh" ]; then
    log_error "bearcave-bash.sh not found at $BASH_DIR"
    exit 1
fi

# --- Load/define checks: every functions/stack-*.sh parses + defines its command ---
log_info "Load/define checks (every file must parse and define its commands)..."

# Syntax-check every function file first (parity with CI's bash -n sweep).
load_fail=0
for f in "$FUNC_DIR"/*.sh "$BASH_DIR"/bearcave-bash.sh "$BASH_DIR"/completions/*.sh; do
    [ -f "$f" ] || continue
    if ! bash -n "$f" 2>/dev/null; then
        load_fail=$((load_fail + 1))
        log_error "syntax: $(basename "$f")"
    fi
done
if [ "$load_fail" -eq 0 ]; then
    passed=$((passed + 1))
    log_success "all function files parse (bash -n)"
else
    failed=$((failed + load_fail))
fi

# Collect the set of stack-* commands the files define.
mapfile -t STACK_CMDS < <(
    for f in "$FUNC_DIR"/stack-*.sh; do
        grep -oE '^stack-[a-z0-9-]+\(\)' "$f" 2>/dev/null | sed 's/()$//'
    done | sort -u
)
if [ "${#STACK_CMDS[@]}" -eq 0 ]; then
    failed=$((failed + 1))
    log_error "no stack-* commands found in $FUNC_DIR"
else
    passed=$((passed + 1))
    log_success "${#STACK_CMDS[@]} stack-* commands defined across function files"
fi

# fmt_* helpers + internal helpers from __helpers.sh
for h in fmt_heading fmt_success fmt_error fmt_warning fmt_dim fmt_status_dot fmt_kv \
         __arr_api __arr_api_url __arr_api_key __stack_arr_app \
         __plex_api __plex_butler __seerr_api __nzbdav_api __stack_containers \
         __stack_curl; do
    assert_defined "$h" "$h"
done

# The guarded docker() wrapper is a function (not the binary).
if declare -F docker >/dev/null 2>&1; then
    passed=$((passed + 1))
    log_success "guarded docker() wrapper is defined"
else
    failed=$((failed + 1))
    log_error "guarded docker() wrapper is missing (loader did not define it)"
fi

# --- Completion checks: one file, parses, registers completions ---
log_info "Completion checks (single generated file parses and registers)..."

if [ ! -f "$COMP_FILE" ]; then
    failed=$((failed + 1))
    log_error "completion file missing: $COMP_FILE"
else
    # Parse check
    if bash -n "$COMP_FILE" 2>/dev/null; then
        passed=$((passed + 1))
        log_success "completion file parses (bash -n)"
    else
        failed=$((failed + 1))
        log_error "completion file fails to parse"
    fi

    # Registers a __stack_complete function and complete -D entries
    if declare -F __stack_complete >/dev/null 2>&1; then
        passed=$((passed + 1))
        log_success "__stack_complete is defined"
    else
        failed=$((failed + 1))
        log_error "__stack_complete is not defined (completion file did not load)"
    fi
fi

# --- stack-help drift: its listing must match the readable stack-*.sh file set ---
# stack-help enumerates functions/stack-*.sh files and prints each file's
# basename as a category (from the `# desc:` header), so a renamed file
# without an updated help would silently drop out. The bash port groups many
# commands per file, so help lists file basenames, not individual functions.
log_info "stack-help drift check (output must match the stack-*.sh file set)..."
help_output="$(STACK_COLOR=false stack-help 2>/dev/null)" || true
# Expected: basenames of readable functions/stack-*.sh minus the .sh extension.
expected="$(for f in "$FUNC_DIR"/stack-*.sh; do
    [ -r "$f" ] || continue
    basename "$f" .sh
done | sort)"
# Actual: first whitespace-delimited token of each non-header line.
actual="$(printf '%s\n' "$help_output" | grep -E '^  stack-' | awk '{print $1}' | sort)"
if [ "$expected" = "$actual" ] && [ -n "$expected" ]; then
    passed=$((passed + 1))
    log_success "stack-help lists exactly the stack-*.sh files ($(printf '%s\n' "$expected" | wc -l | tr -d ' ') categories)"
else
    failed=$((failed + 1))
    log_error "stack-help output drifted from the stack-*.sh file set"
    echo "       in stack-help but no matching file:" | sed 's/^/       /'
    comm -13 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | sed 's/^/         - /'
    echo "       file exists but missing from stack-help:" | sed 's/^/       /'
    comm -23 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | sed 's/^/         - /'
fi

# --- Completion drift: gen-bash-completions --check must report current ---
log_info "completion drift check (gen-bash-completions.sh --check)..."
if bash "$BASH_DIR/scripts/gen-bash-completions.sh" --check >/dev/null 2>&1; then
    passed=$((passed + 1))
    log_success "completions are current (no drift)"
else
    failed=$((failed + 1))
    log_error "completions are out of date — run gen-bash-completions.sh"
fi

# --- Timeout coverage: every curl API call routes through __stack_curl ---
# A bare `curl -sf` in a function file is a hang risk (landmine). Assert none
# remain outside __helpers.sh (which owns the wrapper) and the embedded
# python subprocess arg lists (which carry inline --max-time).
log_info "timeout coverage check (no bare curl -sf outside the wrapper)..."
bare="$(grep -rn 'curl -sf' "$FUNC_DIR" 2>/dev/null \
    | grep -v '__stack_curl' \
    | grep -v "'curl'" || true)"
if [ -z "$bare" ]; then
    passed=$((passed + 1))
    log_success "every curl -sf site routes through __stack_curl"
else
    failed=$((failed + 1))
    log_error "bare curl -sf sites remain (hang risk):"
    printf '%s\n' "$bare" | sed 's/^/         - /' | head -10
fi

# run_live <command> [args...]
# TIER 1 (live): invoke a read-only command against the running stack.
# Pass = exit code 0 or 1 (1 is a clean handled-error like "key not set" or
# "Cannot reach <app>"). A hang or crash (exit >=2, or timeout 124) fails.
# Sources .env + the loader in a subshell so the command sees real API keys.
run_live() {
    local name="$1"; shift
    local output rc
    # Optional per-call timeout as $1 when it starts with a digit (e.g.
    # "run_live stack-disk-config-sizes 120"), else use the default budget.
    local budget="$SMOKE_TIMEOUT"
    if [ "$#" -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
        budget="$1"; shift
    fi
    # Pass args as positional parameters to the inner script so multi-word
    # args (e.g. a release title) survive intact. The single-quoted script is
    # intentional: $1/$@ must expand inside the inner shell, not here
    # (shellcheck SC2016 is expected and correct here).
    # shellcheck disable=SC2016
    output="$(timeout "$budget" bash -c '
        STACK_COLOR=false
        # .env may reference unset vars; source it with -u off so the
        # loader sees real API keys without tripping set -u.
        if [ -f "$1" ]; then
            set +u; set -a; source "$1"; set +a; set -u
        fi
        shift
        source "$1" >/dev/null 2>&1
        shift
        "$@"
    ' _ "$REPO_DIR/.env" "$BASH_DIR/bearcave-bash.sh" "$name" "$@" 2>&1)" && rc=0 || rc=$?
    if [ "$rc" -le 1 ]; then
        passed=$((passed + 1))
        log_success "live: $name $* (exit $rc)"
    else
        failed=$((failed + 1))
        log_error "live: $name $* (exit $rc)"
        printf '%s\n' "$output" | tail -5 | sed 's/^/         /'
    fi
}

# --- Guard tier: mutating/arg-requiring commands must refuse cleanly with no args ---
# Mirrors the fish TIER 2. Invoke with no args on closed stdin; the command
# must print usage and exit 0 or 1 (not hang, not crash).
log_info "Guard tier (no-args invocations must print usage and exit cleanly)..."

# run_guard <command>
run_guard() {
    local name="$1"
    local output rc
    output="$(timeout 20 bash -c "
        STACK_COLOR=false
        source '$BASH_DIR/bearcave-bash.sh' >/dev/null 2>&1
        $name
    " </dev/null 2>&1)" && rc=0 || rc=$?
    if [ "$rc" -le 1 ] && [ -n "$output" ]; then
        passed=$((passed + 1))
        log_success "guard: $name (exit $rc, refused with output)"
    else
        failed=$((failed + 1))
        log_error "guard: $name (exit $rc, $([ -n "$output" ] && echo 'had output' || echo 'no output'))"
        printf '%s\n' "$output" | tail -3 | sed 's/^/         /'
    fi
}

# Arg-requiring commands (subset that needs >=1 arg and prints usage when starved).
for cmd in \
    stack-arr stack-arr-backlog stack-arr-blocklist stack-arr-clear-blocklist \
    stack-arr-import stack-arr-import-all stack-arr-import-candidates \
    stack-arr-import-starvation stack-arr-logs stack-arr-missing-aired \
    stack-arr-queue-errors stack-arr-recently-added stack-arr-toggle-search \
    stack-container stack-cutoff-unmet stack-import-lists stack-loop-candidates \
    stack-loop-exclude stack-loop-unmonitor stack-worktree; do
    # only guard commands that are actually defined
    if printf '%s\n' "${STACK_CMDS[@]}" | grep -qx "$cmd"; then
        run_guard "$cmd"
    fi
done

# stack-restart-all prompts for confirmation; with no stdin it must decline.
if printf '%s\n' "${STACK_CMDS[@]}" | grep -qx stack-restart-all; then
    run_guard stack-restart-all
fi

# --- TIER 1: live read-only commands (skipped under --offline) ---
# Mirrors the fish TIER 1. Each command runs against the real stack with a
# per-call timeout; exit 0 or 1 passes (1 = clean handled-error).
if [ "$DRY_RUN" = true ]; then
    log_warning "Offline mode — skipping live tier (CI-safe)."
elif [ ! -f "$REPO_DIR/.env" ]; then
    log_warning "No $REPO_DIR/.env — skipping live tier (run from the main checkout to exercise live calls)."
else
    log_info "TIER 1: live read-only invocations..."
    SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-60}"
    run_live stack-status
    run_live stack-version
    run_live stack-help
    run_live stack-top
    run_live stack-docker-disk-usage
    run_live stack-disk-config-sizes 120  # du over multi-GB config dirs
    run_live stack-mount-health
    run_live stack-radarr-health
    run_live stack-plex-markers
    run_live stack-prowlarr-indexers
    run_live stack-command-queue-summary
    run_live stack-backlog-status
    run_live stack-queue-status
    run_live stack-arr-backlog radarr
    run_live stack-arr-blocklist radarr 3
    run_live stack-arr-import-candidates radarr
    run_live stack-cutoff-unmet radarr 3
    run_live stack-arr-missing-aired radarr 5
    run_live stack-arr-recently-added radarr 3
    run_live stack-import-lists radarr
    run_live stack-nzbdav-queue
    run_live stack-nzbdav-history 5
    run_live stack-plex-sessions
    run_live stack-plex-recently-added 2
    run_live stack-plex-duplicates
    run_live stack-loop-candidates sonarr
    run_live stack-arr-queue-errors sonarr
    run_live stack-arr-missing-aired sonarr 5
fi

# --- Summary ---
echo ""
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""
echo "  Passed: $passed"
echo "  Failed: $failed"
echo ""

if [ "$failed" -eq 0 ]; then
    log_success "All bash function smoke tests passed!"
    exit 0
else
    log_error "$failed smoke test(s) failed"
    exit 1
fi
