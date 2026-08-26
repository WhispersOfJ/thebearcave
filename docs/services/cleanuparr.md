# Cleanuparr

Queue cleanup automation — strikes, malware blocking, stalled-cleanup.

| | |
|---|---|
| **Image** | `ghcr.io/cleanuparr/cleanuparr:2.10.5` |
| **Port** | 11011 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:11011/` |
| **Config** | `services/cleanuparr/config/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy |

## Role

- Automates what the Control Panel's "unstick" button does by hand
- QueueCleaner: stalled/warning/error queue items
- MalwareBlocker: blocks releases matching malware patterns
- Needs filesystem access to the paths the download client reports — hence the FUSE
  mount bind

## First-run

Cleanuparr discovers *arr apps but needs explicit instance registration in its
`arr_instances` table (it does not auto-register). Register Radarr + Sonarr after
first boot.

## Troubleshooting

- **Not acting on the queue** — confirm instances are registered (Settings → Instances)
  and API keys match `.env`
- **Can't see download paths** — the FUSE mount bind must be present; check
  `docker exec cleanuparr ls /mnt/remote/nzbdav`
