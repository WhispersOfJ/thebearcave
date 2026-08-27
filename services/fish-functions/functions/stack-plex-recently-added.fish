# Usage: stack-plex-recently-added [limit]
function stack-plex-recently-added --description 'What is actually visible in Plex now'
    set -l limit 10
    test (count $argv) -ge 1; and set limit $argv[1]
    __stack_api GET "/api/v2/cli/plex/recently-added?limit=$limit"
end
