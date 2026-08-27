function stack-mdblist-tracked --description 'Every MDBList list currently registered'
    __stack_api GET /api/v2/cli/mdblist/tracked
end
