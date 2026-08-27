function stack-notify-test --description 'Send a test notification via Discord webhook'
    if set -q DISCORD_WEBHOOK_URL
        curl -sf -X POST "$DISCORD_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d '{"content": "🧪 Test notification from The Bear Cave"}' >/dev/null 2>&1
        if test $status -eq 0
            fmt_success "Test notification sent."
        else
            fmt_error "Failed to send notification."
        end
    else
        fmt_warning "DISCORD_WEBHOOK_URL not set."
    end
end
