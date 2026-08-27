function stack-notify-test --description 'Send a test message to the Discord webhook'
    __stack_api POST /api/v2/cli/notify/test
end
