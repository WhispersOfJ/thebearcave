function stack-watchstate-history --description 'Show WatchState watch history'
    set -l title ""
    set -l limit 20
    if test (count $argv) -ge 1
        set title $argv[1]
    end
    if test (count $argv) -ge 2
        set limit $argv[2]
    end
    set -l url "v1/api/history?limit=$limit"
    if test -n "$title"
        set url "$url&title=$title"
    end
    __watchstate_api GET "$url"
end
