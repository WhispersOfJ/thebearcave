# Usage: stack-seerr-requests [pending|approved|available|all]
function stack-seerr-requests --description 'Media requests sitting in Seerr'
    set -l status pending
    test (count $argv) -ge 1; and set status $argv[1]
    __stack_api GET "/api/v2/cli/seerr/requests?status=$status"
end
