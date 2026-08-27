function stack-help --description 'List all stack-* terminal commands'
    echo 'Bear Cave media stack — terminal commands'
    echo ''
    set -l func_dir (status dirname)/../functions
    for f in "$func_dir"/stack-*.fish
        set -l name (string replace -r '\.fish$' '' -- (basename "$f"))
        set -l desc (string match -r "--description '(.+?)'" -- (cat "$f"))[2]
        if test -n "$desc"
            printf "  %-45s %s\n" "$name" "$desc"
        else
            printf "  %s\n" "$name"
        end
    end
end
