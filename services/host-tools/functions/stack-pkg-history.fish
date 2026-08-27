# Usage: stack-pkg-history [N]
function stack-pkg-history --description 'Tail of pacman transaction log'
    set -l count 20
    test (count $argv) -ge 1; and set count $argv[1]
    tail -n "$count" /var/log/pacman.log 2>/dev/null
end
