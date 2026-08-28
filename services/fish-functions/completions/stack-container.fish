# completions for stack-container — GENERATED FILE, do not edit.
# Regenerate: fish services/fish-functions/scripts/gen-completions.fish
complete -c stack-container -f -d 'Restart/stop/start a single container'
complete -c stack-container -n 'test (count (commandline -opc)) -eq 1' -a 'restart stop start'
complete -c stack-container -n 'test (count (commandline -opc)) -eq 2' -a '(docker ps --format "{{.Names}}" 2>/dev/null)'
