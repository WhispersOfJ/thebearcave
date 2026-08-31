#!/usr/bin/env bash
# Install the repository's git hooks so the pre-push gate runs automatically.
#
# Registers scripts/git-hooks as the hooks directory (git config
# core.hooksPath); the pre-push hook runs ./scripts/preflight.sh — including
# the secret-drift guard — before any push reaches the remote. Idempotent;
# re-run after a fresh clone or if the repository moves (the path is stored
# absolute, so a moved tree needs re-running).
#
# Uninstall:   git config --unset core.hooksPath
# Escape hatch: git push --no-verify   (understand the failure first)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT/scripts/git-hooks/pre-push" ]; then
    echo "error: $ROOT/scripts/git-hooks/pre-push missing or not executable" >&2
    exit 1
fi

git -C "$ROOT" config core.hooksPath "$ROOT/scripts/git-hooks"

echo "git hooks installed:"
echo "  core.hooksPath = $(git -C "$ROOT" config --get core.hooksPath)"
echo "  pre-push runs ./scripts/preflight.sh before every push."
echo "Uninstall with: git config --unset core.hooksPath"
