# Usage: stack-loop-unmonitor <radarr|sonarr> <id> [-y|--yes]
function stack-loop-unmonitor --description 'Unmonitor a confirmed looping item'
    if test (count $argv) -lt 2
        echo "Usage: stack-loop-unmonitor <radarr|sonarr> <id> [-y|--yes]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin
        echo "Invalid app: $argv[1]" >&2
        return 1
    end
    set -l id $argv[2]
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P "Unmonitor item $id on $app? [y/N] " confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    set -l endpoint movie
    test "$app" = sonarr; and set endpoint series

    # Get current item, then update monitored=false
    set -l item (curl -sf "$url/api/v3/$endpoint/$id" -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot fetch item $id from $app"
        return 1
    end

    echo "$item" | python3 -c "
import sys, json, subprocess
item = json.load(sys.stdin)
item['monitored'] = False
subprocess.run([
    'curl', '-sf', '-X', 'PUT', '$url/api/v3/$endpoint/$id',
    '-H', 'X-Api-Key: $key',
    '-H', 'Content-Type: application/json',
    '-d', json.dumps(item)
], capture_output=True)
print(f'  Unmonitored: {item.get(\"title\", \"?\")} on $app')
" 2>/dev/null
end
