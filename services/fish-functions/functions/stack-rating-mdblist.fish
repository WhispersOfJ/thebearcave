# Usage: stack-rating-mdblist <imdb-id>
function stack-rating-mdblist --description 'A title MDBList score + IMDb sub-rating'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-mdblist <imdb-id>" >&2
        return 1
    end
    __stack_api GET "/api/v2/cli/rating/mdblist/$argv[1]"
end
