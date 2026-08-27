# Usage: stack-pkg-orphans [--remove]
function stack-pkg-orphans --description 'List or remove orphaned packages'
    set -l orphans (pacman -Qdtq 2>/dev/null)
    if test -z "$orphans"
        echo "No orphaned packages."
        return 0
    end
    if contains -- --remove $argv
        echo "Removing orphans..."
        sudo pacman -Rns $orphans
    else
        echo "$orphans"
    end
end
