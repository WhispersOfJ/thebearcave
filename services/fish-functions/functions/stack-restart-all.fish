# Usage: stack-restart-all [-y|--yes]
function stack-restart-all --description 'Restart the whole stack (confirms first)'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'This restarts EVERY container in the stack. Continue? [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    set -l sock "/var/run/controlpanel-helper.sock"
    if not test -S "$sock"
        fmt_error "Host helper socket not found at $sock"
        return 1
    end

    set -l response (echo '{"action":"restart-all"}' | timeout 120 socat - UNIX-CONNECT:"$sock" 2>/dev/null)
    if test $status -eq 0
        echo "$response"
    else
        fmt_error "Failed to restart stack"
        return 1
    end
end
