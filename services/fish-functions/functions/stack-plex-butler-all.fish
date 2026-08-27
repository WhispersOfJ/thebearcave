function stack-plex-butler-all --description 'Trigger all Plex Butler tasks'
    set -l tasks backup-database clean-cache-files clean-log-files \
        garbage-collect-blobs garbage-collect-media \
        generate-ad-markers generate-chapter-thumbs generate-credits-markers \
        generate-intro-markers generate-media-index generate-voice-activity \
        loudness-analysis music-analysis process-assets refresh-epg \
        refresh-libraries refresh-local-media upgrade-media-analysis
    for task in $tasks
        __plex_butler $task
    end
end
