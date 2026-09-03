# Active Service Registry

The default Compose deployment contains nine always-on services. All default
containerized services except Plex use the `bearcave` bridge network; Plex uses host
networking. Profile-gated maintenance services are listed separately and are not
started by the default deployment.

| Service | Port | Role |
|---------|------|------|
| Prowlarr | 9696 | Indexer manager |
| Radarr | 7878 | Movie acquisition |
| Sonarr | 8989 | TV acquisition |
| Bazarr | 6767 | Subtitle acquisition (re-adopted 2026-09-03) |
| NzbDAV / InfiniDysk | 3000 | Usenet download client and WebDAV |
| `nzbdav_rclone` | — | WebDAV-backed FUSE mount |
| Seerr | 5055 | Request management |
| Plex | 32400 | Media server |
| Unpackerr | — | Download extraction |

There is no reverse proxy or landing page in the active stack. ImageMaid is a manual,
profile-gated maintenance service and is excluded from the normal nine-container startup;
see [imagemaid.md](imagemaid.md). Retired services are tracked in [lifecycle.md](lifecycle.md)
and preserved only as historical records where noted.
