# Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>
function stack-arr-toggle-search --description 'Toggle RSS sync + automatic search'
    if test (count $argv) -ne 2
        echo "Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>" >&2
        return 1
    end

    set -l apps
    if test "$argv[1]" = "all"
        set apps radarr sonarr
    else
        set -l app (__stack_arr_app $argv[1])
        or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
        set apps $app
    end

    for app in $apps
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        curl -sf -X POST "$url/api/v3/command" \
            -H "X-Api-Key: $key" \
            -H "Content-Type: application/json" \
            -d '{"name": "RssSync"}' >/dev/null 2>&1
        if test $status -eq 0
            fmt_success "RssSync triggered on $app."
        else
            fmt_error "Failed to trigger RssSync on $app."
        end
    end
end
