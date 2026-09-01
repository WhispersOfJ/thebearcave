# ============================================================================
# stack-arr-1.sh — arr diagnostics (part 1)
# ============================================================================
# desc: arr backlog, blocklist, recently-added, toggle-search commands
# ============================================================================

# stack-arr-backlog <radarr|sonarr> — internal command-queue backlog
stack-arr-backlog() {
# complete: radarr|sonarr
    if [ "$#" -ne 1 ]; then
        echo "Usage: stack-arr-backlog <radarr|sonarr>" >&2
        return 1
    fi
    local app
    app="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }

    local url key result
    url="$(__arr_api_url "$app")"
    key="$(__arr_api_key "$app")" || return 1
    fmt_heading "$app Command Queue"
    echo ""

    local result
    result="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/command?pageSize=50" -H "X-Api-Key: $key" 2>/dev/null)"
    if [ $? -ne 0 ]; then
        fmt_error "Cannot reach $app"
        return 1
    fi

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
cmds = data.get('records', [])
if not cmds:
    print('  Queue is empty.')
else:
    for c in cmds:
        print(f\"  {c.get('name', '?'):<30s} {c.get('status', '?'):<12s} {(c.get('queued', '') or '')[:19]}\")
" 2>/dev/null
}

# stack-arr-recently-added <radarr|sonarr> [limit]
stack-arr-recently-added() {
# complete: radarr|sonarr
    if [ "$#" -lt 1 ]; then
        echo "Usage: stack-arr-recently-added <radarr|sonarr> [limit]" >&2
        return 1
    fi
    local app
    app="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }
    local limit="${2:-10}"

    local url key endpoint result
    url="$(__arr_api_url "$app")"
    key="$(__arr_api_key "$app")" || return 1
    endpoint="movie"
    [ "$app" = sonarr ] && endpoint="series"
    fmt_heading "$app — Recently Added"
    echo ""

    local result
    result="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/$endpoint?pageSize=$limit&sortKey=added&sortDirection=descending" \
        -H "X-Api-Key: $key" 2>/dev/null)"
    if [ $? -ne 0 ]; then
        fmt_error "Cannot reach $app"
        return 1
    fi

    echo "$result" | LIMIT="$limit" python3 -c "
import sys, json, os
data = json.load(sys.stdin)
if isinstance(data, list):
    items = data
else:
    items = data.get('movies', data.get('series', []))
for item in items[:int(os.environ['LIMIT'])]:
    title = item.get('title', '?')
    year = item.get('year', '?')
    has_file = '✓' if item.get('hasFile') else '✗'
    print(f'  [{has_file}] {title} ({year})')
" 2>/dev/null
}

# stack-arr-toggle-search <radarr|sonarr|all> <on|off>
stack-arr-toggle-search() {
# complete: radarr|sonarr|all on|off
    if [ "$#" -ne 2 ]; then
        echo "Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>" >&2
        return 1
    fi
    case "$2" in
        on|off) ;;
        *) echo "Second argument must be on or off (got: $2)" >&2; return 1 ;;
    esac

    local apps
    if [ "$1" = all ]; then
        apps="radarr sonarr"
    else
        apps="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }
    fi

    local app url key count
    for app in $apps; do
        url="$(__arr_api_url "$app")"
        key="$(__arr_api_key "$app")" || return 1
        count="$(STATE="$2" URL="$url" KEY="$key" python3 - <<'PY' 2>/dev/null
import json, os, urllib.request
enable = os.environ['STATE'] == 'on'
base = os.environ['URL']
headers = {'X-Api-Key': os.environ['KEY'], 'Content-Type': 'application/json'}
req = urllib.request.Request(base + '/api/v3/indexer', headers=headers)
indexers = json.load(urllib.request.urlopen(req, timeout=15))
changed = 0
for idx in indexers:
    for f in idx.get('fields', []):
        if f.get('name') in ('enableRss', 'enableAutomaticSearch'):
            f['value'] = enable
    put = urllib.request.Request(base + '/api/v3/indexer/' + str(idx['id']),
                                 data=json.dumps(idx).encode(),
                                 headers=headers, method='PUT')
    urllib.request.urlopen(put, timeout=15)
    changed += 1
print(changed)
PY
)"
        if [ -n "$count" ] && [ "$count" != 0 ]; then
            fmt_success "$app: RSS sync + automatic search turned $2 on $count indexer(s)."
        elif [ -n "$count" ]; then
            fmt_warning "$app: no indexers to update."
        else
            fmt_error "$app: failed to update indexers."
        fi
    done
}

# stack-arr-blocklist <radarr|sonarr> [limit] — recent blocklisted releases
stack-arr-blocklist() {
# complete: radarr|sonarr
    if [ "$#" -lt 1 ]; then
        echo "Usage: stack-arr-blocklist <radarr|sonarr> [limit]" >&2
        return 1
    fi
    local app
    app="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }
    local limit="${2:-20}"

    local url key result
    url="$(__arr_api_url "$app")"
    key="$(__arr_api_key "$app")" || return 1
    fmt_heading "$app — Blocklist"
    echo ""

    local result
    result="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/blocklist?pageSize=$limit&sortKey=date&sortDirection=descending" \
        -H "X-Api-Key: $key" 2>/dev/null)"
    if [ $? -ne 0 ]; then
        fmt_error "Cannot reach $app"
        return 1
    fi

    echo "$result" | LIMIT="$limit" python3 -c "
import sys, json, os
data = json.load(sys.stdin)
items = data.get('records', [])
if not items:
    print('  Blocklist is empty.')
else:
    for item in items[:int(os.environ['LIMIT'])]:
        title = item.get('title', item.get('sourceTitle', '?'))
        date = (item.get('date', '') or '')[:10]
        print(f'  {date}  {title}')
