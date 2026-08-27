#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FISH_DIR="${HOME}/.config/fish"

# Symlink functions
installed=0
for f in "$SCRIPT_DIR"/functions/stack-*.fish "$SCRIPT_DIR"/functions/__host_*.fish; do
    [ -f "$f" ] || continue
    ln -sf "$f" "$FISH_DIR/functions/$(basename "$f")"
    installed=$((installed + 1))
done

# Symlink completions
mkdir -p "$FISH_DIR/completions"
for f in "$SCRIPT_DIR"/completions/*.fish; do
    [ -f "$f" ] || continue
    ln -sf "$f" "$FISH_DIR/completions/$(basename "$f")"
done

echo "Installed $installed functions + completions from host-tools."
