# Landmines

Active issues that affect operations **today**. Read before touching the stack.

---

## Critical

### 1. FUSE mount cascade

`nzbdav_rclone` is the keystone. Restarting it (or nzbdav, which restarts it) cascades
to radarr, sonarr, plex, unpackerr, cleanuparr via `depends_on: restart: true`.

- **Never** restart the mount owner alone and leave dependents running — they hold
  defunct handles.
- **Never** `sudo umount` the mountpoint. The entrypoint's `fusermount3 -uz` /
  `umount -l` preamble is the self-heal — let it do its job.
- If the mount dies mid-scan, Plex can flag thousands of items "deleted". Restore the
  mount, then rescan.

### 2. Plex `stop_grace_period: 90s`

Plex's shutdown takes ~40s under load. The 90s grace period is load-bearing — removing
it reintroduces the unkillable D-state hang (SIGKILL mid-shutdown → wedged container).

### 3. InfiniDysk queue is not persistent

Recreating the nzbdav container **wipes the queue** and silently blocklists affected
items. Always confirm the queue is empty before touching the container.

### 4. Control Panel reads .env at create time only

`docker compose restart control-panel` does **not** pick up `.env` changes.
Use `docker compose up -d --force-recreate control-panel`.

---

## High

### 5. Cleanuparr doesn't auto-register

It discovers *arr apps but needs explicit instance registration in its `arr_instances`
table. Register Radarr + Sonarr after first boot or restores.

### 6. Watchtower only updates channel-tagged images

`ghcr.io/hotio/*:release` images auto-update nightly at 04:00. Digest-pinned images
(seerr, unpackerr) and versioned tags (cleanuparr:2.10.5) are **excluded by design** —
bump them deliberately.

### 7. App removal must be exhaustive

Removing an app touches: compose block, config dir, `.env` vars, Prowlarr sync,
Cleanuparr rows, Control Panel references, Traefik labels, tests. Miss one and you get
a half-removed service.

### 8. rclone.conf needs `rclone obscure`

The WebDAV password in `config/nzbdav-rclone/rclone.conf` must be rclone-obfuscated
(`rclone obscure "pass"`), not plaintext. The file is gitignored — the committed
`rclone.conf.template` is the only thing that ships.

---

## Medium

### 9. Plex scheduled scan only

`FSEventLibraryUpdatesEnabled` is disabled; scanning is scheduled (6h). New content
doesn't appear instantly — trigger a scan from Plex/Control Panel for immediacy.

### 10. WatchState import window

WatchState's import skips 02:00–05:59 deliberately (SQLite write-contention window
shared with poster sync, arr backup, Plex Butler). Don't schedule other Plex DB writers
into that window.

### 11. Traefik + Plex separation

Plex is not behind Traefik (host network). Anyone expecting "everything through one
port" will be confused — document `:32400` for Plex.

### 12. Linux-only host resolution

Prometheus reaches node-exporter via `host.docker.internal:9100`. This works on Linux
(extra_hosts → host-gateway) but not on Docker Desktop. The stack is Linux-only.

### 13. HTTPS is a local CA — Let's Encrypt can never work here

All `*.nip.io` hostnames serve the mkcert-signed wildcard cert (wired in as Traefik's
default certificate via `config/traefik/dynamic/tls.yml`). Let's Encrypt **cannot**
issue for these names: the ACME HTTP-01 challenge requires a publicly reachable host,
and `*.192.168.4.20.nip.io` resolves to a private LAN IP. Do **not** re-add a
`certificatesResolvers` block expecting it to work — it only spams errors and falls
back to the self-signed default cert (see git history: `ef2ab3c`).

- A browser warning on a device means the **local CA isn't installed there** — run
  `scripts/trust-ca.sh` and follow its per-device steps. Never just dismiss the warning.
- The CA and leaf **private keys** live only on the server (`~/.local/share/mkcert/`,
  `config/traefik/certs/`); devices install only the public `rootCA.pem` (served at
  `https://bearcave.192.168.4.20.nip.io/rootCA.pem`).
- Real public certificates require a public domain pointing at this host with 80/443
  forwarded, then a working `ACME_EMAIL`. Full model in [docs/tls.md](tls.md).

---

## Diagnostics

| Symptom | First thing to check |
|---------|----------------------|
| Plex shows everything deleted | `docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav` |
| Imports stuck "importing" | `docker compose logs nzbdav radarr sonarr \| tail` |
| Services unreachable via nip.io | Traefik up? `docker compose ps traefik` |
| Everything unhealthy | `.env` placeholders? `grep changeme .env` |
| Browser shows certificate warning | CA not installed on that device — `scripts/trust-ca.sh` |
| Metacache "Fix Match" spam | Cache warm status: `curl localhost:8765/warm/status` |
