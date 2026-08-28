# completions for stack-plex-butler — GENERATED FILE, do not edit.
# Regenerate: fish services/fish-functions/scripts/gen-completions.fish
complete -c stack-plex-butler -f -d 'Fire a Plex Butler task on demand'
complete -c stack-plex-butler -n 'test (count (commandline -opc)) -eq 1' -a 'backup-database clean-cache-files clean-log-files deep-media-analysis garbage-collect-blobs garbage-collect-media generate-ad-markers generate-chapter-thumbs generate-credits-markers generate-intro-markers generate-media-index generate-voice-activity loudness-analysis music-analysis process-assets refresh-epg refresh-libraries refresh-local-media upgrade-media-analysis'
