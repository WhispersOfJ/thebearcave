#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Fish Functions Smoke Test
# ============================================================================
# Verifies every stack-* function loads and its argument layer works.
#
# Two tiers:
#   TIER 1 (live):  read-only commands invoked for real against the stack
#   TIER 2 (guard): mutating/arg-requiring commands invoked with no args —
#                   they must print usage/confirm-prompt and exit cleanly
#
# Deliberately NOT invoked live (would mutate the stack or hang):
#   - the 19 stack-plex-* butler wrappers and stack-plex-butler-all /
#     stack-plex-butler <task>, stack-plex-empty-trash, stack-plex-analyze
#     (covered by load/define checks instead)
#   - stack-notify-test, stack-claude-full-backup
#   - stack-arr-logs (follows the log indefinitely)
#
# Usage:
#   ./tests/fish/test_fish_functions.sh            # full suite (live stack)
#   ./tests/fish/test_fish_functions.sh --offline  # static tier only (CI-safe)
#   ./tests/fish/test_fish_functions.sh --dry-run  # alias of --offline
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
FUNC_DIR="$REPO_DIR/services/fish-functions/functions"
TIMEOUT_SECS="${SMOKE_TIMEOUT:-60}"

cd "$REPO_DIR"

# Export API keys so live calls can authenticate
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

DRY_RUN=false
case "${1:-}" in
    "") ;;
    --dry-run | --offline) DRY_RUN=true ;;
    *)
        echo "Unknown option: $1 (usage: $0 [--dry-run|--offline])" >&2
        exit 2
        ;;
esac

passed=0
failed=0

# Preload helper files so a command sourced in isolation sees the same
# environment install.sh creates (helpers on the function path, fmt_* via
# conf.d).
preload_helpers() {
    local h out=""
    for h in "$FUNC_DIR"/__*.fish; do
        out="$out
source '$h'"
    done
    printf '%s\n' "$out"
}

