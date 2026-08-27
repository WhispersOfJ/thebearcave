# Internal helper: call the Control Panel CLI API via Traefik.
# Returns plain text. Color is enabled when MEDIA_STACK_COLOR is true.
# Usage: __stack_api METHOD PATH [JSON_BODY]
function __stack_api
    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    set -l host_ip $MEDIA_STACK_HOST_IP
    test -z "$host_ip"; and set host_ip "192.0.2.1"
    set -l base_url "https://bearcave.$host_ip.nip.io"
    set -l service_key $MEDIA_STACK_SERVICE_KEY

    set -l curl_opts -sS -X $method --fail-with-body
    if test -n "$service_key"
        set curl_opts $curl_opts -H "X-Api-Key: $service_key"
    end
    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end
    if test "$MEDIA_STACK_COLOR" = true
        set curl_opts $curl_opts -H "Accept: text/x-terminal"
    end

    curl $curl_opts "$base_url$path"
end
