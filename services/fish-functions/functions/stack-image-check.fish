function stack-image-check --description 'Check pinned images for newer registry digest'
    __stack_api GET /api/v2/host/image-check
end
