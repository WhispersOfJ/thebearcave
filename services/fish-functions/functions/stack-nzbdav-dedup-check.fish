function stack-nzbdav-dedup-check --description 'Detect duplicate entries in NzbDAV download history'
    fmt_heading "NzbDAV Dedup Check"
    echo ""

    set -l result (__nzbdav_api GET history "limit=500" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach NzbDAV API"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
from collections import Counter
try:
    slots = json.load(sys.stdin).get('history', {}).get('slots', [])
except Exception as e:
    print(f'  Error parsing history: {e}')
    sys.exit(1)

names = Counter(s.get('name') or s.get('nzb_name', '?') for s in slots)
dupes = [(n, c) for n, c in names.most_common() if c > 1]
if not dupes:
    print('  No duplicate downloads in recent history.')
else:
    total_extra = 0
    for name, count in dupes:
        print(f'  [{count}x] {name}')
        total_extra += count - 1
    print(f'\\n  {len(dupes)} title(s) duplicated ({total_extra} redundant grab(s)).')
"
end
