# Usage: stack-nzbdav-delete-failures [-y|--yes]
function stack-nzbdav-delete-failures --description 'Delete NzbDAV failed downloads'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'Delete all FAILED downloads from NzbDAV history? [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    set -l result (__nzbdav_api GET history "limit=500" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach NzbDAV API"
        return 1
    end

    set -l failed_ids (echo "$result" | python3 -c "
import sys, json
try:
    slots = json.load(sys.stdin).get('history', {}).get('slots', [])
except Exception:
    sys.exit(1)
for s in slots:
    if s.get('status') == 'Failed':
        print(s.get('nzo_id', ''))
")

    if test (count $failed_ids) -eq 0
        fmt_success "No failed downloads in history."
        return 0
    end

    set -l deleted 0
    set -l errors 0
    for id in $failed_ids
        if curl -sf "http://localhost:3000/api?mode=history&name=delete&value=$id&output=json&apikey=$FRONTEND_BACKEND_API_KEY" >/dev/null 2>&1
            set deleted (math $deleted + 1)
        else
            set errors (math $errors + 1)
        end
    end

    if test $errors -eq 0
        fmt_success "Deleted $deleted failed download(s)."
    else
        fmt_error "Deleted $deleted failed download(s); $errors delete(s) failed."
        return 1
    end
end
