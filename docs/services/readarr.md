# Readarr

Ebook acquisition — tracks books and monitors authors, downloading through the same pipeline as the rest of the *arr family.

| | |
|---|---|
| **Image** | `linuxserver/readarr:develop-0.4.18.2805-ls157` |
| **Port** | 8787 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:8787/ping` |
| **Config** | `config/readarr/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy (restart cascade) |
| **Image note** | **Pinned** — no hotio image exists and Readarr has no stable release (revived project, dev builds only); bump deliberately |

## Role

- Tracks the ebook library (authors → books), monitors for new editions
- Searches via Prowlarr, grabs through InfiniDysk's SABnzbd-compatible API
- Imports via symlinks into the FUSE mount, using the new `books` nzbdav category

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/readarr/` | `/config` | App state |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` (rslave) | FUSE mount for symlink imports |
| `media/books/` | `/data/books` | Ebook root folder |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `READARR_API_KEY` | API key (generated on first boot, copy into `.env`) |

## First-run

1. Open `https://readarr.HOST_IP.nip.io`
2. Download client → Add → **InfiniDysk**: host `nzbdav`, port 3000,
   API key = `FRONTEND_BACKEND_API_KEY` from `.env`, category `books`
3. Root folder: `/data/books`
4. Copy the generated API key into `.env`, `docker compose up -d --force-recreate readarr`
5. Indexers arrive automatically via Prowlarr push-sync

Requires the nzbdav category rollout first (see `stack-expansion-spec.md` §15).

## Troubleshooting

- **Imports failing with I/O errors** — the FUSE mount may be down. Check
  `docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav`; restart dependents after.
- **API key changed** — every consumer reads `READARR_API_KEY`; update `.env` and
  `--force-recreate` the consumers.
- **Image pinned deliberately** — the `develop-0.4.18.2805-ls157` tag is the only
  reliably resolvable Readarr image; bump intentionally and re-verify the CVE gate.
