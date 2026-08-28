function stack-plex-empty-trash --description 'Empty Plex trash for all libraries'
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    set -l sections (curl -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
        | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", [])]' 2>/dev/null)
    if test -z "$sections"
        fmt_error "Cannot reach Plex or no libraries found."
        return 1
    end
    set -l failed 0
    for key in $sections
        curl -sf -X PUT "$plex_url/library/sections/$key/emptyTrash?X-Plex-Token=$token" >/dev/null 2>&1
        or set failed (math $failed + 1)
    end
    if test $failed -eq 0
        fmt_success "Trash emptied for (count $sections) section(s)."
    else
        fmt_error "Trash emptied for (math (count $sections) - $failed) section(s); $failed failed."
        return 1
    end
end
