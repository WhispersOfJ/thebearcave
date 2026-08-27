function stack-git-status-all --description 'Git status across every repo under ~/Claude'
    for dir in ~/Claude/*/
        if test -d "$dir/.git"
            set -l name (basename "$dir")
            set -l status (git -C "$dir" status --short 2>/dev/null)
            if test -n "$status"
                echo "=== $name ==="
                echo "$status"
                echo ""
            end
        end
    end
end
