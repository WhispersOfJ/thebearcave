# Stack Expansion Spec — 10 New Containers

Status: **Draft — no code changes yet**
Date: 2026-08-28
Author: interview with user (4 rounds) + stack convention research

---

## 1. Request Summary

Add **10 new containers** to the Bear Cave stack in **phases**, driven by
"missing media automation" and open-ended scope. All new services are **full
stack citizens**: `bearcave` network, Traefik `nip.io` subdomain, config bind
mount, healthcheck — mirroring radarr/sonarr.

### Confirmed exclusions (off the table)
- ❌ Analytics/statistics tools (Tautulli-style)
- ❌ Transcode tools (Unmanic/FFmpeg services)
- ❌ Plex metadata managers (Kometa-style)
- ❌ Full media servers (Jellyfin/Emby) — Plex stays primary; niche readers (Audiobookshelf, Komga) are fine
- ❌ Torrent download clients

---

## 2. Scope — The 10 Services by Phase

### Phase 1 — Media acquisition & serving (5)
| # | Service | Purpose | Serves content? | Download path |
|---|---------|---------|-----------------|---------------|
| 1 | **Lidarr** | Music acquisition | No (feeds Plex music) | nzbdav pipeline (new `music` category) |
| 2 | **Readarr** | Ebook acquisition | No | nzbdav pipeline (new `books` category) |
| 3 | **Bazarr** | Subtitles for existing movies/shows | No | Talks to Radarr/Sonarr + Plex; subtitle downloads direct |
| 4 | **Audiobookshelf** | Audiobooks | **Yes** (own player) | nzbdav pipeline (new `audiobooks` category) + own server |
| 5 | **Komga** | Comics / manga | **Yes** (own reader) | nzbdav pipeline (new `comics` category) + own server |

### Phase 2 — Network & security (2)
| # | Service | Purpose | Key deployment note |
|---|---------|---------|---------------------|
| 6 | **AdGuard Home** | Network-wide DNS ad/tracker blocking | Becomes **the LAN DNS** via router DHCP (router config change) |
| 7 | **Crowdsec** | Intrusion detection | **Active blocking** — LAPI + bouncer in front of Traefik |

### Phase 3 — Utilities (3)
| # | Service | Purpose | Notes |
|---|---------|---------|-------|
| 8 | **Uptime Kuma** | Service status / uptime dashboard | |
| 9 | **Vaultwarden** | Self-hosted password manager | Native admin token auth |
| 10 | **n8n** | Workflow automation | First workflow: **Discord notifications** (import/grab/failure events → Discord webhook) |

> **Syncthing removed from scope** by user decision on 2026-08-28 (no offsite/LAN peer wanted).

---

## 3. Decisions from the Interview

| Topic | Decision |
|-------|----------|
| Scope | All 10, phased (phases proposed below, user approves) |
| Media download path | **Same pipeline as Radarr/Sonarr**: Prowlarr indexers → nzbdav (SABnzbd-compatible API) → rclone FUSE mount → library |
| Serving | New tools **may serve their own content** (Audiobookshelf, Komga) |
| Citizenship | Full citizens for all 10 |
| Auth | **Per-tool native auth only** — no Traefik basic-auth layer (Vaultwarden/AdGuard/n8n/Kuma use their own logins; *arr-style tools open like the rest of the stack) |
| Updates | **Per-tool judgment** — auto-update stable (`:latest`/`:release`); pin images with CVE or breaking-change history (like cleanuparr:2.10.5) |
| Docs | All 10 get landing-page cards + `docs/services/*.md` |
| Backups | **Config only** (content is re-acquirable) |
| Resources | **Tailored limits** per tool (host: 22Gi RAM / 16 cores / ~10G free, 266G disk free) |
| AdGuard | Full LAN DNS via router DHCP (documented path, part of Phase 2) |
| Crowdsec | Active blocking (bouncer + Traefik) |
| n8n | Discord notifications + media pipeline glue |
| ~~Syncthing~~ | **Removed from scope** (2026-08-28) |
| Exclusions | Confirmed list in §1 |

---

## 4. Integration Details (repo conventions)

### 4.1 Compose
- Use the `x-common` anchor (`<<: *common`) where defaults fit; override `mem_limit`/`cpus` per §7.
- All services: `networks: [bearcave]`, `restart: unless-stopped`, `*ca-mount` + `*ca-env`, standard logging.
- Healthchecks: `curl -sf http://localhost:<port>/<ping|health|status>` pattern (per-tool endpoint to be confirmed at implementation).
- Traefik labels per service (standard pattern):
  ```yaml
  - "traefik.enable=true"
  - "traefik.http.routers.<name>.rule=Host(`<name>.${HOST_IP}.nip.io`)"
  - "traefik.http.services.<name>.loadbalancer.server.port=<port>"
  - "traefik.http.routers.<name>.tls=true"
  ```
- Container `container_name` set for all.

### 4.2 nzbdav pipeline extension (Phase 1) — ✅ VERIFIED 2026-08-28

**Feasibility confirmed against the live API + official docs:**

- Categories are headless config-driven: `api.categories` → `NZBDAV_CONFIG__API__CATEGORIES` env (official InfiniDysk docs: "Letters/numbers/dashes" allowed).
- Live `GET /api?apikey=$FRONTEND_BACKEND_API_KEY&mode=get_cats` returns exactly the configured set:
  `{"categories":["*","uncategorized","tv","movies","anime-movies","anime-shows"]}`.
- Extending the env to `tv,movies,anime-movies,anime-shows,music,books,audiobooks,comics` is a supported config change — new categories will appear in `get_cats` and as per-category dirs in the rclone FUSE mount (`/mnt/remote/nzbdav/<cat>/`).
- API auth: SABnzbd-compatible endpoint is at **`/api`** (root path is the web UI → redirects to /login); auth via `?apikey=<FRONTEND_BACKEND_API_KEY>` query param. Radarr already uses this client (`NzbDAV Sabnzbd` implementation).

