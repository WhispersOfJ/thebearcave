function stack-timer-status --description 'Stack timer states and last runs'
    systemctl list-timers --all --no-pager 2>/dev/null | grep -i stack
end
