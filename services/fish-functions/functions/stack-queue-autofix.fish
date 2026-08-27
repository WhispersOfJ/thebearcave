# Usage: stack-queue-autofix [-y|--yes]
function stack-queue-autofix --description 'Auto-fix stuck queue items (blocklist+research)'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'Auto-fix stuck queue items? This blocklists failed items. [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end
    # This endpoint performs cross-service analysis in the control panel.
    # Preserved as __stack_api until the logic is extracted to a standalone script.
    __stack_api POST /api/v2/cli/queue/autofix
end