**⚠️ Deployment constraint (landmine #5):** applying the category change requires recreating the nzbdav container, which **wipes a non-empty queue and silently blocklists affected items**. Queue was **empty at last check (2026-08-28)** — follow §15 for the queue-gated rollout using `./scripts/update-nzbdav.sh` (queue guard built in); never `--force`.

- Lidarr/Readarr/Audiobookshelf/Komga configure nzbdav as a **SABnzbd-compatible download client**: `http://nzbdav:3000/api`, API key = `FRONTEND_BACKEND_API_KEY`, category per service (`music`/`books`/`audiobooks`/`comics`), like Radarr/Sonarr.
- **Check at implementation**: whether nzbdav's arr-instance integration (RadarrInstances/SonarrInstances) covers Lidarr/Readarr; if not, plain SABnzbd client config is sufficient.

### 4.3 Prowlarr
- Register Lidarr/Readarr (and Audiobookshelf/Komga if they support indexer sync) as apps in Prowlarr for indexer sharing.
- Requires `LIDARR_API_KEY` / `READARR_API_KEY` in `.env` (copied from app config after first boot, same as RADARR/SONARR keys).

### 4.4 Landing page (ALL services)
- `services/landing-page/service-registry.json` — add 10 entries; consider a **new category** (e.g. `utilities`) for AdGuard/Crowdsec/Kuma/Vaultwarden/n8n; media tools go in `pipeline`; update `pipeline_flow` (prowlarr → lidarr/readarr → nzbdav → …).
- **`services/landing-page/index.html` inline copy must be updated in the same change** (AGENTS.md landmine — the two drift silently).
- `depends_on` / `depended_by` graphs updated.

### 4.5 Env & secrets
- `.env.template` additions: `LIDARR_API_KEY`, `READARR_API_KEY`, `VAULTWARDEN_ADMIN_TOKEN`, `N8N_ENCRYPTION_KEY` (+ basic-auth creds if used), `CROWDSEC_*` as needed.
- `.github/required-secrets.json` — add every new env var (CI env-coverage check will fail otherwise).
- Docker secrets (`secrets/`) only where the tool supports file-based secrets; default to `.env` like the rest of the stack.

### 4.6 Docs
- `docs/services/*.md` × 10 (follow existing per-service doc style).
- Update `AGENTS.md` service table (22 → 32) and the port map.
- Update `docs/operations/backup-restore.md` — new config dirs join the backup list (config only).
- `docs/architecture.md` — service category table + mermaid diagrams.

### 4.7 CI / validation
- `docker compose config --quiet` stays green.
- Trivy scan of all new images (add suppressions to `.trivyignore` only with justification, matching existing policy).
- Nightly healthcheck + integration test scripts updated for new services.
- Actionlint/shellcheck unaffected unless workflows change.

### 4.8 Crowdsec bouncer — ✅ DECIDED 2026-08-28 (Traefik middleware plugin)

**Decision: in-process Traefik middleware plugin, NOT a sidecar.** Crowdsec has no
first-party sidecar/forwardAuth bouncer for Traefik — the plugin *is* the
integration, and it's community-maintained (docs confirm). Plugin:

- `github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin` **v1.7.1** (Traefik
  plugin catalog, 2026-08-28; docs quickstart pins v1.4.5 — use the newer v1.7.1)
- **`crowdsecMode: stream`** (recommended by docs): banned-IP cache in Traefik,
  refreshed from LAPI every 60s; no per-request LAPI calls
- LAPI reachable over `bearcave`: `http://crowdsec:8080` (internal; host port
  18080 only for external `cscli` admin, optional)

Deployment steps (Phase 2):

1. **Static config** — add to `config/traefik/traefik.yml`:
   ```yaml
   experimental:
     plugins:
       crowdsec:
         moduleName: github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin
         version: v1.7.1
   ```
   → Traefik downloads the plugin at startup (network needed) and **restarts**
   (seconds-long route blip).
2. **Bouncer key** — `docker exec crowdsec cscli bouncers add traefik-plugin`;
   write the key to `config/crowdsec/bouncer-key` (gitignored) and mount it into
   Traefik read-only. The middleware uses `crowdsecLapiKeyFile` — **never** put
   the key in a committed dynamic file or label.
3. **Dynamic middleware** — new file `config/traefik/dynamic/crowdsec.yml`:
   ```yaml
   http:
     middlewares:
       crowdsec:
         plugin:
           bouncer:
             enabled: true
             crowdsecMode: stream
             crowdsecLapiScheme: http
             crowdsecLapiHost: crowdsec:8080
             crowdsecLapiPath: /
             crowdsecLapiKeyFile: /etc/traefik/crowdsec/bouncer-key
   ```
   Mount `./config/crowdsec/bouncer-key` into the traefik container.
4. **Attach to routers** — add to **every** Traefik-fronted service's labels in
   `docker-compose.yml` (~20 services):
   `traefik.http.routers.<name>.middlewares=crowdsec@file`
   (mechanical; Plex is unaffected — it's host-network, not behind Traefik).
5. **Verify** — `cscli decisions add --ip <test-ip>` then confirm HTTP 403 for
   that IP through any nip.io host; remove the decision after.

Risks/notes:

- Community plugin → pin version, bump deliberately, watch the repo for breakage
  on Traefik upgrades (Traefik v3.7 compatible as of check).
- LAN-only exposure means crowdsec's value is community blocklists (CAPI) +
  defense-in-depth if any host ever gets exposed; keep default ban durations and
  watch for false positives on LAN clients (`cscli alert list`).
- Traefik dashboard keeps its existing basic-auth middleware; bouncer stacks on
  top harmlessly.

---

## 5. Proposed Phasing & Ordering

**Phase 1a — quick win:** Bazarr (no nzbdav category changes; pure add-on to Radarr/Sonarr/Plex).

**Phase 1b — acquisition:** Lidarr + Readarr together (shared nzbdav-category + Prowlarr work).

**Phase 1c — new content types:** Audiobookshelf + Komga (serve their own content; download via pipeline).

**Phase 2 — network layer:** AdGuard Home (needs router DHCP change — coordinate timing; brief DNS disruption when switching) + Crowdsec (LAPI + bouncer).

**Phase 3 — utilities:** Uptime Kuma (fast win), Vaultwarden, n8n (first workflow: Discord notifications).

Rationale: dependencies first (Bazarr needs nothing new; Lidarr/Readarr share pipeline work; servers build on the extended categories; network tools change topology so they land after media settles; utilities are independent).

---

## 6. Proposed Port Allocations (conflict-checked against existing map)

Existing host ports in use (live `ss` + `docker ps`, 2026-08-28): 80/443 (traefik), 3000 (nzbdav), 3001 (grafana), 3100 (loki), 5055 (seerr), 7878 (radarr), 8000 (landing), 8080 (cadvisor), 8705 (watchstate), 8765 (metacache), 8989 (sonarr), 9090 (prometheus), 9093 (alertmanager), 9100 (node-exporter, host net), 9696 (prowlarr), 11011 (cleanuparr), 41789 (arr-dashboard). Non-stack listeners: 22 (ssh), 32400 (Plex host net), 27036/27060/6463/1716/9323 (Steam/Discord/KDE-Connect/dockerd), 53 on **loopback only** (systemd-resolved stub).

| Service | Container port | Proposed host port | Note |
|---------|---------------|--------------------|------|
| Lidarr | 8686 | 8686 | |
| Readarr | 8787 | 8787 | |
| Bazarr | 6767 | 6767 | |
| Audiobookshelf | 80 | 13378 | |
| Komga | 25600 | 25600 | |
| AdGuard Home | 53 + 3000 web | 53/53 (tcp+udp), **3003** | 3000 host taken by nzbdav → map web to 3003 |
| Crowdsec LAPI | 8080 | **18080** | 8080 host taken by cadvisor |
| Uptime Kuma | 3001 | **3002** | 3001 host taken by grafana |
| Vaultwarden | 80 | **8222** | |
| n8n | 5678 | 5678 | |

> All ports must be re-verified at implementation; the list above is the proposal.

### Live validation (2026-08-28) — ✅ all 10 proposed ports FREE

Checked every proposed host port against the live `ss` table and `docker ps`:
`8686, 8787, 6767, 13378, 25600, 3003, 18080, 3002, 8222, 5678` — all free, no
collisions with the existing 19 published ports or non-stack listeners.
Ephemeral range is 32768–60999, so none of the proposals (all < 32000) clash
with outbound connections.

**Port 53 nuance (AdGuard):** systemd-resolved binds `127.0.0.53:53`/`127.0.0.54:53`
(loopback only) — no conflict with AdGuard publishing `0.0.0.0:53`, which serves
LAN clients. The host itself keeps using systemd-resolved (its stub resolves to
the router) unless we point the host at AdGuard too — **not part of the DHCP
cutover**; decide separately whether the host should also filter.

**Firewall note (AdGuard UDP):** the nftables `DOCKER` chain currently has
**tcp-only** accept rules (no stack container publishes UDP). Docker adds UDP
accept rules automatically when a container publishes `53/udp` — verify
`udp dport 53 accept` appears in the chain after first `up`; if the LAN can't
resolve afterward, that rule is the first place to look.

---

## 7. Resource Allocation (tailored)

| Tier | Limit | Services |
|------|-------|----------|
| Tiny | 128m / 0.25 CPU | AdGuard, Uptime Kuma, Crowdsec LAPI, Bazarr |
| Small | 256m / 0.5 CPU | Vaultwarden, Readarr |
| Medium | 512m / 0.5–1.0 CPU | Lidarr, Audiobookshelf, n8n |
| Larger | 1g / 1.0 CPU | Komga |

> Syncthing tier removed with the service.

---

Host headroom: ~10G free RAM, 16 cores — comfortable. Adjust after 48h of real usage (check `docker stats`).

---

## 8. Env Vars & Secrets (proposed additions)

```
# Phase 1 — *arr-style API keys (copied from app config after first boot)
LIDARR_API_KEY=changeme
READARR_API_KEY=changeme

# Phase 3
VAULTWARDEN_ADMIN_TOKEN=changeme        # admin panel (sign-in page shows token warning if unset)
N8N_ENCRYPTION_KEY=changeme             # n8n requires one
N8N_BASIC_AUTH_USER=changeme            # optional native basic auth
N8N_BASIC_AUTH_PASSWORD=changeme
```

- AdGuard/Crowdsec/Kuma: credentials configured through their own UIs/APIs at first setup (no env vars).
- All new vars go in `.env.template` **and** `.github/required-secrets.json`.

---

## 9. Config & Data Layout

```
./config/lidarr/          # Phase 1
./config/readarr/
./config/bazarr/
./config/audiobookshelf/  # includes metadata/thumbnails DB
./config/komga/
./config/adguard/         # Phase 2
./config/crowdsec/
./config/uptime-kuma/     # Phase 3 (SQLite)
./config/vaultwarden/     # SQLite + attachments
./config/n8n/

./media/music/            # Plex music library target (Phase 1b)
./media/books/
./media/audiobooks/
./media/comics/
```

- Acquisition staging lives on the FUSE mount (`/mnt/remote/nzbdav/<category>/`) like movies/shows.
- Backup scope: **config dirs only** (§3).

---

## 10. Open Questions / To Confirm at Implementation

1. ~~Syncthing~~ — **removed from scope** (user decision 2026-08-28).
2. **n8n workflows** — first workflow confirmed: Discord notifications (import/grab/failure events from Radarr, Sonarr, Lidarr, nzbdav → Discord webhook). Concrete node graph built at deploy.
3. ~~Crowdsec bouncer mechanism~~ — ✅ **RESOLVED 2026-08-28**: in-process Traefik middleware plugin, `maxlerebourg/crowdsec-bouncer-traefik-plugin` **v1.7.1** (current catalog version; module `github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin`), **stream mode** — see §4.8. No sidecar: Crowdsec ships **no** first-party Traefik sidecar/forwardAuth bouncer; the plugin *is* the integration (docs explicitly call it community-maintained — pin the version and bump deliberately).
4. ~~nzbdav category support~~ — ✅ **RESOLVED**: verified live 2026-08-28; arbitrary names config-driven via `NZBDAV_CONFIG__API__CATEGORIES` (§4.2).
5. **Prowlarr app types** — whether Prowlarr supports Lidarr/Readarr app sync (it does for standard *arr; verify Audiobookshelf/Komga aren't indexer apps).
6. **Bazarr + Plex path** — Bazarr needs access to the media folders to place subs; wire the same FUSE/mount paths as sonarr/radarr.
7. **AdGuard router change timing** — plan the DHCP/DNS cutover window with the user.
8. **Per-service health endpoints** — confirm each image's healthcheck path at implementation.
9. **Image source** — hotio for Lidarr/Bazarr (matches stack); **linuxserver for Readarr** (no hotio image); official upstream for Audiobookshelf/Komga/AdGuard/Vaultwarden/n8n; Uptime Kuma `louislam/uptime-kuma:2.5.3-slim-rootless` (**slip candidate**, §14); Crowdsec `crowdsecurity/crowdsec` + Traefik plugin. Pin where CVE-prone or unstable (Readarr!, komga `1.x`). See §14.

---

## 11. Definition of Done (per phase)

For every service in the phase:
- [ ] Compose block with `<<: *common` (or tailored overrides), healthcheck, Traefik labels
- [ ] `docker compose config --quiet` passes; `docker compose up` healthy; healthcheck green
- [ ] Reachable at `https://<name>.${HOST_IP}.nip.io` over HTTPS (native auth where applicable)
- [ ] `.env.template` + `.github/required-secrets.json` updated; `.env` populated
- [ ] Landing page: `service-registry.json` **and** inline `index.html` copy both updated; card renders
- [ ] `docs/services/<name>.md` written
- [ ] Trivy scan of the image is clean or suppressed with justification in `.trivyignore`
- [ ] Config dir added to the backup playbook (config-only scope)
- [ ] `AGENTS.md` service table + port map updated
- [ ] Phase 1 additionally: nzbdav categories + Prowlarr registration verified end-to-end with a real test grab

---

## 12. Summary of User Preferences (single source of truth)

| Pref | Value |
|------|-------|
| What | 10 containers, phased |
| Not wanted | stats, transcode, Kometa-style meta mgmt, Jellyfin/Emby, torrents |
| Media pipeline | Same as Radarr/Sonarr (Prowlarr → nzbdav → FUSE) |
| Serving | New tools may serve own content |
| Citizenship | Full (bearcave + Traefik + config + healthcheck) |
| Auth | Native only |
| Updates | Per-tool judgment |
| Docs | Cards + docs pages for all |
| Backups | Config only |
| Resources | Tailored |
| AdGuard | Full LAN DNS |
| Crowdsec | Active blocking |
| n8n | Discord notifications first (pipeline glue later) |

---

## 13. Appendix — Draft Compose Blocks, Phases 1–3 (not applied)

Draft-only; follows stack conventions (`*common` anchor, bearcave, healthcheck,
Traefik labels). **Not for deployment until approved.**

> ⚠️ nzbdav pipeline change is required first (§4.2): extend
> `NZBDAV_CONFIG__API__CATEGORIES` — requires a recreate **when the queue is empty**.

### Lidarr (hotio, matches *arr pattern)

```yaml
  lidarr:
    <<: *common
    image: ghcr.io/hotio/lidarr:release
    container_name: lidarr
    mem_limit: 512m
    cpus: "0.5"
    networks: [bearcave]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8686/ping || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    depends_on:
      nzbdav_rclone:
        condition: service_healthy
        restart: true
    volumes:
      - *ca-mount
      - ./config/lidarr:/config
      - /mnt/remote/nzbdav:/mnt/remote/nzbdav:rslave
      - ./media/music:/data/music
    ports:
      - "8686:8686"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.lidarr.rule=Host(`lidarr.${HOST_IP}.nip.io`)"
      - "traefik.http.services.lidarr.loadbalancer.server.port=8686"
      - "traefik.http.routers.lidarr.tls=true"
```

### Readarr (linuxserver — **no hotio image exists**; see §14 image findings)

```yaml
  readarr:
    <<: *common
    # Readarr has NO hotio image and NO stable release — linuxserver ships
    # develop/nightly builds only. Pinned versioned tag (verified 2026-08-28);
    # bump deliberately (matches per-tool update judgment).
    image: linuxserver/readarr:develop-0.4.18.2805-ls157
    container_name: readarr
    mem_limit: 256m
    cpus: "0.5"
    networks: [bearcave]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8787/ping || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    depends_on:
      nzbdav_rclone:
        condition: service_healthy
        restart: true
    volumes:
      - *ca-mount
      - ./config/readarr:/config
      - /mnt/remote/nzbdav:/mnt/remote/nzbdav:rslave
      - ./media/books:/data/books
    ports:
      - "8787:8787"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.readarr.rule=Host(`readarr.${HOST_IP}.nip.io`)"
      - "traefik.http.services.readarr.loadbalancer.server.port=8787"
      - "traefik.http.routers.readarr.tls=true"
```

### Bazarr (subtitles; no nzbdav category needed — reads media folders)

```yaml
  bazarr:
    <<: *common
    image: ghcr.io/hotio/bazarr:release
    container_name: bazarr
    mem_limit: 128m
    cpus: "0.25"
    networks: [bearcave]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:6767/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    depends_on:
      nzbdav_rclone:
        condition: service_healthy
        restart: true
    volumes:
      - *ca-mount
      - ./config/bazarr:/config
      - /mnt/remote/nzbdav:/mnt/remote/nzbdav:rslave
      - ./media/movies:/data/movies
      - ./media/shows:/data/shows
      - ./media/anime-movies:/data/anime-movies
      - ./media/anime-shows:/data/anime-shows
    ports:
      - "6767:6767"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.bazarr.rule=Host(`bazarr.${HOST_IP}.nip.io`)"
      - "traefik.http.services.bazarr.loadbalancer.server.port=6767"
      - "traefik.http.routers.bazarr.tls=true"
```

> Bazarr config: point it at Radarr/Sonarr (API keys from `.env`) and the media
> paths above. It does **not** need nzbdav categories — subtitles are fetched
> directly from subtitle providers.

### Audiobookshelf (serves own content; watches folders — no download-client integration)

```yaml
  audiobookshelf:
    image: ghcr.io/advplyr/audiobookshelf:latest
    container_name: audiobookshelf
    mem_limit: 512m
    cpus: "0.5"
    user: "${PUID}:${PGID}"   # official image has no PUID/PGID env support
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
    volumes:
      - *ca-mount
      - ./config/audiobookshelf:/config
      - ./media/audiobooks:/audiobooks
      - ./media/books:/books
      - ./media/podcasts:/podcasts
    ports:
      - "13378:80"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:80/ >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.audiobookshelf.rule=Host(`audiobookshelf.${HOST_IP}.nip.io`)"
      - "traefik.http.services.audiobookshelf.loadbalancer.server.port=80"
      - "traefik.http.routers.audiobookshelf.tls=true"
```

> Acquisition: no *arr exists for audiobooks — manual NZB grabs into nzbdav
> (`audiobooks` category) land in `/mnt/remote/nzbdav/audiobooks`, then get
> imported/symlinked into `./media/audiobooks` (or ABS Watch folder scans it).

### Komga (comics/manga; serves own content — watches folders)

```yaml
  komga:
    image: gotson/komga:1.x   # 1.x = current minor; passes CVE gate w/ draft ignores (§14)
    container_name: komga
    mem_limit: 1g
    cpus: "1.0"
    user: "${PUID}:${PGID}"
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
    volumes:
      - *ca-mount
      - ./config/komga:/config
      - ./media/comics:/comics
    ports:
      - "25600:25600"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:25600/actuator/health | grep -q UP || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.komga.rule=Host(`komga.${HOST_IP}.nip.io`)"
      - "traefik.http.services.komga.loadbalancer.server.port=25600"
      - "traefik.http.routers.komga.tls=true"
```

> Acquisition: manual NZB grabs into nzbdav (`comics` category) → FUSE → symlink
> into `./media/comics`; Komga scans the library folder.

---

### Phase 2 blocks — AdGuard Home + Crowdsec

### AdGuard Home (network-wide DNS blocker; becomes LAN DNS via router DHCP)

```yaml
  adguard:
    image: adguard/adguardhome:latest
    container_name: adguard
    mem_limit: 128m
    cpus: "0.25"
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
      PUID: ${PUID}      # official image supports PUID/PGID — verify at deploy
      PGID: ${PGID}
    volumes:
      - *ca-mount
      - ./config/adguard/conf:/opt/adguardhome/conf
      - ./config/adguard/work:/opt/adguardhome/work
    ports:
      - "53:53/tcp"
      - "53:53/udp"
      - "3003:3000"        # web UI: container 3000, host 3000 taken by nzbdav → 3003
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3000/control/health >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.adguard.rule=Host(`adguard.${HOST_IP}.nip.io`)"
      - "traefik.http.services.adguard.loadbalancer.server.port=3000"
      - "traefik.http.routers.adguard.tls=true"
```

> **LAN DNS cutover (the invasive part, §10 Q7):** container stays on `bearcave`
> (published ports bind all host interfaces), so LAN clients can point at
> `HOST_IP:53` — but the plan is to switch the **router's DHCP** to advertise
> `HOST_IP` as DNS. Keep the router's own DNS as secondary until filtering is
> confirmed. AdGuard's built-in **DHCP server** is deliberately OFF (would need
> `NET_ADMIN` + host-network binding) — router DHCP stays authoritative.

### Crowdsec (intrusion detection + active blocking; LAPI for the Traefik bouncer)

```yaml
  crowdsec:
    image: crowdsecurity/crowdsec:latest
    container_name: crowdsec
    mem_limit: 128m
    cpus: "0.25"
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
      UID: ${PUID}       # official image uses UID/GID envs (not PUID/PGID) — verify
      GID: ${PGID}
      COLLECTIONS: crowdsecurity/linux crowdsecurity/traefik
    volumes:
      - *ca-mount
      - ./config/crowdsec:/etc/crowdsec
      - ./config/crowdsec/data:/var/lib/crowdsec/data
      # optional: container-log acquisition via Docker socket (read-only) —
      # crowdsec's default `docker` acquisition source; skip if unused
      # - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - "18080:8080"   # LAPI: host 8080 taken by cadvisor → 18080; external cscli only — can comment out
    healthcheck:
      test: ["CMD-SHELL", "cscli lapi status >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    # NO Traefik router — LAPI is an API for bouncers/cscli, not a web UI.
    # The bouncer (Traefik middleware plugin, §4.8) reaches it over bearcave
    # at http://crowdsec:8080. No `depends_on` needed on traefik: the plugin
    # tolerates LAPI downtime (stream mode reconnects every 60s).
```

> **Bouncer wiring (from §4.8, requires a Traefik restart):**
> 1. `docker exec crowdsec cscli bouncers add traefik-plugin` → write the key to
>    `config/crowdsec/bouncer-key` (gitignored) → mount into traefik read-only.
> 2. `experimental.plugins` block in `config/traefik/traefik.yml`
>    (`github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin` v1.7.1).
> 3. `config/traefik/dynamic/crowdsec.yml` middleware (`crowdsecMode: stream`,
>    `crowdsecLapiHost: crowdsec:8080`, `crowdsecLapiKeyFile`).
> 4. Attach `crowdsec@file` middleware to **every** Traefik-fronted service's
>    labels (~20, mechanical). Plex unaffected (host network).
> 5. Optional CAPI enroll for community blocklists: `cscli console enroll`.
>    Acquisitions/parsers configured in `./config/crowdsec` (acquis.d, profiles.yaml).

### Phase 3 blocks — Uptime Kuma, Vaultwarden, n8n

### Uptime Kuma (status/uptime dashboard) — ⚠️ flagged for Phase 3 slip (§14)

```yaml
  uptime-kuma:
    # ⚠️ CVE gate: NO tag clears CRITICAL (2026-08-28). Best = slim-rootless
    # (bookworm, UID 1000, 12 CRITICAL — live jsonata/protobufjs/grpc deps).
    # Re-check before Phase 3; if still red, this service slips (see §14).
    image: louislam/uptime-kuma:2.5.3-slim-rootless
    container_name: uptime-kuma
    mem_limit: 128m
    cpus: "0.25"
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
    volumes:
      - *ca-mount
      - ./config/uptime-kuma:/app/data
    ports:
      - "3002:3001"      # web UI: container 3001, host 3001 taken by grafana → 3002
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3001/ >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.uptime-kuma.rule=Host(`uptime-kuma.${HOST_IP}.nip.io`)"
      - "traefik.http.services.uptime-kuma.loadbalancer.server.port=3001"
      - "traefik.http.routers.uptime-kuma.tls=true"
```

> `2.5.3-slim-rootless` runs as UID 1000 (no PUID/PGID env needed; no root).
> **Deploy only if re-scan is green or the slip decision is made** — see the
> §14 tag-sweep table. Watch the 128m cap (Node + SQLite — §7 may need a bump).

### Vaultwarden (self-hosted password manager)

```yaml
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    mem_limit: 256m
    cpus: "0.5"
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
      VAULTWARDEN_ADMIN_TOKEN: ${VAULTWARDEN_ADMIN_TOKEN}
      SIGNUPS_ALLOWED: "false"    # invite-only after first admin; set true for first account
      WEBSOCKET_ENABLED: "true"   # live vault sync; same port, no extra Traefik work
    volumes:
      - *ca-mount
      - ./config/vaultwarden:/data
    ports:
      - "8222:80"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:80/alive >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.vaultwarden.rule=Host(`vaultwarden.${HOST_IP}.nip.io`)"
      - "traefik.http.services.vaultwarden.loadbalancer.server.port=80"
      - "traefik.http.routers.vaultwarden.tls=true"
```

> `SIGNUPS_ALLOWED=false` in the draft — set to `true` once to create the first
> account, then back to `false` (or use `INVITATIONS_ALLOWED=true`). Admin panel
> at `/admin` guarded by `VAULTWARDEN_ADMIN_TOKEN` (native auth only, §3).

### n8n (workflow automation; first workflow: Discord notifications)

```yaml
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    mem_limit: 512m
    cpus: "0.5"
    restart: unless-stopped
    logging: *common-logging
    networks: [bearcave]
    environment:
      <<: *ca-env
      TZ: ${TZ}
      GENERIC_TIMEZONE: ${TZ}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: ${N8N_BASIC_AUTH_USER}
      N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD}
      N8N_HOST: n8n.${HOST_IP}.nip.io      # webhook URLs use this externally
      N8N_PROXY_HOPS: "1"                  # behind Traefik
      N8N_SECURE_COOKIE: "false"           # Traefik terminates TLS; verify after deploy
    volumes:
      - *ca-mount
      - ./config/n8n:/home/node/.n8n
    ports:
      - "5678:5678"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:5678/healthz >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`n8n.${HOST_IP}.nip.io`)"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
      - "traefik.http.routers.n8n.tls=true"
```

> The official image runs as its own `node` user — **do not** override with
> `user: ${PUID}:${PGID}` (data dir ownership breaks). `N8N_SECURE_COOKIE`
> depends on how the browser reaches it; flip to `true` if the client talks
> HTTPS end-to-end. Webhook URLs advertise `N8N_HOST` — fine for LAN. Discord
> notification workflow: webhook node triggered by Radarr/Sonarr/Lidarr/nzbdav
> events (see §10 Q2).

### Notes on the drafts
- `hotio/*:release` tags auto-update via the stack's watchtower mechanism.
- All healthcheck endpoints (`/ping`, `/api/health`, `/actuator/health`,
  `/control/health`, `cscli lapi status`, `/`, `/alive`, `/healthz`) to be
  re-verified against the actual images at deploy time.
- `user: ${PUID}:${PGID}` only where the official image lacks PUID/PGID env
  (Audiobookshelf, Komga) — **verify at deploy**; hotio images handle it via env.
- **AdGuard** publishes host `53/tcp+udp` — the only new low-range host ports;
  nothing else in the stack uses 53. The web-UI publish (3003) and Traefik route
  are for admin; DNS service itself is `HOST_IP:53` on the LAN.
- **Crowdsec** has no Traefik router and no bouncer sidecar container — the
  bouncer is the in-process Traefik plugin (§4.8). Enabling it restarts Traefik
  (seconds-long route blip); stage it outside the AdGuard DHCP cutover window.
- 128m/0.25 for Crowdsec is tight — watch `docker stats` after 48h (§7 tier may
  need a bump; parsers + acquisition can spike).
- **Uptime Kuma** at 128m/0.25 is also tight (Node + SQLite) — likely needs a
  Small-tier bump after 48h of real use; port 3002/container 3001 confirmed in
  §6. No PUID/PGID env support (runs as root; verify data-dir ownership).
- **Vaultwarden** native admin auth via `VAULTWARDEN_ADMIN_TOKEN` (§8) — no
  Traefik basic-auth layer per §3; `SIGNUPS_ALLOWED` flipped true once at setup.
- **n8n** needs `N8N_ENCRYPTION_KEY` before first start (§8) — generated once,
  stored in `.env`; rotation means re-encrypting credentials. Runs as its own
  `node` user — no PUID/PGID override. Native basic auth via `N8N_BASIC_AUTH_*`
  (no Traefik layer).

---

## 14. Image Verification Findings (2026-08-28)

All 10 deployable images re-verified live with `docker manifest inspect` on
2026-08-28 (no pulls) — **10/10 resolve**, digests recorded below:

| Image | Exists? | Resolved digest (prefix) | Notes |
|-------|---------|--------------------------|-------|
| `ghcr.io/hotio/lidarr:release` | ✅ | `sha256:ba6e44dad2342e3225…` | Matches stack convention; watchtower-auto-updatable |
| `ghcr.io/hotio/bazarr:release` | ✅ | `sha256:be98ebc3523b49ff8d…` | |
| `ghcr.io/advplyr/audiobookshelf:latest` | ✅ | `sha256:e388e90e381ae3fa86…` | Official |
| `gotson/komga:1.x` | ✅ | `sha256:e755c9691aa8ec38e2…` | Official; **`1.x` pin** — passes CVE gate with draft ignores (§14) |
| `adguard/adguardhome:latest` | ✅ | `sha256:678640ae9987aff621…` | |
| `crowdsecurity/crowdsec:latest` | ✅ | `sha256:95a25d0f0fb92d9620…` | Bouncer: **Traefik middleware plugin** (see §4.8) — no sidecar container needed |
| `louislam/uptime-kuma:2.5.3-slim-rootless` | ✅ | — | Best tag (bookworm, UID 1000) — **slip candidate** if gate stays red (§14) |
| `vaultwarden/server:latest` | ✅ | `sha256:5d326778c22f063d09…` | |
| `n8nio/n8n:latest` | ✅ | `sha256:6b3a46d63a081e0c7f…` | |
| `linuxserver/readarr:develop-0.4.18.2805-ls157` | ✅ | `sha256:fc5552ceaa09cd31a4…` | **Use this pinned tag**; bump deliberately (0.4.x = revived-project dev builds) |
| `ghcr.io/hotio/readarr:*` | ❌ | — | **hotio does not publish Readarr at all** |
| `linuxserver/readarr:latest` | ❌ | — | No `latest` — Readarr has no stable release |
| `linuxserver/readarr:develop` / `:nightly` | ⚠️ | — | Listed in Hub API but manifest does not resolve (as of check) |

Digests are floating-tag snapshots for reference — `:latest`/`:release` tags
move, so re-verify at deploy. Readarr stays **pinned** (only reliable tag).

### CVE posture scan (2026-08-28, trivy 0.74.0, `CRITICAL,HIGH`)

Scanned all 10 images with the exact `trivy-scan.yml` invocation. **Result:
35 CRITICAL / 912 HIGH** — the CI gate fails on any CRITICAL, so adding these
images to compose **will break the trivy-scan workflow** (push + weekly)
until remediated. Current stack baseline: 20 images, **0 CRITICAL** (the
`fix(security): eliminate 15 CRITICAL CVEs` commit holds the line).

| Image | CRITICAL | HIGH | Notable CVEs (CRITICAL) |
|-------|----------|------|-------------------------|
| `louislam/uptime-kuma:1` | **13** | 220 | stdlib v1.20.5/v1.24.4 (CVE-2024-24790, CVE-2025-68121), zlib1g CVE-2023-45853, protobufjs, liquidjs, jsonata, fast-xml-parser, grpc |
| `gotson/komga:latest` | **9** | 207 | stdlib v1.17.8 (CVE-2023-24538/24540, CVE-2024-24790, CVE-2025-68121), linux-libc-dev 7.0 (5×) |
| `ghcr.io/hotio/lidarr:release` | **5** | 76 | ASP.NET Core 8.0.12 (CVE-2025-55315) — hotio image lags .NET runtime |
| `vaultwarden/server:latest` | **4** | 68 | libmariadb3 11.8.6 (CVE-2026-44172, CVE-2026-49261) |
| `crowdsecurity/crowdsec:latest` | **2** | 241 | kin-openapi v0.137.0 (GHSA-r277-6w6q-xmqw) — Go dep, LAPI HTTP parsing |
| `ghcr.io/advplyr/audiobookshelf:latest` | **2** | 66 | form-data 4.0.0 (CVE-2025-7783), sequelize 6.35.2 (CVE-2026-69240) — Node deps |
| `adguard/adguardhome:latest` | 0 | 2 | |
| `n8nio/n8n:latest` | 0 | 3 | |
| `ghcr.io/hotio/bazarr:release` | 0 | 6 | |
| `linuxserver/readarr:develop-0.4.18.2805-ls157` | 0 | 23 | (pinned tag already the only option) |

**Remediation plan before Phase 1/2 deploy (no pre-emptive `.trivyignore`):**

1. **Re-scan at deploy time** — floating tags (`:latest`/`:release`) move;
   some CRITICALs (e.g. hotio lidarr's stale .NET 8.0.12) may clear on an
   upstream rebuild. The digests above pin what was scanned 2026-08-28.
2. **Prioritize by reachability:** uptime-kuma + komga (22 of 35 CRITICAL) are
   the worst; check for newer tags/pinned versions that drop below the gate.
3. **Suppress only with justification** per existing `.trivyignore` policy
   (e.g. `linux-libc-dev` in komga = host-kernel headers, not shipped binaries).
4. **Merge order:** land the compose changes in a PR and let the trivy scan
   report the live gate result before merging — do not merge with the gate
   red. If a CRITICAL can't be cleared, that image's phase slips until it can.

### Draft `.trivyignore` entries (apply only when the phase lands — 11 of 35 CRITICALs)

Verified reachability in the actual images (2026-08-28). **Only dead-code and
scan-artifact findings are drafted below.** The other 24 CRITICALs (uptime-kuma
13, lidarr 5, crowdsec 2, audiobookshelf 2, vaultwarden… see matrix) are live
runtime code and must NOT be ignored — they need upstream image fixes or a
phase slip (uptime-kuma is the standout: EOL buster base).

Apply the block below to `.trivyignore` **in the same change that adds the
images to compose** — never before (policy: entries are current findings only):

```
# ── New-image CRITICAL CVEs (deferred with justification, 2026-08-28) ───────
# Applies when the Phase 1/2 compose blocks (§13) land. Re-verify at deploy:
# floating tags move and re-scans may clear some entries.

# komga (gotson/komga:1.x): linux-libc-dev = "Linux Kernel Headers for
# development" — compile-time-only package (verified installed, no runtime
# code). Kernel CVEs do not affect the shipped Java app. Track: upstream base
# image change — remove if a slimmer base drops the package.
CVE-2026-53398 # komga linux-libc-dev headers — not runtime code
CVE-2026-64535 # komga linux-libc-dev headers — not runtime code
CVE-2026-64564 # komga linux-libc-dev headers — not runtime code
CVE-2026-72287 # komga linux-libc-dev headers — not runtime code
CVE-2026-74394 # komga linux-libc-dev headers — not runtime code

# komga (gotson/komga:1.x): trivy reports Go stdlib v1.17.8 (CVE-2023-24538,
# CVE-2023-24540, CVE-2024-24790, CVE-2025-68121) but the image ships NO Go
# runtime/binary — Rust coreutils + komga.jar only (verified via ELF scan).
# Scan artifact from multi-stage build layers. Track: re-scan at deploy.
CVE-2023-24538 # komga Go stdlib — no Go binary ships (scan artifact)
CVE-2023-24540 # komga Go stdlib — no Go binary ships (scan artifact)
CVE-2024-24790 # komga Go stdlib — no Go binary ships (scan artifact)
CVE-2025-68121 # komga Go stdlib — no Go binary ships (scan artifact)

# vaultwarden (vaultwarden/server:latest): libmariadb3 present in image but
# the vaultwarden binary has ZERO MariaDB references (verified via strings;
# default backend is SQLite). Unused client lib. Track: upstream image slims
# its Debian base — remove if libmariadb3 disappears.
CVE-2026-44172 # vaultwarden libmariadb3 — unused (SQLite backend)
CVE-2026-49261 # vaultwarden libmariadb3 — unused (SQLite backend)
```

**Tag-sweep results (2026-08-28) — newer tags don't save uptime-kuma; komga
passes with the draft ignores:**

| Image | Tag | Base | CRITICAL | Verdict |
|-------|-----|------|----------|---------|
| uptime-kuma | `:1` / `:latest` | **Debian 10 buster (EOL)** | 13 | Red |
| uptime-kuma | `:2` / `:2.5.3` | bookworm | **134** | Red (worse) |
| uptime-kuma | `2.5.3-slim` | bookworm | **12** | Best option, still red |
| uptime-kuma | `2.5.3-slim-rootless` | bookworm | ~12 (same base), **UID 1000** | Best + least privilege, still red |
| komga | `latest` / `1.x` / `1.26.3` | Ubuntu 26.04 | 9 | **Green if draft ignores applied** (all 9 = suppressible) |

- **komga: resolved.** `1.x` matches `latest` (9 CRITICAL, all in the draft
  block: 5 linux-libc-dev headers + 4 Go-stdlib scan artifacts, verified no
  Go binary ships). Pin `gotson/komga:1.x` and the gate passes.
- **uptime-kuma: unresolved — recommend Phase 3 slip.** No tag clears the
  gate: `:1` is EOL-buster; `:2` jumps to 134; the **`2.5.3-slim-rootless`**
  (bookworm, UID 1000 — best security posture) still has 12, and several are
  live app deps (jsonata 2.1.1 ×3, protobufjs, grpc in the JS bundle —
  reachable; verified no Go toolchain so the 2 stdlib hits are artifacts, and
  node isn't linked against system sqlite/gnutls/zlib, but the JS-deps alone
  keep it red under repo policy). Re-check `2.5.3-slim-rootless` at Phase 3
  time; slip if still red. Do NOT ignore live JSON-parsing deps to force green.

**NOT in this draft (live runtime code — fix upstream, do not ignore):**

| Image | CVEs | Why not ignorable |
|-------|------|-------------------|
| uptime-kuma 2.5.3-slim-rootless | 12 (jsonata, protobufjs, grpc, sqlite3, gnutls, zlib, stdlib) | 2 stdlib = scan artifacts; rest = live app/base deps — see slip note above |
| hotio/lidarr:release | 5 (ASP.NET Core 8.0.12 CVE-2025-55315) | .NET runtime IS the app; hotio image lags upstream — pin newer hotio or wait for rebuild |
| crowdsec:latest | 2 (kin-openapi GHSA-r277-6w6q-xmqw) | Go dep compiled into LAPI which parses HTTP — reachable; track upstream release |
| audiobookshelf:latest | 2 (form-data, sequelize) | Node deps in the running app (sequelize = DB layer) — track upstream |

---

## 15. nzbdav Category Rollout Runbook (queue-gated)

Goal: extend `NZBDAV_CONFIG__API__CATEGORIES` with `music,books,audiobooks,comics`
so the Phase-1 tools can download through the existing pipeline.

### The change

```yaml
# docker-compose.yml, nzbdav service
NZBDAV_CONFIG__API__CATEGORIES: "tv,movies,anime-movies,anime-shows,music,books,audiobooks,comics"
```

Compose recreates the container when the file changes, so this is a normal
config rollout — **not** an image change. The guarded script
`./scripts/update-nzbdav.sh` applies it correctly: its `docker compose up -d
nzbdav` step recreates with the new env, then health-gates the cascade
(rclone remount + radarr/sonarr/plex/unpackerr/cleanuparr restarts).

### Phase 0 — Preparation (any time)

- [ ] Review the exact CATEGORIES edit above; confirm category names match what
      the new apps will send (Lidarr default `music`, Readarr default `books`;
      Audiobookshelf/Komga folders `audiobooks`/`comics` — names are arbitrary
      per docs, keep them consistent).
- [ ] Create media dirs: `./media/music`, `./media/books`, `./media/audiobooks`,
      `./media/comics` (Phase 1 requirement; FUSE side needs nothing — new
      category dirs materialize under `/mnt/remote/nzbdav/` on first use).
- [ ] Have a test NZB ready (any small release) to validate a `cat=music` grab.

### Phase 1 — Queue-empty window (the hard gate)

- [ ] Watch the queue until `slots: 0`:
  ```bash
  KEY=$(grep -E "^FRONTEND_BACKEND_API_KEY=" .env | cut -d= -f2-)
  curl -s "http://localhost:3000/api?apikey=${KEY}&mode=queue&output=json" | \
    python3 -c "import sys,json; print(len(json.load(sys.stdin)['queue'].get('slots',[])))"
  ```
- [ ] Ideally also idle: no active Plex streams over FUSE, no in-flight
      imports (radarr/sonarr CPU low). A new grab during the window would
      repopulate the queue — the script re-checks at execution time, so it
      aborts safely if that happens.
- [ ] **Current state 2026-08-28: queue is EMPTY** — window open at time of
      writing.
- [ ] Never use `--force` (wipes queued NZBs + silent blocklist, landmine #5).

### Phase 2 — Execute (within the window)

```bash
# 1. Make the edit (Phase 0), then:
./scripts/update-nzbdav.sh --dry-run   # preflight + queue re-check; stops
./scripts/update-nzbdav.sh             # pull → up -d nzbdav → cascade → verify
```

Expected: ~5–10 min (nzbdav start_period 60s, mount content check, dependents
health waits). The `:dev` tag pull may also fetch a newer dev build — that's
the script's designed behavior; no separate image bump needed.

### Phase 3 — Post-rollout verification

```bash
KEY=$(grep -E "^FRONTEND_BACKEND_API_KEY=" .env | cut -d= -f2-)
# 1. Categories exposed
curl -s "http://localhost:3000/api?apikey=${KEY}&mode=get_cats&output=json"
#    expect: music,books,audiobooks,comics present
# 2. FUSE still serving
docker exec nzbdav_rclone ls /mnt/remote/nzbdav
#    new category dirs may be absent until first use — not an error
# 3. Test grab (SABnzbd API, category music)
curl -s "http://localhost:3000/api?apikey=${KEY}&mode=addurl&name=<nzb-url>&cat=music"
#    confirm it queues with cat=music, completes, symlink appears in
#    /mnt/remote/nzbdav/completed-symlinks/music; then remove it
# 4. All services green
docker compose ps | grep -c healthy
# 5. Regression: a normal tv/movies grab still works (unchanged categories)
```

### Phase 4 — Rollback (if anything breaks)

- Revert the CATEGORIES line in `docker-compose.yml`.
- Re-run `./scripts/update-nzbdav.sh` (same queue gate applies).
- Categories revert; no other state touched.

### Risks / notes

- The queue guard is the only real gate — respect it.
- Category names are free-form (letters/numbers/dashes); keep them aligned
  between the apps' download-client settings and this env so imports land in
  the right FUSE dirs.
- `NZBDAV_CONFIG__ARR__INSTANCES` may need Lidarr/Readarr entries later if
  nzbdav's arr integration supports them — check at Phase-1 implementation
  (§4.3 note).
