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

# conf.d entries installed by install.sh (shared fmt_* helpers + .env loader)
# bearcave-env.fish is a generated regular file, not a symlink.
for f in "$FISH_DIR"/conf.d/bearcave-cli-format.fish "$FISH_DIR"/conf.d/bearcave-env.fish; do
    [ -e "$f" ] && rm "$f" && removed=$((removed + 1))
done

# docker compose guard wrapper (landmine #3) — installed as a regular symlink
for f in "$FISH_DIR"/functions/docker.fish; do
    [ -L "$f" ] && rm "$f" && removed=$((removed + 1))
done
# bash/zsh snippet
rm -f "${HOME}/.config/bearcave/docker-guard.sh" 2>/dev/null || true

echo "Removed $removed symlinks from fish-functions."
