# Usage: stack-plex-empty-trash [library ...]
function stack-plex-empty-trash --description 'Empty trash on one library, or all'
    set -l lib $argv[1]
    test -z "$lib"; and set lib "all"
    __stack_api POST "/api/v2/cli/plex/empty-trash?library=$lib"
end