# run_live <function-file-basename> <args...>
# TIER 1: invoke a read-only command against the live stack.
# Pass = exit code 0 or 1 (1 is a clean handled-error like "key not set").
run_live() {
    local file="$1"
    shift
    local name="${file%.fish}"
    local output rc preload
    preload=$(preload_helpers)
    output=$(timeout "$TIMEOUT_SECS" fish -c "
        $preload
        source '$FUNC_DIR/$file'
        $name \$argv
    " "$@" 2>&1) && rc=0 || rc=$?
    if [ "$rc" -le 1 ]; then
        passed=$((passed + 1))
        log_success "live: $file $* (exit $rc)"
    else
        failed=$((failed + 1))
        log_error "live: $file $* (exit $rc)"
        echo "$output" | tail -5 | sed 's/^/       /'
    fi
}

# run_guard <function-file-basename>
# TIER 2: invoke with no args on closed stdin; the command must refuse
# cleanly (usage text or confirmation decline), exiting 0 or 1.
run_guard() {
    local file="$1"
    local name="${file%.fish}"
    local output rc preload
    preload=$(preload_helpers)
    output=$(timeout 20 fish -c "
        $preload
        source '$FUNC_DIR/$file'
        $name
    " </dev/null 2>&1) && rc=0 || rc=$?
    if [ "$rc" -le 1 ] && [ -n "$output" ]; then
        passed=$((passed + 1))
        log_success "guard: $name (exit $rc, refused with output)"
    else
        failed=$((failed + 1))
        log_error "guard: $name (exit $rc)"
        echo "$output" | tail -3 | sed 's/^/       /'
    fi
}

# check_defines <file> — load the file, assert its command function exists.
# Used for commands excluded from live invocation.
check_defines() {
    local file="$1"
    local name="${file%.fish}"
    if fish -c "source '$FUNC_DIR/$file'; functions -q '$name'" 2>/dev/null; then
        passed=$((passed + 1))
        log_success "defines: $name"
    else
        failed=$((failed + 1))
        log_error "defines: $name (function missing or file fails to load)"
    fi
}

# ============================================================================
# Main
# ============================================================================

echo ""
echo "=========================================="
echo "  Fish Functions Smoke Test"
echo "=========================================="
echo ""

if ! command -v fish >/dev/null; then
    log_error "fish is not installed"
    exit 1
fi

# --- Load/define checks for every installable command ---
log_info "Load/define checks (every file must define its command)..."
load_fail=0
for f in "$FUNC_DIR"/*.fish; do
    base=$(basename "$f")
    name="${base%.fish}"
    [ "$name" = "__cli_format" ] && continue
    if ! fish -c "source '$f'; functions -q '$name'" 2>/dev/null; then
        load_fail=$((load_fail + 1))
        log_error "load/define: $base"
    fi
done
if [ "$load_fail" -eq 0 ]; then
    passed=$((passed + 1))
    log_success "all commands define their function"
else
    failed=$((failed + load_fail))
fi

# fmt_* helper library loads
if fish -c "source '$FUNC_DIR/__cli_format.fish'; functions -q fmt_success" 2>/dev/null; then
    passed=$((passed + 1))
    log_success "fmt_* helpers load from __cli_format.fish"
else
    failed=$((failed + 1))
    log_error "fmt_* helpers do not load"
fi

# conf.d env loader loads the repo .env so stack-* commands get API keys
# without manual export. Scrub the key from the environment so the check
# exercises the loader, not the inherited env.
if [ -f ".env" ]; then
    if env -u SONARR_API_KEY -u RADARR_API_KEY fish -c "source '$REPO_DIR/services/fish-functions/conf.d/bearcave-env.fish'; test -n \"\$SONARR_API_KEY\"" 2>/dev/null; then
        passed=$((passed + 1))
        log_success "conf.d env loader exports keys from .env"
    else
        failed=$((failed + 1))
        log_error "conf.d env loader does not export keys from .env"
    fi
else
    log_warning "conf.d env loader check skipped (no .env)"
fi

# --- Completion files: one per command, parseable, registering >=1 completion ---
log_info "Completion checks (one file per command)..."
COMP_DIR="$REPO_DIR/services/fish-functions/completions"
comp_fail=0
for f in "$FUNC_DIR"/stack-*.fish; do
    base=$(basename "$f")
    name="${base%.fish}"
    cfile="$COMP_DIR/$base"
    if [ ! -f "$cfile" ]; then
        comp_fail=$((comp_fail + 1))
        log_error "completion missing: $name"
        continue
    fi
    if ! fish --no-execute "$cfile" 2>/dev/null; then
        comp_fail=$((comp_fail + 1))
        log_error "completion parse failure: $name"
        continue
    fi
    if ! fish -c "source '$cfile'; test (count (complete -c '$name')) -ge 1" 2>/dev/null; then
        comp_fail=$((comp_fail + 1))
        log_error "completion registers nothing: $name"
    fi
done
if [ "$comp_fail" -eq 0 ]; then
    passed=$((passed + 1))
    log_success "all completions present, parse, and register"
else
    failed=$((failed + comp_fail))
fi

# --- stack-help drift: its listing must match the readable stack-* set ---
# stack-help enumerates stack-*.fish files (skipping unreadable ones, e.g.
# dangling symlinks), so a retired/renamed command without a pruned file
# would silently drop out of help. Assert the two sets are identical.
log_info "stack-help drift check (output must match readable stack-* set)..."
preload=$(preload_helpers)
help_output=$(timeout 20 fish -c "
    $preload
    source '$FUNC_DIR/stack-help.fish'
    stack-help
" 2>&1) || true
# Expected: basenames of readable stack-*.fish minus the .fish extension.
expected=$(for f in "$FUNC_DIR"/stack-*.fish; do
    [ -r "$f" ] || continue
    basename "$f" .fish
done | sort)
# Actual: command names stack-help prints (skip the 2-line header, take the
# first whitespace-delimited token of each remaining line).
actual=$(printf '%s
' "$help_output" | tail -n +3 | awk '{print $1}' | sort)
if [ "$expected" = "$actual" ] && [ -n "$expected" ]; then
    passed=$((passed + 1))
    log_success "stack-help lists exactly the readable stack-* commands ($(printf '%s\n' "$expected" | wc -l | tr -d ' ') commands)"
else
    failed=$((failed + 1))
    log_error "stack-help output drifted from the readable stack-* file set"
    echo "       in stack-help but not on disk:" | sed 's/^/       /'
    comm -13 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | sed 's/^/         - /'
    echo "       missing from stack-help:" | sed 's/^/       /'
    comm -23 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | sed 's/^/         - /'
fi

# --- Completion drift: exactly one completion file per stack-* command ---
# gen-completions.fish emits one completion file per command, so the
# completion set must equal the function set in both directions: a command
# without a completion file loses tab-completion silently, and an orphaned
# completion file hints at a retired command that was never swept. Assert
# the two sets are identical (same readability guard as stack-help).
log_info "completion drift check (one completion file per stack-* command)..."
# Expected: basenames of readable stack-*.fish minus the .fish extension.
expected=$(for f in "$FUNC_DIR"/stack-*.fish; do
    [ -r "$f" ] || continue
    basename "$f" .fish
done | sort)
# Actual: readable completion file basenames minus the .fish extension.
actual=$(for f in "$COMP_DIR"/*.fish; do
    [ -r "$f" ] || continue
    basename "$f" .fish
done | sort)
if [ "$expected" = "$actual" ] && [ -n "$expected" ]; then
    passed=$((passed + 1))
    log_success "completions match the stack-* command set exactly ($(printf '%s\n' "$expected" | wc -l | tr -d ' ') files)"
else
    failed=$((failed + 1))
    log_error "completion files drifted from the stack-* command set"
    echo "       orphaned completion files (no matching command):" | sed 's/^/       /'
    comm -13 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | sed 's/^/         - /'
    echo "       commands missing a completion file:" | sed 's/^/       /'
    comm -23 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | sed 's/^/         - /'
fi

if [ "$DRY_RUN" = true ]; then
    log_warning "Offline mode — skipping live/guard tiers (CI-safe)."
    echo ""
    echo "Results: $passed passed, $failed failed"
    [ "$failed" -eq 0 ] || exit 1
    exit 0
fi

# --- TIER 1: live read-only commands ---
log_info "TIER 1: live read-only invocations..."
run_live stack-status.fish
run_live stack-version.fish
run_live stack-help.fish
run_live stack-image-check.fish
run_live stack-top.fish cpu 3
run_live stack-docker-disk-usage.fish
run_live stack-oom-check.fish
run_live stack-resource-check.fish
run_live stack-mount-health.fish
run_live stack-disk-config-sizes.fish
run_live stack-perms-check.fish
run_live stack-radarr-health.fish
run_live stack-log-levels.fish
run_live stack-letterboxd-tracked.fish
run_live stack-mdblist-tracked.fish
run_live stack-letterboxd-history.fish
run_live stack-mdblist-history.fish
run_live stack-prowlarr-indexers.fish
run_live stack-arr-queue-errors.fish
run_live stack-arr-import-starvation.fish
run_live stack-command-queue-summary.fish
run_live stack-backlog-status.fish
run_live stack-queue-status.fish
run_live stack-arr-backlog.fish radarr
run_live stack-arr-blocklist.fish radarr 3
run_live stack-arr-import-candidates.fish radarr
run_live stack-cutoff-unmet.fish radarr 3
run_live stack-arr-missing-aired.fish radarr 5
run_live stack-arr-recently-added.fish radarr 3
run_live stack-import-lists.fish radarr
run_live stack-nzbdav-queue.fish
run_live stack-nzbdav-history.fish 5
run_live stack-nzbdav-stats.fish
run_live stack-nzbdav-dedup-check.fish
run_live stack-plex-libraries.fish
run_live stack-plex-sessions.fish
run_live stack-plex-updates.fish
run_live stack-plex-recently-added.fish 2
run_live stack-seerr-requests.fish pending
run_live stack-rating-imdb.fish tt0068646
run_live stack-rating-mdblist.fish tt0068646

# --- TIER 2: mutating commands must refuse cleanly with no args ---
log_info "TIER 2: usage-guard invocations (no args, closed stdin)..."
run_guard stack-arr.fish
run_guard stack-arr-missing-aired.fish
run_guard stack-arr-recently-added.fish
run_guard stack-arr-blocklist.fish
run_guard stack-arr-import.fish
run_guard stack-arr-import-all.fish
run_guard stack-arr-import-candidates.fish
run_guard stack-arr-toggle-search.fish
run_guard stack-cutoff-unmet.fish
run_guard stack-container.fish
run_guard stack-restart-all.fish
run_guard stack-queue-autofix.fish
run_guard stack-loop-candidates.fish
run_guard stack-loop-unmonitor.fish
run_guard stack-loop-exclude.fish
run_guard stack-plex.fish
run_guard stack-plex-butler.fish
run_guard stack-mdblist-import.fish
run_guard stack-mdblist-track.fish
run_guard stack-mdblist-untrack.fish
run_guard stack-letterboxd-import.fish
run_guard stack-letterboxd-track.fish
run_guard stack-letterboxd-untrack.fish
run_guard stack-nzbdav-delete-failures.fish
run_guard stack-arr-clear-blocklist.fish

# --- Commands excluded from invocation: define-check only ---
log_info "Define-only checks (mutating Plex commands)..."
check_defines stack-plex-empty-trash.fish
check_defines stack-plex-analyze.fish
check_defines stack-plex-butler-all.fish
check_defines stack-notify-test.fish
check_defines stack-claude-full-backup.fish
for f in "$FUNC_DIR"/stack-plex-*.fish; do
    base=$(basename "$f")
    case "$base" in
        stack-plex.fish|stack-plex-libraries.fish|stack-plex-sessions.fish|\
        stack-plex-updates.fish|stack-plex-duplicates.fish|stack-plex-recently-added.fish|\
        stack-plex-empty-trash.fish|stack-plex-analyze.fish|stack-plex-butler-all.fish|\
        stack-plex-tmdb-missing.fish)
            continue
            ;;
        *)
            # Butler wrappers + clean-* + generate-* etc.
            name="${base%.fish}"
            if fish -c "source '$f'; functions -q '$name'" 2>/dev/null; then
                passed=$((passed + 1))
            else
                failed=$((failed + 1))
                log_error "defines: $name"
            fi
            ;;
    esac
done

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
    log_success "All fish function smoke tests passed!"
    exit 0
else
    log_error "$failed smoke test(s) failed"
    exit 1
fi
