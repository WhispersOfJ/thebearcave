function stack-letterboxd-tracked --description 'Every Letterboxd list currently registered'
    set -l tracked_file "$HOME/.config/bearcave/letterboxd-tracked.txt"

    fmt_heading "Tracked Letterboxd Lists"
    echo ""

    if not test -f "$tracked_file"
        echo "  No lists tracked."
        return
    end

    set -l count 0
    while read -l line
        test -z "$line"; and continue
        set -l url (string split '|' $line)[1]
        set -l label (string split '|' $line)[2]
        if test -n "$label"
            echo "  $label  $url"
        else
            echo "  $url"
        end
        set count (math $count + 1)
    end <"$tracked_file"

    if test $count -eq 0
        echo "  No lists tracked."
    else
        echo ""
        echo "  $count list(s) tracked."
    end
end
