# Usage: stack-arr-clear-blocklist <radarr|sonarr> [-y|--yes]
function stack-arr-clear-blocklist --description 'Clear every blocklisted release'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-clear-blocklist <radarr|sonarr> [-y|--yes]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P "Clear ALL blocklisted items on $app? [y/N] " confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end
    __stack_api DELETE "/api/v2/cli/arr/$app/blocklist"
end
