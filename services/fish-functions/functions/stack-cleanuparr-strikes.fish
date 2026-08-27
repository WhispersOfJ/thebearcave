# Usage: stack-cleanuparr-strikes [limit]
function stack-cleanuparr-strikes --description 'Recent stalled/slow/malware strikes'
    set -l limit 15
    test (count $argv) -ge 1; and set limit $argv[1]
    __cleanuparr_api GET "api/v1/strikes?limit=$limit"
end
