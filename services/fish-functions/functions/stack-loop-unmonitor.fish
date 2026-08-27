# Usage: stack-loop-unmonitor <radarr|sonarr> <id> [-y|--yes]
function stack-loop-unmonitor --description 'Unmonitor a confirmed looping item'
    if test (count $argv) -lt 2
        echo "Usage: stack-loop-unmonitor <radarr|sonarr> <id> [-y|--yes]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    set -l id $argv[2]
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P "Unmonitor item $id on $app? [y/N] " confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end
    __stack_api POST "/api/v2/cli/loop/unmonitor?app=$app&id=$id"
end
