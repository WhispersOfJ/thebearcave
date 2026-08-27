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

    if test "$by" = "mem"
        docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}' \
            | sort -t'%' -k2 -rn | head -n $limit | while read -l name cpu mem_pct mem_usage
            echo "  $name  $cpu  $mem_pct  $mem_usage"
        end
    else
        docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}' \
            | sort -t'%' -k1 -rn | head -n $limit | while read -l name cpu mem_pct mem_usage
            echo "  $name  $cpu  $mem_pct  $mem_usage"
        end
    end
end
