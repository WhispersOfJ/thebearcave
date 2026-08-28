#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FISH_DIR="${HOME}/.config/fish"

# Symlink ALL functions: the stack-* commands plus the __-prefixed helpers
# they call at runtime (__arr_api, __plex_api, ...). Fish only autoloads a
# file when its command name is invoked, so __-files are never exposed as
# user commands — but they must be on the function path for the stack-*
# commands to work.
installed=0
for f in "$SCRIPT_DIR"/functions/*.fish; do
    [ -f "$f" ] || continue
    ln -sf "$f" "$FISH_DIR/functions/$(basename "$f")"
    installed=$((installed + 1))
done

# __cli_format.fish defines shared fmt_* helpers but nothing ever invokes a
# command named __cli_format, so autoload would never load it. conf.d scripts
# run at fish startup, which is exactly what a shared helper library needs.
mkdir -p "$FISH_DIR/conf.d"
ln -sf "$SCRIPT_DIR/functions/__cli_format.fish" "$FISH_DIR/conf.d/bearcave-cli-format.fish"

# Symlink completions (optional — directory may be empty)
mkdir -p "$FISH_DIR/completions"
completions=0
for f in "$SCRIPT_DIR"/completions/*.fish; do
    [ -f "$f" ] || continue
    ln -sf "$f" "$FISH_DIR/completions/$(basename "$f")"
    completions=$((completions + 1))
done

echo "Installed $installed functions + $completions completions from fish-functions."
