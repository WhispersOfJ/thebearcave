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
#   unit:         offline renderer tests — mock wanted/missing + movie JSON
#                 through the real stack-arr-missing-aired sonarr/radarr
#                 paths, asserting '?'-title degradation and monitored +
#                 missing + available filtering
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
# Pin the repo root for the loader: bearcave-bash.sh honors a pre-set
# BEARCAVE_REPO_DIR, and an ambient value (e.g. an interactive shell's
# export pointing at the main checkout) would silently source the wrong
# functions/ tree when this suite runs from a worktree.
export BEARCAVE_REPO_DIR="$REPO_DIR"
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

# --- Unit: stack-arr-missing-aired sonarr renderer (offline) ---
# Feed mock wanted/missing JSON through the real function with a dead
# SONARR_URL so the in-python series fetch fails and titles degrade to '?'
# (the renderer's documented fallback). The bash-side fetch is mocked so the
# test never touches the network and runs in CI. On the pre-fix renderer this
# fails (empty SERIES_MAP crashed json.loads), so it pins the rework.
log_info "unit: stack-arr-missing-aired sonarr renderer (mock wanted/missing)..."
mock_file="$(mktemp)"
trap 'rm -f "$mock_file"' EXIT
printf '%s' '{"records":[{"seriesId":42,"seasonNumber":3,"episodeNumber":7,"title":"The Test"},{"seriesId":7,"seasonNumber":1,"episodeNumber":2,"title":"Second"}],"totalRecords":3}' > "$mock_file"
unit_out="$(SONARR_URL='http://127.0.0.1:1' SONARR_API_KEY='mock-key' STACK_COLOR=false bash -c '
    MOCK_FILE="$2"
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    # Replace the curl wrapper: emit the mock payload so the bash side never
    # touches the network; the python renderer still tries the dead
    # SONARR_URL and degrades to "?" titles.
    __stack_curl() { cat "$MOCK_FILE"; }
    "$3" sonarr 5
' _ "$BASH_DIR/bearcave-bash.sh" "$mock_file" stack-arr-missing-aired 2>&1)" && rc=0 || rc=$?
rm -f "$mock_file"
if [ "$rc" -eq 0 ] \
    && printf '%s' "$unit_out" | grep -q '? S03E07 The Test' \
    && printf '%s' "$unit_out" | grep -q '? S01E02 Second' \
    && printf '%s' "$unit_out" | grep -q '... and 1 more' \
    && ! printf '%s' "$unit_out" | grep -q 'Cannot reach'; then
    passed=$((passed + 1))
    log_success "unit: missing-aired renderer degrades to '?' titles on dead series URL"
else
    failed=$((failed + 1))
    log_error "unit: missing-aired renderer output unexpected (rc=$rc):"
    printf '%s\n' "$unit_out" | tail -8 | sed 's/^/         /'
fi

# --- Unit: stack-arr-missing-aired radarr renderer (offline) ---
# Feed mock movie JSON through the real function and assert the filter
# (monitored AND no file AND available) keeps only the right titles; the
# excluded dimensions (unmonitored / already-has-file / not-yet-available)
# must not appear. Bash-side fetch is mocked, so no network (CI-safe).
log_info "unit: stack-arr-missing-aired radarr renderer (mock movies)..."
radarr_mock="$(mktemp)"
printf '%s' '[{"title":"Available Miss","year":2020,"monitored":true,"hasFile":false,"isAvailable":true},{"title":"Not Yet Aired","year":2025,"monitored":true,"hasFile":false,"isAvailable":false},{"title":"Already Have","year":2019,"monitored":true,"hasFile":true,"isAvailable":true},{"title":"Unmonitored","year":2021,"monitored":false,"hasFile":false,"isAvailable":true},{"title":"Second Miss","year":2024,"monitored":true,"hasFile":false,"isAvailable":true}]' > "$radarr_mock"
radarr_out="$(RADARR_API_KEY='mock-key' STACK_COLOR=false bash -c '
    MOCK_FILE="$2"
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    # Replace the curl wrapper: emit the mock payload so the bash side never
    # touches the network (the radarr renderer only filters stdin).
    __stack_curl() { cat "$MOCK_FILE"; }
    "$3" radarr 1
