# Usage: stack-plex <scan|empty-trash|optimize-db|clean-bundles>
function stack-plex --description 'Trigger a Plex maintenance action'
    if test (count $argv) -ne 1
        echo "Usage: stack-plex <scan|empty-trash|optimize-db|clean-bundles>" >&2
        return 1
    end
    __stack_api POST "/api/v2/cli/plex/$argv[1]"
end
