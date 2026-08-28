function stack-tmdb-missing --description 'Scan libraries for items with no TMDb link'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    if test -z "$token"
        fmt_error "PLEX_TOKEN not set"
        return 1
    end

    fmt_heading "TMDb Missing Check"
    echo ""

    # Get all library sections
    set -l sections (curl -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach Plex"
        return 1
    end

    echo "$sections" | python3 -c "
import sys, json, urllib.request

plex_url = '$plex_url'
token = '$token'
data = json.load(sys.stdin)
total_missing = 0

for section in data.get('MediaContainer', {}).get('Directory', []):
    key = section.get('key')
    title = section.get('title', '?')
    stype = section.get('type', '')
    if stype not in ('movie', 'show'):
        continue

    url = f'{plex_url}/library/sections/{key}/all?X-Plex-Token={token}&pageSize=500'
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    r = urllib.request.urlopen(req, timeout=30)
    items = json.loads(r.read()).get('MediaContainer', {}).get('Metadata', [])

    missing = []
    for item in items:
        guids = item.get('Guid', [])
        has_tmdb = any('tmdb' in g.get('id', '').lower() for g in guids)
        if not has_tmdb:
            missing.append(item.get('title', '?'))

    if missing:
        print(f'  {title}: {len(missing)} items without TMDb')
        for m in missing[:10]:
            print(f'    - {m}')
        if len(missing) > 10:
            print(f'    ... and {len(missing) - 10} more')
        total_missing += len(missing)

if total_missing == 0:
    print('  All items have TMDb links.')
else:
    print(f'\n  Total: {total_missing} items without TMDb')
" 2>/dev/null
end
