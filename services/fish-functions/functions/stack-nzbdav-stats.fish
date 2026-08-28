function stack-nzbdav-stats --description 'Show NzbDAV aggregate queue/history counts'
    fmt_heading "NzbDAV Stats"
    echo ""

    set -l queue (__nzbdav_api GET queue 2>/dev/null | python3 -c '
import sys, json
try:
    q = json.load(sys.stdin).get("queue", {})
    print(q.get("noofslots", len(q.get("slots", []))))
except Exception:
    print("?")
')
    set -l history (__nzbdav_api GET history 2>/dev/null | python3 -c '
import sys, json
try:
    h = json.load(sys.stdin).get("history", {})
    print(h.get("noofslots", len(h.get("slots", []))))
except Exception:
    print("?")
')

    if test "$queue" = "?" -o "$history" = "?"
        fmt_error "Cannot reach NzbDAV API"
        return 1
    end
    fmt_kv "Queue items" "$queue"
    fmt_kv "History entries (recent)" "$history"
end
