# Usage: stack-container <restart|stop|start> <container-name>
function stack-container --description 'Restart/stop/start a single container'
    if test (count $argv) -ne 2; or not contains -- $argv[1] restart stop start
        echo "Usage: stack-container <restart|stop|start> <container-name>" >&2
        return 1
    end
    set -l action $argv[1]
    set -l name $argv[2]

    if not docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx -- "$name"
        fmt_error "No such container: $name"
        return 1
    end

    if docker $action $name >/dev/null 2>&1
        fmt_success "$action on $name."
    else
        fmt_error "Failed to $action $name"
        return 1
    end
end
