function stack-watchstate-status --description 'WatchState system status'
    set -l result (__watchstate_api GET "v1/api/system/healthcheck" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach WatchState"
        return 1
    end
    echo "$result" | python3 -c '
import sys, json
d = json.load(sys.stdin)
state = d.get("status", "?")
label = "healthy" if state == "ok" else state
print("  WatchState: " + label + " - " + d.get("message", ""))
'
end