' _ "$BASH_DIR/bearcave-bash.sh" "$radarr_mock" stack-arr-missing-aired 2>&1)" && rc=0 || rc=$?
rm -f "$radarr_mock"
if [ "$rc" -eq 0 ] \
    && printf '%s' "$radarr_out" | grep -q 'Available Miss (2020)' \
    && printf '%s' "$radarr_out" | grep -q '... and 1 more' \
    && printf '%s' "$radarr_out" | grep -q '2 item(s) missing.' \
    && ! printf '%s' "$radarr_out" | grep -q 'Not Yet Aired' \
    && ! printf '%s' "$radarr_out" | grep -q 'Already Have' \
    && ! printf '%s' "$radarr_out" | grep -q 'Unmonitored' \
    && ! printf '%s' "$radarr_out" | grep -q 'Cannot reach'; then
    passed=$((passed + 1))
    log_success "unit: missing-aired radarr filter keeps monitored+missing+available only"
else
    failed=$((failed + 1))
    log_error "unit: missing-aired radarr filter unexpected (rc=$rc):"
    printf '%s\n' "$radarr_out" | tail -8 | sed 's/^/         /'
fi

# --- Unit: stack-requests Seerr renderer (offline) ---
# Feed mock count + request JSON through the real function with the curl
# wrapper mocked; assert the verdict ladder against Seerr's real enums
# (server/constants/media.ts: request 1 PENDING, 2 APPROVED, 3 DECLINED,
# 4 FAILED, 5 COMPLETED; media 1 UNKNOWN .. 5 AVAILABLE): only the open
# pipeline (pending/approved) renders, an approved request whose media is
# already available shows as available-now, and declined/failed/completed
# requests never appear.
log_info "unit: stack-requests Seerr renderer (mock requests)..."
seerr_counts_mock="$(mktemp)"
seerr_list_mock="$(mktemp)"
printf '%s' '{"total":10,"movie":6,"tv":4,"pending":0,"approved":2,"declined":1,"failed":0,"processing":1,"available":0,"completed":6}' > "$seerr_counts_mock"
printf '%s' '{"pageInfo":{"pages":1,"pageSize":10,"results":6,"page":1},"results":['\
'{"id":1,"status":2,"type":"movie","media":{"title":null,"tmdbId":41264,"status":3},"requestedBy":{"plexUsername":"RequesterA"}},'\
'{"id":2,"status":2,"type":"movie","media":{"title":"Watchable Now","tmdbId":77,"status":5},"requestedBy":{"plexUsername":"RequesterD"}},'\
'{"id":3,"status":1,"type":"tv","media":{"title":null,"tvdbId":55,"status":2},"requestedBy":{"plexUsername":"RequesterF"}},'\
'{"id":4,"status":5,"type":"movie","media":{"title":"Closed And Available","tmdbId":99,"status":5},"requestedBy":{"plexUsername":"RequesterB"}},'\
'{"id":5,"status":3,"type":"movie","media":{"title":"Declined Flick","tmdbId":123,"status":3},"requestedBy":{"plexUsername":"RequesterE"}},'\
'{"id":6,"status":4,"type":"tv","media":{"title":"Failed Show","tmdbId":456,"status":3},"requestedBy":{"plexUsername":"RequesterG"}}]}' > "$seerr_list_mock"
seerr_out="$(SEERR_API_KEY='mock-key' STACK_COLOR=false bash -c '
    COUNTS="$2" LIST="$3"
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    # Both endpoints go through __seerr_api ($1=METHOD, $2=path): serve the
    # count payload for the count call, the list payload for the list call.
    __seerr_api() {
        case "$2" in
            *"request/count"*) cat "$COUNTS" ;;
            *) cat "$LIST" ;;
        esac
    }
    "$4" 10
