function stack-plex-updates --description 'Check for Plex updates'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex — Updates"
    echo ""

    curl -sf -H "Accept: application/json" "$plex_url/updater/check?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    updates = data.get('MediaContainer', {}).get('Metadata', [])
    if not updates:
        print('  No updates available.')
    for u in updates:
        print(f\"  {u.get('title', '?')} v{u.get('version', '?')}\")
except: pass
" 2>/dev/null
end
