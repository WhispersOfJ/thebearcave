function stack-help --description 'List all stack-* terminal commands'
    echo 'Bear Cave media stack — terminal commands'
    echo ''
    set -l func_dir (status dirname)/../functions
    # Skip entries whose file is unreadable — e.g. stale symlinks left in an
    # installed fish path after a command was retired — and sort with the
    # family root first: replace '-' with a space in the sort key so
    # 'stack-arr' ('stack arr') precedes 'stack-arr-backlog'
    # ('stack arr backlog') — space (0x20) sorts before '-' (0x2D).
    set -l keys
    for f in "$func_dir"/stack-*.fish
        test -r "$f"; or continue
        set -l name (string replace -r '\.fish$' '' -- (basename "$f"))
        set -a keys (string replace -a -- '-' ' ' $name)
    end
    for key in (printf '%s\n' $keys | sort)
        set -l name (string replace -a -- ' ' '-' $key)
        set -l desc (string match -r -- "--description '(.+?)'" (cat "$func_dir/$name.fish"))[2]
        if test -n "$desc"
            printf "  %-45s %s\n" "$name" "$desc"
        else
            printf "  %s\n" "$name"
        end
    end
end
