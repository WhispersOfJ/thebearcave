function stack-perms-check --description 'Check file permissions on config directories'
    fmt_heading "Permissions Check"
    echo ""
    set -l found 0
    for d in /opt/arr /config
        if test -d "$d"
            set -l unreadable (find "$d" -maxdepth 2 ! -readable 2>/dev/null | head -20)
            for f in $unreadable
                set found 1
                echo "  $f"
            end
        end
    end
    if test $found -eq 0
        fmt_success "All config files are readable."
    end
end
