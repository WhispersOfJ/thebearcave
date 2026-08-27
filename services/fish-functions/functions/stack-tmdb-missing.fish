function stack-tmdb-missing --description 'Scan libraries for items with no TMDb link'
    # Custom cross-service scan logic in the control panel
    # Preserved as __stack_api until extracted to standalone script
    __stack_api GET /api/v2/host/oom-check
end
