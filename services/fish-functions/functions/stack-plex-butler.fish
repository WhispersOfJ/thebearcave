# Usage: stack-plex-butler <task>
function stack-plex-butler --description 'Fire a Plex Butler task on demand'
    if test (count $argv) -ne 1
        echo "Usage: stack-plex-butler <task>" >&2
        echo "Tasks: backup-database, clean-cache-files, clean-log-files," >&2
        echo "  deep-media-analysis, garbage-collect-blobs, garbage-collect-media," >&2
        echo "  generate-ad-markers, generate-chapter-thumbs, generate-credits-markers," >&2
        echo "  generate-intro-markers, generate-media-index, generate-voice-activity," >&2
        echo "  loudness-analysis, music-analysis, process-assets, refresh-epg," >&2
        echo "  refresh-libraries, refresh-local-media, upgrade-media-analysis" >&2
        return 1
    end
    __stack_api POST "/api/v2/cli/plex/butler/$argv[1]"
end
