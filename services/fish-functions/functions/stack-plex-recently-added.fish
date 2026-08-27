# Usage: stack-plex-recently-added [limit]
function stack-plex-recently-added --description 'What is actually visible in Plex now'
    set -l limit 10
    test (count $argv) -ge 1; and set limit $argv[1]

    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex — Recently Added"
    echo ""

    curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c "
import sys, json, subprocess
try:
    data = json.load(sys.stdin)
    plex_url = '$plex_url'
    token = '$token'
    for section in data.get('MediaContainer', {}).get('Directory', []):
        key = section.get('key')
        title = section.get('title', '?')
        url = f'{plex_url}/library/sections/{key}/all?sort=addedAt:desc&limit=$limit&X-Plex-Token={token}'
        import urllib.request
        r = urllib.request.urlopen(url, timeout=10)
        items = json.loads(r.read()).get('MediaContainer', {}).get('Metadata', [])
        if items:
            print(f'  {title}')
            for item in items[:$limit]:
                name = item.get('title', '?')
                year = item.get('year', '')
                if year:
                    print(f'    {name} ({year})')
                else:
                    print(f'    {name}')
            print()
except Exception as e:
    print(f'  Error: {e}')
" 2>/dev/null
end
