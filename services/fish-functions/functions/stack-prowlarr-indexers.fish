function stack-prowlarr-indexers --description 'Every indexer enabled state + priority'
    __stack_api GET /api/v2/host/image-check
end
