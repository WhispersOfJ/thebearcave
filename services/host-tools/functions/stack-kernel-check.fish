function stack-kernel-check --description 'Compare running vs installed kernel'
    set -l running (uname -r)
    set -l installed (pacman -Q linux 2>/dev/null | awk '{print $2}')
    echo "Running:  $running"
    echo "Installed: $installed"
    if test "$running" != "$installed"
        echo "MISMATCH — a reboot is needed."
        return 1
    else
        echo "OK — running kernel matches installed."
    end
end
