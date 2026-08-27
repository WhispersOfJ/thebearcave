function stack-mdblist-history --description 'Recent MDBList sync runs'
    __stack_api GET /api/v2/cli/mdblist/history
end
