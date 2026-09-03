# Waybar config (dotfile source of truth)

Canonical copies of the desktop bar files. The live session runs from
`~/.config/waybar/` — after editing here, sync and restart the bar:

```bash
cp config      ~/.config/waybar/config
cp style.css   ~/.config/waybar/style.css
cp scripts/*.sh ~/.config/waybar/scripts/
pkill -x waybar && waybar -c ~/.config/waybar/config -s ~/.config/waybar/style.css &
```

## `custom/stack` — stack-tui launcher

`scripts/stack-tui-toggle.sh` toggles the repo's stack-tui
(`services/bash-functions/scripts/stack-tui`) in a centred floating
alacritty window on the sway scratchpad; the TUI keeps running while hidden.
A matching sway binding (`$mod+s`) fires the same script.

Subcommands:

| Command | Purpose |
|---------|---------|
| `toggle` | show / hide / launch the TUI window (waybar on-click, `$mod+s`) |
| `state` | emit waybar JSON (`open`/`closed` class + tooltip with function count and running function) |
| `opacity [value]` | set `window.opacity` live via alacritty IPC — no relaunch; applies `$STACK_TUI_OPACITY` (default 0.85) when omitted |

Env overrides: `STACK_TUI_REPO`, `STACK_TUI_TERM`, `STACK_TUI_CLASS`,
`STACK_TUI_TITLE`, `STACK_TUI_SIZE`, `STACK_TUI_OPACITY`.

The sway side needs its window rule, tracked here as
`sway/stack-tui.conf` and pulled into the session config with an `include`:

```bash
cp sway/stack-tui.conf ~/.config/sway/stack-tui.conf
swaymsg reload
```
