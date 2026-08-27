# Usage: stack-log-levels [reset]
function stack-log-levels --description 'Check, or reset, every Servarr app log level'
    if test (count $argv) -ge 1; and test "$argv[1]" = reset
        __stack_api POST /api/v2/cli/log-levels
    else
        __stack_api GET /api/v2/cli/log-levels
    end
end
