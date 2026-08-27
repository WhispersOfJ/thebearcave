# Usage: stack-top [cpu|mem] [limit]
function stack-top --description 'Top containers by CPU or memory usage'
    set -l by cpu
    set -l limit 10
    if test (count $argv) -ge 1; and contains -- $argv[1] cpu mem
        set by $argv[1]
    end
    if test (count $argv) -ge 2
        set limit $argv[2]
    end
    __stack_api GET "/api/v2/cli/top?by=$by&limit=$limit"
end
