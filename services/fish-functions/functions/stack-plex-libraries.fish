function stack-plex-libraries --description 'List Plex library names'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex Libraries"
    echo ""

    curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    dirs = data.get('MediaContainer', {}).get('Directory', [])
    for d in dirs:
        print(f\"  {d.get('title', '?')} ({d.get('type', '?')})\")
except: pass
" 2>/dev/null
end
