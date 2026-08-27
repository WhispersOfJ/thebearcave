function stack-oom-check --description 'Check for OOM-killed containers'
    fmt_heading "OOM Check"
    echo ""
    set -l found 0
    for c in (docker ps -a --format '{{.Names}}')
        set -l oom (docker inspect --format '{{.State.OOMKilled}}' "$c" 2>/dev/null)
        if test "$oom" = "true"
            set found 1
            echo "  "(fmt_status_dot "OOM-killed")"  $c"
        end
    end
    if test $found -eq 0
        fmt_success "No OOM-killed containers."
    end
end
