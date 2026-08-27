function stack-resource-check --description 'Show containers missing mem_limit/cpus'
    __stack_api GET /api/v2/cli/resource-check
end
