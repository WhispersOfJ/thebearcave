# Usage: stack-top [cpu|mem] [limit]
function stack-top --description 'Top containers by CPU or memory usage'
    set -l by cpu
    set -l limit 10
    if test (count $argv) -ge 1; and contains -- $argv[1] cpu mem
        set by $argv[1]
    end
    if test (count $argv) -ge 2
        set limit $argv[2]
    end

    fmt_heading "Top Containers (by $by)"
    echo ""

    if test "$by" = mem
        # Metric-first columns so `sort -rn` orders on the right value
        docker stats --no-stream --format '{{.MemPerc}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' 2>/dev/null \
            | sort -rn | head -n $limit | while read -l mem_pct name cpu mem_usage
            echo "  $name  $cpu  $mem_pct  $mem_usage"
        end
    else
        docker stats --no-stream --format '{{.CPUPerc}}\t{{.Name}}\t{{.MemPerc}}\t{{.MemUsage}}' 2>/dev/null \
            | sort -rn | head -n $limit | while read -l cpu name mem_pct mem_usage
            echo "  $name  $cpu  $mem_pct  $mem_usage"
        end
    end
end
