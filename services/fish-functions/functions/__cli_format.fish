# __cli_format.fish — Shared formatting helpers for fish functions
# Replaces the Python Formatter class from the retired CLI API.
# All functions respect $STACK_COLOR (true/false, default: auto-detect TTY).

# ANSI color codes using fish-compatible escape sequences
set -g _FMT_RESET (printf '\033[0m')
set -g _FMT_BOLD (printf '\033[1m')
set -g _FMT_DIM (printf '\033[2m')
set -g _FMT_RED (printf '\033[31m')
set -g _FMT_GREEN (printf '\033[32m')
set -g _FMT_YELLOW (printf '\033[33m')
set -g _FMT_BLUE (printf '\033[34m')
set -g _FMT_CYAN (printf '\033[36m')
set -g _FMT_WHITE (printf '\033[37m')

function _fmt_color_enabled
    if set -q STACK_COLOR
        test "$STACK_COLOR" = "true"
        return
    end
    test -t 1
end

function fmt_heading
    set -l text $argv[1]
    if _fmt_color_enabled
        printf "%s%s%s%s\n" "$_FMT_BOLD" "$_FMT_CYAN" "$text" "$_FMT_RESET"
    else
        echo "$text"
    end
end

function fmt_success
    set -l text $argv[1]
    if _fmt_color_enabled
        printf "%s%s%s\n" "$_FMT_GREEN" "$text" "$_FMT_RESET"
    else
        echo "$text"
    end
end

function fmt_error
    set -l text $argv[1]
    if _fmt_color_enabled
        printf "%s%s%s\n" "$_FMT_RED" "$text" "$_FMT_RESET"
    else
        echo "$text"
    end
end

function fmt_warning
    set -l text $argv[1]
    if _fmt_color_enabled
        printf "%s%s%s\n" "$_FMT_YELLOW" "$text" "$_FMT_RESET"
    else
        echo "$text"
    end
end

function fmt_dim
    set -l text $argv[1]
    if _fmt_color_enabled
        printf "%s%s%s\n" "$_FMT_DIM" "$text" "$_FMT_RESET"
    else
        echo "$text"
    end
end

function fmt_status_dot
    set -l st $argv[1]
    if not _fmt_color_enabled
        echo "$st"
        return
    end
    set -l lc "$_FMT_WHITE"
    switch (string lower "$st")
        case running healthy up ok
            set lc "$_FMT_GREEN"
        case exited down unhealthy error failed
            set lc "$_FMT_RED"
        case warning stalled starting paused
            set lc "$_FMT_YELLOW"
    end
    printf "%s%s%s\n" "$lc" "$st" "$_FMT_RESET"
end

function fmt_kv
    set -l key $argv[1]
    set -l val $argv[2]
    if _fmt_color_enabled
        printf "  %s%s:%s %s\n" "$_FMT_BOLD" "$key" "$_FMT_RESET" "$val"
    else
        echo "  $key: $val"
    end
end
