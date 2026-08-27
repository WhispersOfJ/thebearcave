function stack-claude-full-backup --description 'Full ~/Claude tree tar.zst backup to Dropbox'
    set -l dest ~/Dropbox/backups/claude-backup-(date +%Y%m%d-%H%M%S).tar.zst
    echo "Backing up ~/Claude to $dest..."
    tar -cf - -C ~ Claude | zstd -o "$dest"
    echo "Done: $dest"
end
