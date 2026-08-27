function stack-plex-duplicates --description 'Show duplicate media in Plex'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex — Duplicates"
    echo ""

    curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c "
import sys, json, urllib.request
try:
    data = json.load(sys.stdin)
    for section in data.get('MediaContainer', {}).get('Directory', []):
        key = section.get('key')
        title = section.get('title', '?')
        url = f'$plex_url/library/sections/{key}/all?X-Plex-Token=$token'
        r = urllib.request.urlopen(url, timeout=10)
        items = json.loads(r.read()).get('MediaContainer', {}).get('Metadata', [])
        dupes = {}
        for item in items:
            name = item.get('title', '?')
            dupes.setdefault(name, []).append(item)
        for name, entries in dupes.items():
            if len(entries) > 1:
                print(f'  {title}: {name} ({len(entries)} copies)')
except Exception as e:
    print(f'  Error: {e}')
" 2>/dev/null
end
