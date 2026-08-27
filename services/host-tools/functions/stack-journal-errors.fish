function stack-journal-errors --description 'Error-or-worse journal entries since last boot'
    journalctl -p err -b --no-pager -o short-iso 2>/dev/null | tail -50
end
