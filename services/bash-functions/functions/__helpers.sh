# ============================================================================
# __helpers.sh — internal helpers for the stack-* bash functions
# ============================================================================
# Bash translations of __arr_api.fish, __arr_api_url.fish, __arr_api_key.fish,
# __stack_arr_app.fish, __plex_api.fish, __plex_butler.fish, __seerr_api.fish,
# __nzbdav_api.fish, __stack_containers.fish.
# Sourced by bearcave-bash.sh before the stack-*.sh files.
# ============================================================================

# __arr_api <app> <METHOD> <path> [json_body]
#   app: radarr, sonarr, prowlarr
# Defaults target the host-published ports (host shell: docker service names
# do not resolve). Override with RADARR_URL / SONARR_URL / PROWLARR_URL.
__arr_api() {
    if [ "$#" -lt 3 ]; then
        echo "Usage: __arr_api <app> <METHOD> <path> [json_body]" >&2
        return 1
    fi
    local app="$1" method="$2" path="$3" body="${4:-}"
    local base_url="" api_key=""

    case "$app" in
        radarr)
            base_url="${RADARR_URL:-http://localhost:7878}"
            api_key="$RADARR_API_KEY" ;;
        sonarr)
            base_url="${SONARR_URL:-http://localhost:8989}"
            api_key="$SONARR_API_KEY" ;;
        prowlarr)
            base_url="${PROWLARR_URL:-http://localhost:9696}"
            api_key="$PROWLARR_API_KEY" ;;
        *)
            echo "Unknown app: $app (use radarr, sonarr, or prowlarr)" >&2
            return 1 ;;
    esac

    local opts=(-sS -X "$method" --fail-with-body)
    [ -n "$api_key" ] && opts+=(-H "X-Api-Key: $api_key")
    if [ -n "$body" ]; then
        opts+=(-H 'Content-Type: application/json' -d "$body")
    fi
    curl "${opts[@]}" "$base_url$path"
}

# __arr_api_url <radarr|sonarr|prowlarr>
__arr_api_url() {
    if [ "$#" -lt 1 ]; then
        echo "Usage: __arr_api_url <radarr|sonarr|prowlarr>" >&2
        return 1
    fi
    case "$1" in
        radarr)   echo "${RADARR_URL:-http://localhost:7878}" ;;
        sonarr)   echo "${SONARR_URL:-http://localhost:8989}" ;;
        prowlarr) echo "${PROWLARR_URL:-http://localhost:9696}" ;;
        *) echo "Unknown app: $1 (use radarr, sonarr, or prowlarr)" >&2; return 1 ;;
    esac
}

# __arr_api_key <radarr|sonarr|prowlarr> — fails if unset/empty.
__arr_api_key() {
    if [ "$#" -lt 1 ]; then
        echo "Usage: __arr_api_key <radarr|sonarr|prowlarr>" >&2
        return 1
    fi
    local key=""
    case "$1" in
        radarr)   key="$RADARR_API_KEY" ;;
        sonarr)   key="$SONARR_API_KEY" ;;
        prowlarr) key="$PROWLARR_API_KEY" ;;
        *)
            echo "Unknown app: $1 (use radarr, sonarr, or prowlarr)" >&2
            return 1 ;;
    esac
    if [ -z "$key" ]; then
        echo "API key for $1 not set (expected ${1}_API_KEY uppercase in environment)" >&2
        return 1
    fi
    echo "$key"
}

# __stack_arr_app <name> — validate an Arr instance name (radarr or sonarr).
__stack_arr_app() {
    if [ "$#" -ne 1 ]; then
        return 1
    fi
    case "$1" in
        radarr|sonarr) echo "$1" ;;
        *) return 1 ;;
    esac
}

# __plex_api <METHOD> <path> [json_body]
# Plex runs on host networking: localhost:32400 from the host shell.
__plex_api() {
    if [ "$#" -lt 2 ]; then
        echo "Usage: __plex_api <METHOD> <path> [json_body]" >&2
        return 1
    fi
    local method="$1" path="$2" body="${3:-}"
    local base_url="${PLEX_URL:-http://localhost:32400}"
    local opts=(-sS -X "$method" --fail-with-body -H "Accept: application/json")
    [ -n "$PLEX_TOKEN" ] && opts+=(-H "X-Plex-Token: $PLEX_TOKEN")
    if [ -n "$body" ]; then
        opts+=(-H 'Content-Type: application/json' -d "$body")
    fi
    curl "${opts[@]}" "$base_url$path"
}

# __plex_butler <task-name> — trigger a Plex Maintenance (Butler) task.
__plex_butler() {
    local task="$1"
    if [ -z "$task" ]; then
        echo "Usage: __plex_butler <task-name>" >&2
        return 1
    fi
    local plex_url="${PLEX_URL:-http://localhost:32400}"
    if [ -z "$PLEX_TOKEN" ]; then
        echo "PLEX_TOKEN not set" >&2
        return 1
    fi
    if curl -sf -X POST "$plex_url/butler?task=$task&X-Plex-Token=$PLEX_TOKEN" >/dev/null 2>&1; then
        fmt_success "Butler task '$task' triggered."
    else
        fmt_error "Failed to trigger butler task '$task'."
        return 1
    fi
}

# __seerr_api <METHOD> <path> [json_body]
__seerr_api() {
    if [ "$#" -lt 2 ]; then
        echo "Usage: __seerr_api <METHOD> <path> [json_body]" >&2
        return 1
    fi
    local method="$1" path="$2" body="${3:-}"
    local base_url="${SEERR_URL:-http://localhost:5055}"
    if [ -z "$SEERR_API_KEY" ]; then
        echo "SEERR_API_KEY not set" >&2
        return 1
    fi
    local opts=(-sS -X "$method" --fail-with-body -H "X-Api-Key: $SEERR_API_KEY")
    if [ -n "$body" ]; then
        opts+=(-H 'Content-Type: application/json' -d "$body")
    fi
    # normalize slashes on both sides (parity with __seerr_api.fish)
    base_url="${base_url#/}"; base_url="${base_url%/}"
    path="${path#/}"; path="${path%/}"
    curl "${opts[@]}" "$base_url/$path"
}

# __nzbdav_api <METHOD> <mode> [extra_params]
# NzbDAV uses SABnzbd-compatible API: /api?mode=<mode>&output=json&apikey=<key>
__nzbdav_api() {
    if [ "$#" -lt 2 ]; then
        echo "Usage: __nzbdav_api <METHOD> <mode> [extra_params]" >&2
        return 1
    fi
    local method="$1" mode="$2" extra="${3:-}"
    local base_url="${NZBDAV_URL:-http://localhost:3000}"
    local opts=(-sS -X "$method" --fail-with-body)
    local query="mode=$mode&output=json"
    [ -n "$FRONTEND_BACKEND_API_KEY" ] && query="$query&apikey=$FRONTEND_BACKEND_API_KEY"
    [ -n "$extra" ] && query="$query&$extra"
    curl "${opts[@]}" "$base_url/api?$query"
}

# __stack_containers — live container names (completion helper).
__stack_containers() {
    docker ps -a --format '{{.Names}}' 2>/dev/null | sort
}