' _ "$BASH_DIR/bearcave-bash.sh" "$seerr_counts_mock" "$seerr_list_mock" stack-requests 2>&1)" && rc=0 || rc=$?
rm -f "$seerr_counts_mock" "$seerr_list_mock"
if [ "$rc" -eq 0 ] \
    && printf '%s' "$seerr_out" | grep -q 'total=10 pending=0 approved=2 declined=1 failed=0' \
    && printf '%s' "$seerr_out" | grep -q '\[movie\] tmdb:41264 - by RequesterA (processing)' \
    && printf '%s' "$seerr_out" | grep -q '\[tv\] tvdb:55 - by RequesterF (pending)' \
    && printf '%s' "$seerr_out" | grep -q 'Watchable Now - by RequesterD (available now)' \
    && ! printf '%s' "$seerr_out" | grep -q 'Closed And Available' \
    && ! printf '%s' "$seerr_out" | grep -q 'Declined Flick' \
    && ! printf '%s' "$seerr_out" | grep -q 'Failed Show' \
    && ! printf '%s' "$seerr_out" | grep -q 'RequesterB'; then
    passed=$((passed + 1))
    log_success "unit: requests renderer surfaces open + available-now, hides closed"
else
    failed=$((failed + 1))
    log_error "unit: requests renderer output unexpected (rc=$rc):"
    printf '%s\n' "$seerr_out" | tail -10 | sed 's/^/         /'
fi

# --- Unit: stack-unwatched Plex renderer (offline) ---
# Feed mock section + item JSON through the real function with the curl
# wrapper mocked on the request URL; assert: movie libraries render their
# 30-day-fresh unwatched items with ages, non-media libraries (artist) are
# skipped entirely, and items older than the 30-day window appear only in
# the counts — never as rows.
log_info "unit: stack-unwatched Plex renderer (mock sections)..."
plex_sections_mock="$(mktemp)"
plex_items_mock="$(mktemp)"
printf '%s' '{"MediaContainer":{"Directory":['\
'{"key":"1","title":"Movies","type":"movie"},'\
'{"key":"3","title":"Music","type":"artist"}]}}' > "$plex_sections_mock"
printf '{"MediaContainer":{"Metadata":[{"title":"Fresh Flick","year":2026,"addedAt":%s},{"title":"Old Flick","year":1985,"addedAt":%s}]}}' \
    "$(date -d '-2 days' +%s)" "$(date -d '-40 days' +%s)" > "$plex_items_mock"
plex_out="$(PLEX_TOKEN='mock-token' STACK_COLOR=false bash -c '
    SECTIONS="$2" ITEMS="$3"
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    __stack_curl() {
        local url="${*: -1}"
        case "$url" in
            *"/library/sections?"*) cat "$SECTIONS" ;;
            *"/library/sections/"*"/unwatched?"*) cat "$ITEMS" ;;
        esac
    }
    "$4" 5
' _ "$BASH_DIR/bearcave-bash.sh" "$plex_sections_mock" "$plex_items_mock" stack-unwatched 2>&1)" && rc=0 || rc=$?
rm -f "$plex_sections_mock" "$plex_items_mock"
if [ "$rc" -eq 0 ] \
    && printf '%s' "$plex_out" | grep -q '\[Movies\]' \
    && printf '%s' "$plex_out" | grep -q 'Fresh Flick (2026) - added 2d ago' \
    && printf '%s' "$plex_out" | grep -q '(1 of 2 unwatched added within the last 30 days)' \
    && ! printf '%s' "$plex_out" | grep -q '\[Music\]' \
    && ! printf '%s' "$plex_out" | grep -q 'Old Flick'; then
    passed=$((passed + 1))
    log_success "unit: unwatched renderer lists 30-day-fresh, skips non-media libraries"
else
    failed=$((failed + 1))
    log_error "unit: unwatched renderer output unexpected (rc=$rc):"
    printf '%s\n' "$plex_out" | tail -10 | sed 's/^/         /'
fi

# --- Unit: stack-arrival-notify --help prints usage (offline) ---
# The wrapper is thin (python core carries the logic, unit-tested in
# scripts/test_arrival_notifier.py) — pin its interface: --help must print
# usage and exit 0 without touching the network or the stack.
log_info "unit: stack-arrival-notify --help prints usage..."
arr_help_out="$(bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    "$2" --help
' _ "$BASH_DIR/bearcave-bash.sh" stack-arrival-notify 2>&1)" && rc=0 || rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$arr_help_out" | grep -q 'Usage: stack-arrival-notify'; then
    passed=$((passed + 1))
    log_success "unit: arrival-notify --help prints usage (exit 0)"
