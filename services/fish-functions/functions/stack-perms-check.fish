function stack-perms-check --description 'Check file permissions on config directories'
    fmt_heading "Permissions Check"
    echo ""
    set -l repo (path resolve (status dirname)/../..)
    set -l found 0
    for d in "$repo/config" "$repo/secrets"
        if test -d "$d"
            set -l unreadable (find "$d" ! -readable 2>/dev/null | head -20)
            for f in $unreadable
                set found 1
                echo "  $f"
            end
        else
            echo "  $d  "(fmt_status_dot "missing")
        end
    end
    if test $found -eq 0
        fmt_success "All config files are readable."
    end
end
