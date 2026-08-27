# Usage: stack-flatpak-updates [--apply]
function stack-flatpak-updates --description 'List or apply pending Flatpak updates'
    if not type -q flatpak
        echo "Flatpak not installed."
        return 1
    end
    if contains -- --apply $argv
        flatpak update -y
    else
        flatpak update
    end
end
