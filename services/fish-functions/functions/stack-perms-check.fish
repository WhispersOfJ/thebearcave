function stack-perms-check --description 'Config files unreadable by group/other'
    __stack_api GET /api/v2/cli/perms-check
end
