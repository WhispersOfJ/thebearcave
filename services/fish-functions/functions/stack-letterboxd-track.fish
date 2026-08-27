# Usage: stack-letterboxd-track <list-url> [--label TEXT]
function stack-letterboxd-track --description 'Register a Letterboxd list for nightly sync'
    if test (count $argv) -lt 1
        echo "Usage: stack-letterboxd-track <list-url> [--label TEXT]" >&2
        return 1
    end
    set -l url $argv[1]
    set -l label ""
    set -l idx (contains -i -- --label $argv)
    if test -n "$idx"
        set -l next (math $idx + 1)
        set label $argv[$next]
    end
    __stack_api POST "/api/v2/cli/letterboxd/track?url=$url&label=$label"
end
