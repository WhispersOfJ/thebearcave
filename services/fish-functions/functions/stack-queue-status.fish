function stack-queue-status --description 'Every app download queue with live-measured speed/ETA'
    __stack_api GET /api/v2/cli/queue/status
end
