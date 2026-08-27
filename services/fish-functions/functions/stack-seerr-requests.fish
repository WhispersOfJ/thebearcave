# Usage: stack-seerr-requests [pending|approved|available|all]
function stack-seerr-requests --description 'Media requests sitting in Seerr'
    set -l status_filter pending
    test (count $argv) -ge 1; and set status_filter $argv[1]
    __seerr_api GET "api/v1/request?filter=$status_filter"
end
