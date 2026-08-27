# Usage: stack-journal-size [--vacuum-size SIZE]
function stack-journal-size --description 'Journald disk usage; optionally vacuum'
    if contains -- --vacuum-size $argv
        set -l idx (contains -i -- --vacuum-size $argv)
        set -l next (math $idx + 1)
        sudo journalctl --vacuum-size=$argv[$next]
    else
        journalctl --disk-usage
    end
end
