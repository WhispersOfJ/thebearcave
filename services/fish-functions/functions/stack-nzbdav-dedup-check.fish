function stack-nzbdav-dedup-check --description 'Verify api.duplicate-nzb-behavior is mark-failed'
    __stack_api GET /api/v2/cli/nzbdav/dedup-check
end
