# Backup & Restore

Everything you need to survive hardware failure, bad config edits, or a botched upgrade.

---

## What holds state

| Data | Location | Criticality |
|------|----------|-------------|
| Plex library DB + metadata | `config/plex/` (~33 GB) | **Highest** — irreplaceable watch history |
| *arr DBs | `services/{radarr,sonarr,prowlarr,seerr,cleanuparr}/config/` | High — easily rebuilt but tedious |
| InfiniDysk DB + queue | `config/nzbdav/` | High — **queue is not persistent across recreate** |
| Control Panel DB | `data/control-panel/` | Medium |
| WatchState DB | `config/watchstate/` | Medium — redundant with Plex |
| Metacache DB + images | `data/metacache/` | Low — regenerable via warm |
| Grafana/Prometheus/Loki | `data/{grafana,prometheus,loki}/` | Low — regenerable |
| Secrets | `secrets/` + `.env` | **Critical** — losing these is losing access |

---

## Automated backup

```bash
./scripts/backup.sh                 # full backup to backups/<timestamp>/
./scripts/backup.sh --configs-only  # configs + compose + .env
./scripts/backup.sh --secrets-only  # secrets/ + .env
```

Produces `backups/bearcave_backup_<YYYYMMDD_HHMMSS>/` with:
- `configs/` — every `services/<app>/config/` + root configs
- `databases/` — plex, metacache, watchstate, control-panel DBs
- `secrets/` — `.env` + `secrets/`
- `plex-metadata/` — tar.gz of the Plex config tree

> **Copy backups off-host.** A backup on the same disk as the stack protects against
> config errors, not disk failure. rsync/tar-pipe to another machine or cloud.

---

## InfiniDysk note

InfiniDysk has its **own daily backup** (02:00 local, 7 retained) inside its config —
that's in `config/nzbdav/`. The queue itself is ephemeral: **confirm the queue
is empty before any container operation that recreates it.**

---

## Restore procedure

### 1. Stop the stack

```bash
docker compose down
```

### 2. Restore configs

```bash
# From the backup dir:
cp -r backups/bearcave_backup_<ts>/configs/* services/
cp backups/bearcave_backup_<ts>/.env .env    # if restoring secrets too
```

### 3. Restore Plex (the critical one)

```bash
# Plex must be stopped (stack is down, so it is)
rm -rf config/plex
cp -r backups/bearcave_backup_<ts>/plex-metadata/plex-metadata.tar.gz /tmp/
tar -xzf /tmp/plex-metadata.tar.gz -C services/plex/   # restores config/
```

Verify ownership: Plex runs as UID/GID **955** — the files must be owned by 955:
```bash
chown -R 955:955 config/plex
```

### 4. Restore secrets

```bash
cp -r backups/bearcave_backup_<ts>/secrets/* secrets/ 2>/dev/null || true
```

### 5. Bring it back

```bash
docker compose up -d
./tests/health/run-all.sh
```

---

## Scheduled backup (recommended)

Add a host cron/systemd timer, e.g.:

```bash
# nightly at 03:30, keep 7 days
30 3 * * * cd /home/bear/TheBearCave && ./scripts/backup.sh >> /var/log/bearcave-backup.log 2>&1 && find backups -maxdepth 1 -name 'bearcave_backup_*' -mtime +7 -exec rm -rf {} +
```

> The media-stack archive includes systemd units for the old stack's backup jobs
> (`archive/media-stack/systemd/stack-arr-backup.{service,timer}`) — adapt them for
> this repo's paths.

---

## DR checklist

- [ ] Off-host backup of `backups/` runs nightly
- [ ] You know where `secrets/` lives and have a copy off-host
- [ ] Test a restore at least once (restore to a scratch dir, not the live tree)
- [ ] Plex ownership (955:955) verified after restore
- [ ] Queue confirmed empty before InfiniDysk container operations
