# Quick Start

Get The Bear Cave running from zero to streaming in ~30 minutes.

---

## 1. Prerequisites

| Requirement | Detail |
|-------------|--------|
| **Linux host** | Required — `host.docker.internal` resolution only works on Linux |
| **Docker** | 24.0+ with Compose v2 (`docker compose`, not `docker-compose`) |
| **FUSE** | `/dev/fuse` available; kernel module loaded (`lsmod | grep fuse`) |
| **Hardware transcode (optional)** | Intel GPU with VAAPI (`/dev/dri` present) for Plex |
| **Usenet provider** | At least one provider (host, port 563, username, password) |
| **API keys** | TMDB (required for Metacache), TVDB (optional), Radarr/Sonarr (self-generated) |

> **Not supported:** Docker Desktop for Mac/Windows. The stack uses FUSE mounts and
> host-network Plex, both of which behave differently there.

---

## 2. Clone

```bash
git clone https://github.com/WhispersOfJ/thebearcave.git
cd thebearcave
```

---

## 3. Configure environment

```bash
cp .env.template .env
nano .env   # fill in real values
```

The minimum to start the stack:

```bash
PUID=1000
PGID=1000
TZ=America/New_York
HOST_IP=192.168.1.100        # your server's LAN IP

# One-time values you generate yourself:
PLEX_TOKEN=changeme           # see step 6
RADARR_API_KEY=changeme       # generate via openssl rand -hex 32
SONARR_API_KEY=changeme
PROWLARR_API_KEY=changeme

# Usenet provider:
NZBDAV_USENET_HOST=news.yourprovider.net
NZBDAV_USENET_PORT=563
NZBDAV_USENET_USER=yourusername
NZBDAV_USENET_PASS=yourpassword
```

---

## 4. Run setup

```bash
./scripts/setup.sh
```

This script will:
1. Validate Docker, the `.env` file, compose syntax, and directory structure
2. Generate Docker secrets into `secrets/` (gitignored)
3. Report placeholder values still needing real data

> **rclone password note:** `config/nzbdav-rclone/rclone.conf` requires an
> **rclone-obfuscated** password, not plaintext. Generate it with:
> ```bash
> rclone obscure "your-webdav-password"
> ```
> then put the output in `rclone.conf` (which is gitignored — the committed file is
> only a template).

---

## 5. Start the stack

```bash
docker compose up -d --build
```

First boot builds Metacache (the only service built from source), pulls ~20 images,
and starts everything in dependency order (Prowlarr → nzbdav → rclone → the rest).

Watch it come up:

```bash
docker compose ps
docker compose logs -f nzbdav nzbdav_rclone   # the critical path
```

The FUSE mount is the gate: radarr/sonarr/plex/unpackerr all wait for
`nzbdav_rclone` to report healthy.

---

## 6. Configure services

### Plex
1. Open `http://HOST_IP:32400/web`, claim the server with your Plex token
2. Add libraries pointing at:
   - `/data/movies` → Movies
   - `/data/shows` → TV Shows
   - `/data/anime-movies` → Movies (or your own layout)
   - `/data/anime-shows` → TV Shows
3. Verify hardware transcoding: Settings → Transcoder → "Use hardware acceleration when available"

### Metacache (metadata provider)
1. Open `http://HOST_IP:8765/dashboard` — check the health panel
2. Trigger a warm: `POST http://HOST_IP:8765/warm/all` (or use the dashboard button)
3. In Plex: Settings → Metadata Agents → **Add Provider** → `http://HOST_IP:8765/movie`
   (repeat with `/tv`), create an agent, assign as Primary to your libraries

### Radarr / Sonarr
1. Open `https://radarr.HOST_IP.nip.io`, accept the wizard
2. Add the download client: InfiniDysk (`http://nzbdav:3000`, API key = `FRONTEND_BACKEND_API_KEY`)
3. Add root folders: `/data/movies` (Radarr), `/data/shows` (Sonarr),
   `/data/anime-movies`, `/data/anime-shows`
4. Radarr/Sonarr generate their own API keys on first boot — copy them into `.env`
   and recreate the containers: `docker compose up -d --force-recreate`

### Seerr
1. Open `https://seerr.HOST_IP.nip.io`, complete setup wizard
2. Connect Radarr, Sonarr, and Plex

### HTTPS certificates (kill the browser warning)
All `*.nip.io` hostnames are served over HTTPS by Traefik. By default Traefik uses
its self-signed cert (browser warning). To get valid certificates from the
stack's own mkcert CA — installed on this host already — run `scripts/trust-ca.sh`
and install `rootCA.pem` on each device you browse from:

```bash
./scripts/trust-ca.sh   # prints per-platform install steps
```

See [docs/tls.md](tls.md) for the full model, renewal, and troubleshooting.

---

## 7. Verify everything

```bash
# All containers healthy?
docker compose ps

# Automated health checks (all 29 services)
./tests/health/run-all.sh

# Integration pipeline test (Plex, rclone, Radarr/Sonarr, InfiniDysk, Metacache)
./tests/integration/test_pipeline.sh

# FUSE mount live?
docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav && echo "MOUNT OK"
```

---

## 8. Next steps

- Point Seerr/Radarr/Sonarr at your Usenet providers via Prowlarr
- Configure WatchState to back up Plex watch history
- Import your old stack data — see [Migration guides](migration/from-media-stack.md)
- Explore the dashboards — see [Monitoring](services/monitoring.md)

---

## Day-1 checklist

- [ ] `.env` filled with real values (no `changeme` left)
- [ ] `./scripts/setup.sh` passes all validations
- [ ] `docker compose up -d --build` completes
- [ ] `docker compose ps` — all services healthy
- [ ] FUSE mount confirmed (`mountpoint -q` succeeds)
- [ ] Plex claims + libraries added
- [ ] Metacache provider registered in Plex
- [ ] Radarr/Sonarr download client + root folders set
- [ ] `./tests/health/run-all.sh` — all pass
