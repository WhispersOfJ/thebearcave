#!/usr/bin/env fish
# ============================================================================
# gen-completions.fish — generate fish tab completions for every stack-* command
# ============================================================================
# Reads the --description from each functions/stack-*.fish and writes one
# completions/<command>.fish file per command (fish autoloads completion files
# by command name, mirroring the functions/ layout that install.sh symlinks).
#
# Commands with a fixed argument vocabulary get positional/flag completions
# from extra_completions below. To change or add argument completions, edit
# that table and regenerate — never edit completions/*.fish by hand.
#
# Usage:
#   fish scripts/gen-completions.fish            # (re)generate completions/
#   fish scripts/gen-completions.fish --check    # exit 1 if completions/ is stale
# ============================================================================

set -g SCRIPT_DIR (status dirname)
set -g FUNC_DIR (realpath "$SCRIPT_DIR/../functions")
set -g COMP_DIR (realpath "$SCRIPT_DIR/..")/completions

# Argument completions beyond the shared description line.
# $argv[1] is the command name; print extra `complete` lines for it.
#
# Positional conditions: `commandline -opc` counts already-typed tokens
# (including the command itself), so `-eq 1` means "completing the first
# argument". Case order matters — specific patterns must precede globs.
function extra_completions --argument-names name
    switch $name
        # --- app + action / value pairs ---
        case stack-arr
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'radarr sonarr'"
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 2' -a 'rss-sync search-missing unstick unstick-importing'"
        case stack-arr-toggle-search
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'radarr sonarr all'"
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 2' -a 'on off'"
        case stack-plex
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'scan empty-trash optimize-db clean-bundles'"
        case stack-plex-image-clean
            # No arguments: this is a deliberately narrow, PhotoTranscoder-only run.
        case stack-plex-butler
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'backup-database clean-cache-files clean-log-files deep-media-analysis garbage-collect-blobs garbage-collect-media generate-ad-markers generate-chapter-thumbs generate-credits-markers generate-intro-markers generate-media-index generate-voice-activity loudness-analysis music-analysis process-assets refresh-epg refresh-libraries refresh-local-media upgrade-media-analysis'"
        case stack-seerr-requests
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'pending approved available all'"
        case stack-top
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'cpu mem'"
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 2' -a '1 3 5 10 20'"
        case stack-container
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'restart stop start'"
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 2' -a '(docker ps --format \"{{.Names}}\" 2>/dev/null)'"
        case stack-worktree
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'docs/ ci/ feat/ fix/ chore/'"
        case stack-letterboxd-import
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'film list watchlist watched collection filmography popular random'"
            echo "complete -c $name -l limit -d 'Max rows to import'"

            # --- completion from tracked-list files ---
        case stack-mdblist-untrack
            echo "complete -c $name -a '(cat ~/.config/bearcave/mdblist-tracked.txt 2>/dev/null)'"
        case stack-letterboxd-untrack
            echo "complete -c $name -a '(cat ~/.config/bearcave/letterboxd-tracked.txt 2>/dev/null)'"

            # --- confirmation-skip flags ---
        case stack-queue-autofix stack-restart-all stack-nzbdav-delete-failures
            echo "complete -c $name -l yes -s y -d 'Skip confirmation prompt'"

            # --- app-arg commands (radarr|sonarr ...) ---
        case 'stack-arr-*' stack-cutoff-unmet stack-import-lists stack-loop-candidates stack-loop-unmonitor stack-customformat-diff
            echo "complete -c $name -n 'test (count (commandline -opc)) -eq 1' -a 'radarr sonarr'"
    end
end

# Write one completion file per stack-* function into $out_dir.
function generate --argument-names out_dir
    mkdir -p $out_dir
    for f in $FUNC_DIR/stack-*.fish
        set -l name (basename $f .fish)
        set -l m (string match -r -- "--description '(.+?)'" (cat $f))
        set -l lines
        if set -q m[2]
            set -l desc (string replace -a "'" "\\'" -- $m[2])
            set lines "complete -c $name -f -d '$desc'"
        else
            set lines "complete -c $name -f"
        end
        set -a lines (extra_completions $name)
        printf '%s\n' \
            "# completions for $name — GENERATED FILE, do not edit." \
            "# Regenerate: fish services/fish-functions/scripts/gen-completions.fish" \
            $lines >$out_dir/$name.fish
    end
end

if test (count $argv) -ge 1; and test "$argv[1]" = --check
    set -l tmp (mktemp -d)
    generate "$tmp/completions"
    set -l drift (diff -ru $COMP_DIR "$tmp/completions" 2>&1)
    if test $status -eq 0
        echo "completions are up to date ($(count $COMP_DIR/*.fish) files)"
        rm -rf $tmp
        exit 0
    else
        echo "completions are stale or out of sync:" >&2
        echo "$drift" >&2
        echo "Regenerate with: fish services/fish-functions/scripts/gen-completions.fish" >&2
        rm -rf $tmp
        exit 1
    end
else
    generate $COMP_DIR
    echo "Wrote $(count $COMP_DIR/*.fish) completion files to $COMP_DIR"
end
