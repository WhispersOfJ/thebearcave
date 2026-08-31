function stack-plex-image-clean --description 'Clean Plex PhotoTranscoder cache and report reclaimed space'
    set -l output (docker compose --profile maintenance run --rm --no-deps imagemaid 2>&1)
    set -l rc $status
    set -l recovered (string match -r -- 'Space Recovered:.*' $output)

    if test $rc -eq 0; and test (count $recovered) -gt 0
        printf '%s\n' $recovered
    else
        printf '%s\n' $output >&2
    end
    return $rc
end
