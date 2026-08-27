function stack-aur-audit --description 'AUR security audit'
    if type -q arch-audit
        arch-audit
    else
        echo "arch-audit not installed. Listing foreign packages:"
        pacman -Qmq
    end
end
