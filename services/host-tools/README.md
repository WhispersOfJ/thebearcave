# Host Tools — Local-only CLI

System diagnostic and maintenance commands that run directly on the host.
No API dependency — these are pure shell.

## Setup

```bash
services/host-tools/scripts/install.sh
```

## Commands

| Command | Description |
|---------|-------------|
| `stack-disk-free [warn] [crit]` | Disk free with thresholds |
| `stack-disk-health` | SMART health summary |
| `stack-mem-pressure` | Kernel PSI stats |
| `stack-kernel-check` | Running vs installed kernel |
| `stack-reboot-check` | Pending reboot marker |
| `stack-uptime-report` | Uptime + load + shutdown |
| `stack-zombie-check` | Zombie processes |
| `stack-service-failed` | Failed systemd units |
| `stack-pkg-updates` | Pending updates |
| `stack-pkg-update [--yes]` | Run system update |
| `stack-pkg-history [N]` | Pacman transaction log |
| `stack-pkg-orphans [--remove]` | Orphaned packages |
| `stack-pkg-clean-cache [N]` | Vacuum package cache |
| `stack-aur-audit` | AUR security audit |
| `stack-flatpak-updates [--apply]` | Flatpak updates |
| `stack-ssh-doctor` | SSH config health |
| `stack-git-status-all` | Git status across repos |
| `stack-claude-home` | cd to ~/Claude + launch Claude |

## Architecture

```
functions/          # One .fish file per command
completions/        # Manual tab completions
scripts/            # install.sh, uninstall.sh
```

No API calls — these run local commands (df, pacman, systemctl, etc).
