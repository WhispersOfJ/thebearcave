# Usage: stack-letterboxd-import <type> <url> [--no-search] [--dry-run] [--limit N]
function stack-letterboxd-import --description 'Import Letterboxd content to Radarr'
    if test (count $argv) -lt 2
        echo "Usage: stack-letterboxd-import <type> <url> [--no-search] [--dry-run] [--limit N]" >&2
        echo "Types: film, list, watchlist, watched, collection, filmography, popular, random" >&2
        return 1
    end
    set -l type $argv[1]
    set -l list_url $argv[2]

    fmt_heading "Letterboxd Import ($type)"
    echo ""

    # Fetch the Letterboxd RSS/JSON feed
    set -l feed_url "$list_url"
    if not string match -q 'http*' "$list_url"
        set feed_url "https://letterboxd.com/$list_url/"
    end

    # Try RSS feed
    set -l rss_url "$feed_urlrss/"
    set -l result (curl -sf "$rss_url" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot fetch Letterboxd feed from $rss_url"
        return 1
    end

    # Parse RSS for film titles
    echo "$result" | python3 -c "
import sys, re
xml = sys.stdin.read()
titles = re.findall(r'<title>([^<]+)</title>', xml)
# Skip the first one (feed title)
for t in titles[1:10]:
    print(f'  {t}')
if len(titles) > 11:
    print(f'  ... and {len(titles) - 11} more')
if len(titles) <= 1:
    print('  No items found in feed.')
" 2>/dev/null
end
