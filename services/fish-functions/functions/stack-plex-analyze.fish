# Usage: stack-plex-analyze [library ...]
function stack-plex-analyze --description 'Queue deep media analysis'
    set -l lib $argv[1]
    test -z "$lib"; and set lib "all"
    __stack_api POST "/api/v2/cli/plex/analyze?library=$lib"
end
