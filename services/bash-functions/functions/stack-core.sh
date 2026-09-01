# ============================================================================
# stack-core.sh — core stack commands
# ============================================================================
# desc: core stack status, container, restart, top, version, help commands
# ============================================================================

# stack-status — Show live state/health of every container
stack-status() {
    fmt_heading "Container Status"
    echo ""
    docker ps -a --format '{{.Names}}\t{{.State}}\t{{.Status}}' | sort | \
    while IFS=$'\t' read -r name st status_line; do
        printf "  %-25s %s  %s\n" "$name" "$(fmt_status_dot "$st")" "$status_line"
    done
}

# stack-container <restart|stop|start> <name> — control a single container
stack-container() {
# complete: <container> restart|stop|start
    if [ "$#" -ne 2 ]; then
        echo "Usage: stack-container <restart|stop|start> <name>" >&2
        return 1
    fi
    local action="$1" name="$2"
    case "$action" in
        restart|stop|start)
            docker "$action" "$name"
            ;;
        *)
            echo "Unknown action: $action (use restart, stop, or start)" >&2
            return 1
            ;;
    esac
}

# stack-restart-all [-y] — restart the whole stack
stack-restart-all() {
# complete: -y|--yes
    local assume_yes=false
    [ "${1:-}" = "-y" ] && assume_yes=true
    if [ "$assume_yes" != true ]; then
        printf "Restart the whole stack? [y/N] "
        local reply
        read -r reply
        case "$reply" in
            y|Y) assume_yes=true ;;
            *) echo "Aborted."; return 1 ;;
        esac
    fi
    fmt_heading "Restarting stack"
    docker compose restart
    fmt_success "Stack restarted."
}

# stack-top — docker stats snapshot
stack-top() {
    fmt_heading "Container Resources"
    echo ""
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
}

# stack-version — repo + compose image versions
stack-version() {
    fmt_heading "Stack Versions"
    fmt_kv "repo" "$(cd "$BEARCAVE_REPO_DIR" && git log -1 --format='%h %s' 2>/dev/null || echo 'n/a')"
    fmt_kv "docker" "$(docker --version 2>/dev/null | cut -d, -f1 || echo 'n/a')"
    echo ""
    docker compose images 2>/dev/null || fmt_warning "docker compose images failed"
}

# stack-help — list all stack-* commands
stack-help() {
    echo "Bear Cave media stack — terminal commands (bash)"
    echo ""
    local f name desc
    for f in "$BEARCAVE_REPO_DIR/services/bash-functions/functions"/stack-*.sh; do
        [ -r "$f" ] || continue
        name="$(basename "$f" .sh)"
        desc="$(grep -m1 -o "# desc: .*" "$f" 2>/dev/null | sed 's/^# desc: //')"
        if [ -n "$desc" ]; then
            printf "  %-45s %s\n" "$name" "$desc"
        else
            printf "  %s\n" "$name"
        fi
    done
}
