# bearcave-env.fish — Load the Bear Cave stack .env into the fish environment.
# At every fish startup the stack-* CLI commands need the API keys that live in
# the repo's .env (the same file docker compose reads). This loader exports
# them, honoring values already set.
#
# install.sh writes a conf.d entry that sets BEARCAVE_REPO_DIR (the repo root)
# before running this body. If the loader is sourced without that variable
# (e.g. directly from the repo for testing), it falls back to resolving the
# repo relative to this file's own path.
#
# NB: this deliberately avoids `source` and `while read` — fish 4.8.1 stack-
# overflows when a file sourced from conf.d at startup uses the read builtin.

set -l repo "$BEARCAVE_REPO_DIR"
if test -z "$repo"
    set -l self (status --current-filename)
    set -l real (readlink -f "$self" 2>/dev/null; or echo "$self")
    set repo (dirname (dirname (dirname "$real")))
end

set -l env_file "$repo/.env"
if test -f "$env_file"
    for line in (cat "$env_file")
        string match -q -- '#*' "$line"; and continue
        test -z "$line"; and continue
        set -l parts (string split -m 1 -- '=' "$line")
        test (count $parts) -ge 2; or continue
        set -l key (string trim -- "$parts[1]")
        set -l value (string trim -- "$parts[2]")
        test -z "$key"; and continue
        # strip one level of surrounding single/double quotes
        set -l value (string replace -r '^"(.*)"$' '$1' -- "$value")
        set -l value (string replace -r "^'(.*)'\$" '$1' -- "$value")
        if not set -q $key
            set -gx $key "$value"
        end
    end
end
