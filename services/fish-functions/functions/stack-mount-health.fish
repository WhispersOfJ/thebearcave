function stack-mount-health --description 'Check every known FUSE mountpoint'
    __stack_api GET /api/v2/cli/mount-health
end
