# Usage: stack-rating-imdb <imdb-id>
function stack-rating-imdb --description 'A title IMDb rating via OMDb'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-imdb <imdb-id>" >&2
        return 1
    end
    __stack_api GET "/api/v2/cli/rating/imdb/$argv[1]"
end