else
    failed=$((failed + 1))
    log_error "unit: arrival-notify --help unexpected (rc=$rc): [$arr_help_out]"
fi

# --- Unit: stack-activity-feed refuses >1 arg (offline) ---
# stack-activity-feed takes at most one positional arg (the print limit);
# extra args must be refused with usage on stderr and exit 1.
log_info "unit: stack-activity-feed refuses extra args..."
feed_usage_out="$(bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    "$2" 5 bogus
' _ "$BASH_DIR/bearcave-bash.sh" stack-activity-feed 2>&1)" && rc=0 || rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$feed_usage_out" | grep -q 'Usage: stack-activity-feed'; then
    passed=$((passed + 1))
    log_success "unit: activity-feed refuses >1 arg with usage (exit 1)"
else
    failed=$((failed + 1))
    log_error "unit: activity-feed usage unexpected (rc=$rc): [$feed_usage_out]"
fi

# --- Unit: __stack_containers docker timeout (offline) ---
# A wedged Docker daemon must not hang completion: stub a slow `docker`
# binary earlier in PATH and assert __stack_containers returns within the
# STACK_DOCKER_TIMEOUT budget (empty output) instead of hanging. Uses the
# already-sourced loader, so no network or real docker is needed (CI-safe).
log_info "unit: __stack_containers returns within STACK_DOCKER_TIMEOUT..."
fake_bin="$(mktemp -d)"
printf '#!/bin/bash\nsleep 30\n' > "$fake_bin/docker"
chmod +x "$fake_bin/docker"
docker_t0=$SECONDS
docker_out="$(PATH="$fake_bin:$PATH" STACK_DOCKER_TIMEOUT=2 __stack_containers 2>&1)" && rc=0 || rc=$?
docker_elapsed=$((SECONDS - docker_t0))
rm -rf "$fake_bin"
# rc is 124 under set -o pipefail (timeout(1) surfaces through the pipeline)
# or 0 in an interactive shell — both mean the call was cut at the budget.
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 124 ]; } \
    && [ "$docker_elapsed" -le 5 ] && [ -z "$docker_out" ]; then
    passed=$((passed + 1))
    log_success "unit: __stack_containers cut at STACK_DOCKER_TIMEOUT (${docker_elapsed}s, empty output)"
else
    failed=$((failed + 1))
    log_error "unit: __stack_containers docker timeout (rc=$rc, ${docker_elapsed}s, output=[$docker_out])"
fi

# --- Unit: __arr_api_key unset message names the real var (offline) ---
# With the key unset the helper must name SONARR_API_KEY (uppercase), not the
# lowercase app-prefixed form — the old message sent users hunting for a
# nonexistent "sonarr_API_KEY" during stale-key debugging.
log_info "unit: __arr_api_key unset message names SONARR_API_KEY..."
key_msg="$(SONARR_API_KEY='' STACK_COLOR=false bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    unset SONARR_API_KEY
    __arr_api_key sonarr
' _ "$BASH_DIR/bearcave-bash.sh" 2>&1)" && rc=0 || rc=$?
if [ "$rc" -eq 1 ] \
    && printf '%s' "$key_msg" | grep -q 'SONARR_API_KEY' \
    && ! printf '%s' "$key_msg" | grep -q 'sonarr_API_KEY'; then
    passed=$((passed + 1))
    log_success "unit: __arr_api_key unset message names SONARR_API_KEY"
else
    failed=$((failed + 1))
    log_error "unit: __arr_api_key unset message unexpected (rc=$rc): [$key_msg]"
fi

# --- Unit: stale arr key/URL warning (offline) ---
# A pre-set key that differs from .env must produce a warning naming the var;
# a matching pre-set value and a missing .env must stay silent. Uses a
# throwaway fixture .env via BEARCAVE_REPO_DIR so the result is deterministic
# in CI (dummy .env) and locally (real .env).
log_info "unit: stale arr key warning fires on mismatch, silent on match..."
stale_tmp="$(mktemp -d)"
printf 'SONARR_API_KEY=real-key\nRADARR_URL=http://real:7878\n' > "$stale_tmp/.env"
stale_out="$(SONARR_API_KEY='stale-key' RADARR_URL='http://real:7878' \
    BEARCAVE_REPO_DIR="$stale_tmp" STACK_COLOR=false bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    __bearcave_warn_stale_keys
