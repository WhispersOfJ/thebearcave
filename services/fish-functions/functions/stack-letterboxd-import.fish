# Usage: stack-letterboxd-import <type> <url-or-path> [--limit N]
function stack-letterboxd-import --description 'Import Letterboxd content to Radarr'
    if test (count $argv) -lt 2
        echo "Usage: stack-letterboxd-import <type> <url-or-path> [--limit N]" >&2
        echo "Types: film, list, watchlist, watched, collection, filmography, popular, random" >&2
        return 1
    end
    set -l type $argv[1]
    set -l list_url $argv[2]

    set -l limit 10
    set -l idx (contains -i -- --limit $argv)
    if test -n "$idx"
        if test $idx -eq (count $argv)
            echo "--limit given but no value provided" >&2
            return 1
        end
        set limit $argv[(math $idx + 1)]
    end

    fmt_heading "Letterboxd Import ($type)"
    echo ""

    # Accept a full URL or a bare list path
    set -l feed_url "$list_url"
    if not string match -q 'http*' "$list_url"
        set feed_url "https://letterboxd.com/$list_url/"
    end

    set -l rss_url "$feed_url/rss/"
    set -l result (curl -sfL "$rss_url" 2>/dev/null)
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
shown = titles[1:1 + $limit]
for t in shown:
    print(f'  {t}')
if len(titles) - 1 > len(shown):
    print(f'  ... and {len(titles) - 1 - len(shown)} more')
if len(titles) <= 1:
    print('  No items found in feed.')
"
end
