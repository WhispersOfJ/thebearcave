# ============================================================================
# stack-plex-extra.sh — Plex maintenance extras
# ============================================================================
# desc: plex duplicates, gc wrappers, updates, image-clean, analyses
# ============================================================================

# stack-plex-duplicates — show duplicate media in Plex
stack-plex-duplicates() {
    local plex_url="${PLEX_URL:-http://localhost:32400}"
    local token="${PLEX_TOKEN:-}"

    fmt_heading "Plex — Duplicates"
    echo ""

    __stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | PLEX_URL="$plex_url" TOKEN="$token" python3 -c "
import sys, json, urllib.request, os
try:
    data = json.load(sys.stdin)
    plex_url = os.environ['PLEX_URL']
    token = os.environ['TOKEN']
    for section in data.get('MediaContainer', {}).get('Directory', []):
        key = section.get('key')
        title = section.get('title', '?')
        url = f'{plex_url}/library/sections/{key}/all?X-Plex-Token={token}'
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        r = urllib.request.urlopen(req, timeout=10)
        items = json.loads(r.read()).get('MediaContainer', {}).get('Metadata', [])
        dupes = {}
        for item in items:
            name = item.get('title', '?')
            dupes.setdefault(name, []).append(item)
        for name, entries in dupes.items():
            if len(entries) > 1:
                print(f'  {title}: {name} ({len(entries)} copies)')
except Exception as e:
    print(f'  Error: {e}')
" 2>/dev/null
}

# --- thin butler task wrappers -----------------------------------------------

stack-plex-garbage-collect-media() {
    __plex_butler garbage-collect-media
}

stack-plex-garbage-collect-blobs() {
    __plex_butler garbage-collect-blobs
}

stack-plex-backup-database() {
    __plex_butler backup-database
}

stack-plex-automatic-updates() {
    __plex_butler automatic-updates
}

stack-plex-process-assets() {
    __plex_butler process-assets
}

stack-plex-refresh-epg() {
    __plex_butler refresh-epg
}

stack-plex-refresh-local-media() {
    __plex_butler refresh-local-media
}

stack-plex-clean-cache-files() {
    __plex_butler clean-cache-files
}

stack-plex-clean-log-files() {
    __plex_butler clean-log-files
}

# stack-plex-image-clean — clean PhotoTranscoder cache, report reclaimed space
stack-plex-image-clean() {
    local output rc recovered
    output="$(docker compose --profile maintenance run --rm --no-deps imagemaid 2>&1)"
    rc=$?
    recovered="$(printf '%s\n' "$output" | grep -m1 'Space Recovered:')"

    if [ $rc -eq 0 ] && [ -n "$recovered" ]; then
        printf '%s\n' "$recovered"
    else
        printf '%s\n' "$output" >&2
    fi
    return $rc
}

# --- analysis wrappers ---------------------------------------------------------

# stack-plex-deep-media-analysis — deep media analysis on all sections
stack-plex-deep-media-analysis() {
    local plex_url="${PLEX_URL:-http://localhost:32400}"
    local token="${PLEX_TOKEN:-}"
    if [ -z "$token" ]; then
        fmt_error "PLEX_TOKEN not set"
        return 1
    fi
    fmt_heading "Plex — Deep Media Analysis"
    echo ""
    local sections failed=0 total=0 key
    sections="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", [])]' 2>/dev/null)"
    if [ -z "$sections" ]; then
        fmt_error "Cannot reach Plex or no libraries found."
        return 1
    fi
    for key in $sections; do
        total=$((total + 1))
        __stack_curl "$STACK_API_TIMEOUT_MUTATE" -sf -X PUT "$plex_url/library/sections/$key/analyze?X-Plex-Token=$token" >/dev/null 2>&1 \
            || failed=$((failed + 1))
    done
    if [ "$failed" -eq 0 ]; then
        fmt_success "Deep analysis triggered for $total section(s)."
    else
        fmt_error "Analysis triggered for $((total - failed)) section(s); $failed failed."
        return 1
    fi
}

