# Internal helper: validate an Arr instance name (radarr or sonarr).
# Usage: __stack_arr_app <name>
function __stack_arr_app
    argparse container -- $argv
    or return 1
    test (count $argv) -eq 1; or return 1
    switch $argv[1]
        case radarr sonarr
            echo $argv[1]
        case '*'
            return 1
    end
end
