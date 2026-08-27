# Usage: stack-container <restart|stop|start> <container-name>
function stack-container --description 'Restart/stop/start a single container'
    if test (count $argv) -ne 2; or not contains -- $argv[1] restart stop start
        echo "Usage: stack-container <restart|stop|start> <container-name>" >&2
        return 1
    end
    set -l action $argv[1]
    set -l name $argv[2]

    set -l sock "/var/run/controlpanel-helper.sock"
    if not test -S "$sock"
        fmt_error "Host helper socket not found at $sock"
        return 1
    end

    set -l response (echo "{\"action\":\"$action\",\"name\":\"$name\"}" | timeout 30 socat - UNIX-CONNECT:"$sock" 2>/dev/null)
    if test $status -eq 0
        echo "$response"
    else
        fmt_error "Failed to $action $name"
        return 1
    end
end
