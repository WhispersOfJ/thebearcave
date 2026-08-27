# Usage: stack-plex-duplicates [min_gb]
function stack-plex-duplicates --description 'Movies carrying redundant duplicate files'
    set -l min_gb 2
    test (count $argv) -ge 1; and set min_gb $argv[1]
    __stack_api GET "/api/v2/cli/plex/duplicates?min_gb=$min_gb"
end
