# Usage: stack-pkg-clean-cache [keep-N]
function stack-pkg-clean-cache --description 'Vacuum pacman package cache to last N versions'
    set -l keep 2
    test (count $argv) -ge 1; and set keep $argv[1]
    sudo paccache -rk "$keep"
end
