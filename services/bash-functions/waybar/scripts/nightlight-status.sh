#!/usr/bin/env bash
# nightlight-status.sh — waybar custom-module state for gammastep.
#
# Polled by custom/nightlight: sun (dim) while the night light is off, moon
# (amber, class `active`) while gammastep runs. The toggle lives in the sway
# script ~/.config/sway/gammastep-toggle.sh.
set -euo pipefail

if pgrep -x gammastep >/dev/null 2>&1; then
    text=""
    class="active"
    tooltip="Night light on — click to disable"
else
    text=""
    class="idle"
    tooltip="Night light off — click to enable"
fi

jq -nc --arg text "$text" --arg class "$class" --arg tooltip "$tooltip" \
    '{text: $text, class: $class, tooltip: $tooltip}'
