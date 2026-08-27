function stack-disk-config-sizes --description 'Per-app config directory size, largest first'
    __stack_api GET /api/v2/cli/disk-usage
end
