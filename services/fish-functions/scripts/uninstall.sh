#!/usr/bin/env bash
set -euo pipefail

FISH_DIR="${HOME}/.config/fish"
removed=0

for f in "$FISH_DIR"/functions/stack-*.fish "$FISH_DIR"/functions/__stack_*.fish; do
    [ -L "$f" ] && rm "$f" && removed=$((removed + 1))
done
for f in "$FISH_DIR"/completions/stack-*.fish "$FISH_DIR"/completions/__stack_*.fish; do
    [ -L "$f" ] && rm "$f"
done

echo "Removed $removed symlinks from fish-functions."