" 2>/dev/null
}

# stack-arr-clear-blocklist <radarr|sonarr>
stack-arr-clear-blocklist() {
# complete: radarr|sonarr
    if [ "$#" -ne 1 ]; then
        echo "Usage: stack-arr-clear-blocklist <radarr|sonarr>" >&2
        return 1
    fi
    local app
    app="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }

    local url key
    url="$(__arr_api_url "$app")"
    key="$(__arr_api_key "$app")" || return 1

    if __stack_curl "$STACK_API_TIMEOUT_MUTATE" -sf -X DELETE "$url/api/v3/blocklist" -H "X-Api-Key: $key" >/dev/null 2>&1; then
        fmt_success "Blocklist cleared for $app."
    else
        fmt_error "Failed to clear blocklist for $app."
        return 1
    fi
}

# stack-arr-missing-aired <radarr|sonarr> [limit]
stack-arr-missing-aired() {
# complete: radarr|sonarr
    if [ "$#" -lt 1 ]; then
        echo "Usage: stack-arr-missing-aired <radarr|sonarr> [limit]" >&2
        return 1
    fi
    local app
    app="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }
    local limit="${2:-30}"

    local url key result
    url="$(__arr_api_url "$app")"
    key="$(__arr_api_key "$app")" || return 1
    fmt_heading "$app — Missing + Aired"
    echo ""

    local result
    if [ "$app" = radarr ]; then
        result="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/movie?pageSize=1000" -H "X-Api-Key: $key" 2>/dev/null)"
        if [ $? -ne 0 ]; then
            fmt_error "Cannot reach $app"
            return 1
        fi
        echo "$result" | LIMIT="$limit" python3 -c "
import sys, json, os
try:
    items = json.load(sys.stdin)
except Exception as e:
    print(f'  Error parsing response: {e}')
    sys.exit(1)
missing = [m for m in items if m.get('monitored') and not m.get('hasFile') and m.get('isAvailable')]
if not missing:
    print('  Nothing missing that has been released.')
else:
    for m in missing[:int(os.environ['LIMIT'])]:
        print(f\"  {m.get('title', '?')} ({m.get('year', '?')})\")
    if len(missing) > int(os.environ['LIMIT']):
        print(f\"\n  ... and {len(missing) - int(os.environ['LIMIT'])} more\")
    print(f\"\n  {len(missing)} item(s) missing.\")
"
    else
        # Sonarr: the wanted/missing endpoint is already monitored + aired
        # episodes (the bare /missing endpoint returns 401 on current Sonarr).
        # Episode records do not embed the series, so resolve titles from
        # /api/v3/series.
        local series_map
        series_map="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/series?pageSize=1000" -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c "import sys,json; print(json.dumps({s['id']: s.get('title','?') for s in json.load(sys.stdin)}))" 2>/dev/null)"
        result="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/wanted/missing?pageSize=$limit&sortKey=airDateUtc&sortDirection=descending" \
            -H "X-Api-Key: $key" 2>/dev/null)"
        if [ $? -ne 0 ]; then
            fmt_error "Cannot reach $app"
            return 1
        fi
        echo "$result" | SERIES_MAP="$series_map" LIMIT="$limit" python3 -c "
import sys, json, os
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f'  Error parsing response: {e}')
    sys.exit(1)
series = json.loads(os.environ.get('SERIES_MAP', '{}'))
records = data.get('records', [])
total = data.get('totalRecords', len(records))
if not records:
    print('  Nothing missing that has aired.')
else:
    for e in records[:int(os.environ['LIMIT'])]:
        sid = e.get('seriesId')
        series_title = series.get(str(sid), series.get(sid, '?'))
        season = e.get('seasonNumber', 0)
        number = e.get('episodeNumber', 0)
        title = e.get('title', '?')
        print(f\"  {series_title} S{season:02d}E{number:02d} {title}\")
    if total > len(records):
        print(f\"\n  ... and {total - len(records)} more\")
        print(f\"\n  {total} episode(s) missing.\")
"
    fi
}

# stack-cutoff-unmet <radarr|sonarr> [limit]
stack-cutoff-unmet() {
# complete: radarr|sonarr
    if [ "$#" -lt 1 ]; then
        echo "Usage: stack-cutoff-unmet <radarr|sonarr> [limit]" >&2
        return 1
    fi
    local app
    app="$(__stack_arr_app "$1")" || { echo "Invalid app: $1" >&2; return 1; }
    local limit="${2:-10}"

    local url key result
    url="$(__arr_api_url "$app")"
    key="$(__arr_api_key "$app")" || return 1
    fmt_heading "$app — Cutoff Unmet"
    echo ""

    local result
    result="$(__stack_curl "$STACK_API_TIMEOUT_LIGHT" -sf "$url/api/v3/wanted/cutoff?pageSize=$limit" -H "X-Api-Key: $key" 2>/dev/null)"
    if [ $? -ne 0 ]; then
        fmt_error "Cannot reach $app"
        return 1
    fi

    echo "$result" | LIMIT="$limit" python3 -c "
import sys, json, os
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f'  Error parsing response: {e}')
    sys.exit(1)
records = data.get('records', [])
total = data.get('totalRecords', len(records))
if not records:
    print('  Nothing is below its quality cutoff.')
else:
    for item in records[:int(os.environ['LIMIT'])]:
        if 'series' in item:
            ep = item.get('episode', {})
            title = item.get('series', {}).get('title', '?')
            label = f\"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d} {ep.get('title', '?')}\"
        else:
            title = item.get('title', '?')
            label = f\"({item.get('year', '?')})\"
        print(f'  {title} {label}')
    if total > len(records):
        print(f'\n  ... and {total - len(records)} more')
    print(f'\n  {total} item(s) below cutoff.')
"
}
