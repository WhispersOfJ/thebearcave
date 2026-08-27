# Usage: stack-pkg-update [--yes]
function stack-pkg-update --description 'Run pacman/AUR system update'
    if not type -q pacman
        echo "Not an Arch-based host." >&2
        return 1
    end
    if not contains -- --yes $argv
        read -l -P "Run a full system update now? [y/N] " confirm
        if not string match -qr '^[Yy]' -- $confirm
            echo "Aborted."
            return 1
        end
    end
    sudo -n pacman -Syu --noconfirm
    set -l status_pacman $status
    if type -q paru
        paru -Sua --noconfirm
    else if type -q yay
        yay -Sua --noconfirm
    end
    return $status_pacman
end
