function stack-plex-butler-all --description 'Fire every Plex Butler task sequentially'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'Fire ALL Butler tasks? This takes a while. [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end
    for task in backup-database clean-cache-files clean-log-files deep-media-analysis \
        garbage-collect-blobs garbage-collect-media generate-ad-markers \
        generate-chapter-thumbs generate-credits-markers generate-intro-markers \
        generate-media-index generate-voice-activity loudness-analysis \
        music-analysis process-assets refresh-epg refresh-libraries \
        refresh-local-media upgrade-media-analysis
        echo "Firing $task..."
        __stack_api POST "/api/v2/cli/plex/butler/$task"
    end
end
