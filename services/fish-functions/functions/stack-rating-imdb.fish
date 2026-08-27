# Usage: stack-rating-imdb <imdb-id>
function stack-rating-imdb --description 'A title IMDb rating via OMDb'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-imdb <imdb-id>" >&2
        return 1
    end
    # OMDb lookup is custom logic in the control panel
    # Preserved as __stack_api until extracted to standalone script
    __stack_api GET "/api/v2/cli/rating/imdb/$argv[1]"
end
