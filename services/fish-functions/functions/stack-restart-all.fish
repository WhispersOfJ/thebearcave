# Usage: stack-restart-all [-y|--yes]
function stack-restart-all --description 'Restart the whole stack (confirms first)'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'This restarts EVERY container in the stack. Continue? [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    if not command -q docker
        fmt_error "docker not found"
        return 1
    end

    set -l containers (docker ps -q 2>/dev/null)
    if test (count $containers) -eq 0
        fmt_warning "No running containers."
        return 0
    end

    fmt_heading "Restarting (count $containers) container(s)"
    if docker restart $containers >/dev/null 2>&1
        fmt_success "Restarted (count $containers) container(s)."
    else
        fmt_error "Restart failed — run 'docker compose ps' to check state."
        return 1
    end
end
