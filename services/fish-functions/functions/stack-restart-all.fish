# Usage: stack-restart-all [-y|--yes]
function stack-restart-all --description 'Restart the whole stack (confirms first)'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'This restarts EVERY container in the stack. Continue? [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end
    __stack_api POST /api/v2/cli/stack/restart-all
end
