# Usage: stack-rating-mdblist <imdb-id>
function stack-rating-mdblist --description 'A title MDBList score + IMDb sub-rating'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-mdblist <imdb-id>" >&2
        return 1
    end
    # MDBList lookup is custom logic in the control panel
    echo "This function requires archived control panel logic. Not yet migrated." && return 1
    echo "This function requires the control panel backend (archived). Not yet migrated to direct API calls." && return 1
end
