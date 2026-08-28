# completions for stack-top — GENERATED FILE, do not edit.
# Regenerate: fish services/fish-functions/scripts/gen-completions.fish
complete -c stack-top -f -d 'Top containers by CPU or memory usage'
complete -c stack-top -n 'test (count (commandline -opc)) -eq 1' -a 'cpu mem'
complete -c stack-top -n 'test (count (commandline -opc)) -eq 2' -a '1 3 5 10 20'