' _ "$BASH_DIR/bearcave-bash.sh" 2>&1)" && rc=0 || rc=$?
match_out="$(SONARR_API_KEY='real-key' RADARR_URL='http://real:7878' \
    BEARCAVE_REPO_DIR="$stale_tmp" STACK_COLOR=false bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    __bearcave_warn_stale_keys
' _ "$BASH_DIR/bearcave-bash.sh" 2>&1)" && rc=0 || rc=$?
noenv_out="$(SONARR_API_KEY='stale-key' BEARCAVE_REPO_DIR="$(mktemp -d)" \
    STACK_COLOR=false bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    __bearcave_warn_stale_keys
' _ "$BASH_DIR/bearcave-bash.sh" 2>&1)" && rc=0 || rc=$?
rm -rf "$stale_tmp"
if printf '%s' "$stale_out" | grep -q 'SONARR_API_KEY' \
    && ! printf '%s' "$stale_out" | grep -q 'RADARR_URL' \
    && [ -z "$match_out" ] && [ -z "$noenv_out" ]; then
    passed=$((passed + 1))
    log_success "unit: stale arr key warning fires on mismatch, silent on match"
else
    failed=$((failed + 1))
    log_error "unit: stale arr key warning unexpected (stale=[$stale_out] match=[$match_out] noenv=[$noenv_out])"
fi

# --- Unit: stack-arr-clear-blocklist posts the ClearBlocklist command ---
# The old implementation DELETEd /api/v3/blocklist, which *arr rejects with
# 405 (collection-wide DELETE unsupported). The supported clear is the async
# ClearBlocklist command. Stub __stack_curl to capture the invocation and
# assert it POSTs to /command with the command name (no DELETE).
log_info "unit: clear-blocklist posts the ClearBlocklist command..."
clear_tmp="$(mktemp)"
CAPTURE_FILE="$clear_tmp" RADARR_API_KEY='mock-key' \
    RADARR_URL='http://127.0.0.1:1' STACK_COLOR=false bash -c '
    # shellcheck disable=SC1091
    source "$1" >/dev/null 2>&1
    # The function redirects the curl call to /dev/null, so capture the
    # invocation via CAPTURE_FILE instead of stdout.
    __stack_curl() { printf "%s" "$*" > "$CAPTURE_FILE"; return 0; }
    stack-arr-clear-blocklist radarr
' _ "$BASH_DIR/bearcave-bash.sh" >/dev/null 2>&1; rc=$?
clear_capture="$(cat "$clear_tmp")"
rm -f "$clear_tmp"
if [ "$rc" -eq 0 ] \
    && printf '%s' "$clear_capture" | grep -q -- '-X POST' \
    && printf '%s' "$clear_capture" | grep -q 'api/v3/command' \
    && printf '%s' "$clear_capture" | grep -q 'ClearBlocklist' \
    && ! printf '%s' "$clear_capture" | grep -q -- '-X DELETE'; then
    passed=$((passed + 1))
    log_success "unit: clear-blocklist posts the ClearBlocklist command"
else
    failed=$((failed + 1))
    log_error "unit: clear-blocklist invocation unexpected (rc=$rc): [$clear_capture]"
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
        # shellcheck disable=SC2034  # read by sourced fmt_* helpers in the inner shell
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
    stack-container stack-cutoff-unmet stack-disk-reclaim stack-import-lists \
    stack-loop-candidates \
    stack-loop-exclude stack-loop-unmonitor stack-radarr-prune \
    stack-sonarr-prune stack-worktree; do
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
    run_live stack-maintenance-digest
    run_live stack-audit-residue
    run_live stack-config-drift
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
    run_live stack-watchable
    run_live stack-unwatched 5
    run_live stack-recent 3
    run_live stack-requests 5
    run_live stack-activity-feed 3
    run_live stack-arrival-notify --dry-run
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
