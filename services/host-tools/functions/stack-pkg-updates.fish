function stack-pkg-updates --description 'Pending pacman + AUR updates'
    if not type -q pacman
        echo "Not an Arch-based host." >&2
        return 1
    end
    echo "=== Pacman ==="
    pacman -Qu 2>/dev/null | head -20
    echo ""
    if type -q paru
        echo "=== AUR (paru) ==="
        paru -Qua 2>/dev/null | head -20
    else if type -q yay
        echo "=== AUR (yay) ==="
        yay -Qua 2>/dev/null | head -20
    end
end