# stack-plex-upgrade-media-analysis — upgrade media analysis on all sections
stack-plex-upgrade-media-analysis() {
    local plex_url="${PLEX_URL:-http://localhost:32400}"
    local token="${PLEX_TOKEN:-}"
    if [ -z "$token" ]; then
        fmt_error "PLEX_TOKEN not set"
        return 1
    fi
    fmt_heading "Plex — Upgrade Media Analysis"
    echo ""
    local sections failed=0 total=0 key
    sections="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", [])]' 2>/dev/null)"
    if [ -z "$sections" ]; then
        fmt_error "Cannot reach Plex or no libraries found."
        return 1
    fi
    for key in $sections; do
        total=$((total + 1))
        __stack_curl "$STACK_API_TIMEOUT_MUTATE" -sf -X PUT "$plex_url/library/sections/$key/analyze?X-Plex-Token=$token" >/dev/null 2>&1 \
            || failed=$((failed + 1))
    done
    if [ "$failed" -eq 0 ]; then
        fmt_success "Upgrade media analysis triggered for $total section(s)."
    else
        fmt_error "Analysis triggered for $((total - failed)) section(s); $failed failed."
        return 1
    fi
}

# stack-plex-music-analysis — analyze music libraries
stack-plex-music-analysis() {
    local plex_url="${PLEX_URL:-http://localhost:32400}"
    local token="${PLEX_TOKEN:-}"
    if [ -z "$token" ]; then
        fmt_error "PLEX_TOKEN not set"
        return 1
    fi
    fmt_heading "Plex — Music Analysis"
    echo ""
    local sections key
    sections="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", []) if d.get("type")=="artist"]' 2>/dev/null)"
    if [ -z "$sections" ]; then
        fmt_warning "No music libraries found."
        return 0
    fi
    local failed=0 total=0
    for key in $sections; do
        total=$((total + 1))
        __stack_curl "$STACK_API_TIMEOUT_MUTATE" -sf -X PUT "$plex_url/library/sections/$key/analyze?X-Plex-Token=$token" >/dev/null 2>&1 \
            || failed=$((failed + 1))
    done
    if [ "$failed" -eq 0 ]; then
        fmt_success "Music analysis triggered for $total section(s)."
    else
        fmt_error "Analysis triggered for $((total - failed)) section(s); $failed failed."
        return 1
    fi
}

# stack-plex-loudness-analysis — loudness analysis on music libraries
stack-plex-loudness-analysis() {
    local plex_url="${PLEX_URL:-http://localhost:32400}"
    local token="${PLEX_TOKEN:-}"
    if [ -z "$token" ]; then
        fmt_error "PLEX_TOKEN not set"
        return 1
    fi
    fmt_heading "Plex — Loudness Analysis"
    echo ""
    local sections key failed=0 total=0
    sections="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", []) if d.get("type")=="artist"]' 2>/dev/null)"
    if [ -z "$sections" ]; then
        fmt_warning "No music libraries found."
        return 0
    fi
    for key in $sections; do
        total=$((total + 1))
        __stack_curl "$STACK_API_TIMEOUT_MUTATE" -sf -X PUT "$plex_url/library/sections/$key/analyze?X-Plex-Token=$token" >/dev/null 2>&1 \
            || failed=$((failed + 1))
    done
    if [ "$failed" -eq 0 ]; then
        fmt_success "Loudness analysis triggered for $total section(s)."
    else
        fmt_error "Analysis triggered for $((total - failed)) section(s); $failed failed."
        return 1
    fi
}

# stack-plex-generate-media-index — generate media index files
stack-plex-generate-media-index() {
    __plex_butler generate-media-index
}

# stack-plex-generate-voice-activity — generate voice activity
stack-plex-generate-voice-activity() {
    __plex_butler generate-voice-activity
}

# stack-plex-generate-intro-markers — generate intro markers
stack-plex-generate-intro-markers() {
    __plex_butler generate-intro-markers
}

# stack-plex-generate-credits-markers — generate credits markers
stack-plex-generate-credits-markers() {
    __plex_butler generate-credits-markers
}

# stack-plex-generate-ad-markers — generate ad markers
stack-plex-generate-ad-markers() {
    __plex_butler generate-ad-markers
}

# stack-plex-generate-chapter-thumbs — generate chapter thumbnails
stack-plex-generate-chapter-thumbs() {
    __plex_butler generate-chapter-thumbs
}
