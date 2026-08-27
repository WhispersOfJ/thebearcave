function stack-plex-sessions --description 'Who is watching what right now'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex Sessions"
    echo ""

    set -l result (curl -sf "$plex_url/status/sessions?X-Plex-Token=$token" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach Plex"
        return 1
    end

    set -l sessions (echo "$result" | string match -ra '"title"\s*:\s*"\K[^"]+')
    if test (count $sessions) -eq 0
        fmt_success "No active sessions."
        return
    end

    # Parse with jq-like approach using grep
    echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    items = data.get('MediaContainer', {}).get('Metadata', [])
    if not items:
        print('  No active sessions.')
    for s in items:
        user = s.get('User', {}).get('title', '?')
        title = s.get('title', '?')
        state = s.get('state', '?')
        player = s.get('Player', {}).get('platform', '?')
        print(f'  {user}  {title}  [{state}]  ({player})')
except Exception as e:
    print(f'  Error parsing: {e}')
" 2>/dev/null
end
