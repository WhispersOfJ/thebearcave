# Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>
function stack-arr-toggle-search --description 'Toggle RSS sync + automatic search on indexers'
    if test (count $argv) -ne 2
        echo "Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>" >&2
        return 1
    end

    switch $argv[2]
        case on off
            # validated below in the python payload
        case '*'
            echo "Second argument must be on or off (got: $argv[2])" >&2
            return 1
    end

    set -l apps
    if test "$argv[1]" = all
        set apps radarr sonarr
    else
        set -l app (__stack_arr_app $argv[1])
        or begin
            echo "Invalid app: $argv[1]" >&2
            return 1
        end
        set apps $app
    end

    for app in $apps
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l count (echo "" | python3 -c "
import sys, json, urllib.request
enable = {'on': 'true', 'off': 'false'}['$argv[2]'] == 'true'
base = '$url'
headers = {'X-Api-Key': '$key', 'Content-Type': 'application/json'}
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
" 2>/dev/null)
        if test -n "$count" -a "$count" != 0
            fmt_success "$app: RSS sync + automatic search turned $argv[2] on $count indexer(s)."
        else if test -n "$count"
            fmt_warning "$app: no indexers to update."
        else
            fmt_error "$app: failed to update indexers."
        end
    end
end
