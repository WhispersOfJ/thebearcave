function stack-reboot-check --description 'Check for pending reboot marker'
    if test -f /run/reboot-required
        echo "Reboot required (/run/reboot-required exists)"
        return 1
    else
        echo "No reboot pending."
    end
    stack-kernel-check
end
