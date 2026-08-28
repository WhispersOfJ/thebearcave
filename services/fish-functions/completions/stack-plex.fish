# completions for stack-plex — GENERATED FILE, do not edit.
# Regenerate: fish services/fish-functions/scripts/gen-completions.fish
complete -c stack-plex -f -d 'Trigger a Plex maintenance action'
complete -c stack-plex -n 'test (count (commandline -opc)) -eq 1' -a 'scan empty-trash optimize-db clean-bundles'
