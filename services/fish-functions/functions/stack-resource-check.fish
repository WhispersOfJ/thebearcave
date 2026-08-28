function stack-resource-check --description 'Check containers missing mem_limit/cpus'
    fmt_heading "Resource Check"
    echo ""
    set -l found 0
    for c in (docker ps --format '{{.Names}}')
        set -l mem (docker inspect --format '{{.HostConfig.Memory}}' "$c" 2>/dev/null)
        set -l cpus (docker inspect --format '{{.HostConfig.NanoCpus}}' "$c" 2>/dev/null)
        set -l mem_ok "✗"
        set -l cpu_ok "✗"
        if test "$mem" != 0; and test -n "$mem"
            set mem_ok "✓"
        end
        if test "$cpus" != 0; and test -n "$cpus"
            set cpu_ok "✓"
        end
        if test "$mem_ok" = "✗"; or test "$cpu_ok" = "✗"
            set found 1
            echo "  $c  mem=$mem_ok  cpus=$cpu_ok"
        end
    end
    if test $found -eq 0
        fmt_success "All containers have resource limits set."
    end
end
