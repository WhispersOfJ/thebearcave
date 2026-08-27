# Internal helper: call service APIs directly (no control panel).
# Routes based on path prefix to the appropriate per-service helper.
# Falls back to docker CLI for host operations.
#
# Usage: __stack_api METHOD PATH [JSON_BODY]
# Returns plain text. Color is enabled when MEDIA_STACK_COLOR is true.
#
# Migration note: this replaces the old control-panel gateway. Each
# function will eventually call its service helper directly; this
# router exists for backward compatibility during the transition.
function __stack_api
    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    # ── Arr APIs ──────────────────────────────────────────────────
    if string match -q '/api/v2/cli/arr/*' $path
        set -l rest (string replace '/api/v2/cli/arr/' '' $path)
        set -l parts (string split '/' $rest)
        set -l app $parts[1]
        set -l api_path "/"(string join '/' $parts[2..])
        __arr_api $app $method $api_path $body
        return
    end

    # ── Plex API ──────────────────────────────────────────────────
    if string match -q '/api/v2/cli/plex/*' $path
        set -l plex_path (string replace '/api/v2/cli/plex' '' $path)
        test -z "$plex_path"; and set plex_path "/"
        __plex_api $method $plex_path $body
        return
    end

    # ── NzbDAV API ────────────────────────────────────────────────
    if string match -q '/api/v2/cli/nzbdav/*' $path
        set -l nzbdav_path (string replace '/api/v2/cli/nzbdav' '' $path)
        __nzbdav_api $method $nzbdav_path $body
        return
    end

    # ── WatchState API ────────────────────────────────────────────
    if string match -q '/api/v2/cli/watchstate/*' $path
        set -l ws_path (string replace '/api/v2/cli/watchstate' '' $path)
        __watchstate_api $method "/v1/api$ws_path" $body
        return
    end

    # ── Seerr API ─────────────────────────────────────────────────
    if string match -q '/api/v2/cli/seerr/*' $path
        set -l seerr_path (string replace '/api/v2/cli/seerr' '' $path)
        __seerr_api $method "/api/v1$seerr_path" $body
        return
    end

    # ── Cleanuparr API ────────────────────────────────────────────
    if string match -q '/api/v2/cli/cleanuparr/*' $path
        set -l carr_path (string replace '/api/v2/cli/cleanuparr' '' $path)
        __cleanuparr_api $method "$carr_path" $body
        return
    end

    # ── Docker CLI operations (host-level) ────────────────────────

    # Container status
    if test "$path" = "/api/v2/cli/status"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" --no-trunc 2>/dev/null
        return
    end

    # Container action (restart/stop/start)
    if string match -q '/api/v2/cli/container/*' $path
        set -l rest (string replace '/api/v2/cli/container/' '' $path)
        set -l parts (string split '/' $rest)
        set -l name $parts[1]
        set -l action $parts[2]
        switch $action
            case restart
                docker restart $name 2>&1
            case stop
                docker stop $name 2>&1
            case start
                docker start $name 2>&1
            case '*'
                echo "Unknown action: $action" >&2
                return 1
        end
        return
    end

    # Stack restart-all
    if test "$path" = "/api/v2/cli/stack/restart-all"
        # Staged restart in FUSE-safe order
        for c in nzbdav; do docker restart $c 2>&1; sleep 5; end
        for c in nzbdav_rclone; do docker restart $c 2>&1; sleep 5; end
        for c in (docker ps --format '{{.Names}}' | grep -v -E '^(nzbdav|control-panel)$'); do
            docker restart $c 2>&1
        end
        return
    end

    # Top containers
    if string match -q '/api/v2/cli/top*' $path
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null
        return
    end

    # Resource check
    if test "$path" = "/api/v2/cli/resource-check"
        echo "Resource check: use 'docker inspect' for per-container limits"
        docker ps --format '{{.Names}}' | while read -l name
            set -l mem (docker inspect --format '{{.HostConfig.Memory}}' $name 2>/dev/null)
            set -l cpu (docker inspect --format '{{.HostConfig.NanoCpus}}' $name 2>/dev/null)
            test "$mem" = "0"; and set mem "unset"
            test "$cpu" = "0"; and set cpu "unset"
            printf "  %-25s mem=%-10s cpus=%s\n" $name $mem $cpu
        end
        return
    end

    # OOM check
    if test "$path" = "/api/v2/cli/oom-check"
        docker ps --format '{{.Names}}' | while read -l name
            set -l oom (docker inspect --format '{{.State.OOMKilled}}' $name 2>/dev/null)
            test "$oom" = "true"; and echo "  OOM-killed: $name"
        end
        echo "OOM check complete."
        return
    end

    # Disk usage
    if test "$path" = "/api/v2/cli/disk-usage"
        docker system df 2>/dev/null
        return
    end

    # Mount health
    if test "$path" = "/api/v2/cli/mount-health"
        if test -d /mnt/remote/nzbdav
            ls /mnt/remote/nzbdav >/dev/null 2>&1 and echo "  remote/nzbdav: healthy" or echo "  remote/nzbdav: stale"
        else
            echo "  remote/nzbdav: missing"
        end
        return
    end

    # Perms check
    if test "$path" = "/api/v2/cli/perms-check"
        echo "Perms check: scanning config/..."
        find config/ -type f ! -perm -o+r 2>/dev/null | head -20
        return
    end

    # Version
    if test "$path" = "/api/v2/cli/version"
        if test -f "$MEDIA_STACK_DIR/README.md"
            grep -oP 'Current version: \*\*\K[^*]+' "$MEDIA_STACK_DIR/README.md" 2>/dev/null || echo "unknown"
        else
            echo "unknown"
        end
        return
    end

    # Log levels
    if test "$path" = "/api/v2/cli/log-levels"
        if test "$method" = "POST"
            # Reset all to info
            for app in radarr sonarr prowlarr
                set -l url (eval echo \$$app:toupper)_URL
                test -z "$url"; and continue
                set -l key (eval echo \$$app:toupper)_API_KEY
                set -l cfg (curl -sS "$url/api/v3/config/host" -H "X-Api-Key: $key" 2>/dev/null)
                test -z "$cfg"; and continue
                set -l id (echo $cfg | grep -oP '"id":\s*\K\d+')
                set -l level (echo $cfg | grep -oP '"logLevel":\s*"\K[^"]+')
                test "$level" != "debug"; and continue
                curl -sS -X PUT "$url/api/v3/config/host/$id" \
                    -H "X-Api-Key: $key" -H "Content-Type: application/json" \
                    -d (echo $cfg | sed 's/"logLevel":"[^"]*"/"logLevel":"info"/') >/dev/null 2>&1
                echo "Reset $app to info"
            end
        else
            for app in radarr sonarr prowlarr
                set -l url (eval echo \$$app:toupper)_URL
                test -z "$url"; and echo "$app: unreachable"; and continue
                set -l key (eval echo \$$app:toupper)_API_KEY
                set -l level (curl -sS "$url/api/v3/config/host" -H "X-Api-Key: $key" 2>/dev/null | grep -oP '"logLevel":\s*"\K[^"]+')
                echo "  $app: $level"
            end
        end
        return
    end

    # Notify test
    if test "$path" = "/api/v2/cli/notify/test"
        if test -n "$DISCORD_WEBHOOK_URL"
            curl -sS -X POST "$DISCORD_WEBHOOK_URL" -H 'Content-Type: application/json' \
                -d '{"content": "Test notification from fish shell"}' >/dev/null 2>&1
            echo "Test notification sent."
        else
            echo "DISCORD_WEBHOOK_URL not set." >&2
            return 1
        end
        return
    end

    # ── Fallback: unknown path ────────────────────────────────────
    echo "Unknown API path: $path" >&2
    echo "This function needs to be migrated to call its service directly." >&2
    return 1
end
