function stack-plex-empty-trash --description 'Empty Plex trash for all libraries'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    set -l sections (curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | string match -ra 'key="\K[0-9]+')
    for key in $sections
        curl -sf -X PUT "$plex_url/library/sections/$key/emptyTrash?X-Plex-Token=$token" >/dev/null 2>&1
    end
    fmt_success "Trash emptied for all libraries."
end
