# Expansion Deployment Checklist

This checklist activates the expansion services only after explicit operator
approval. Repository configuration can be validated without starting or
restarting containers; the commands below are intentionally separated into
read-only preparation and state-changing rollout steps.

## Current state

- 29 services are configured and running in `docker-compose.yml`.
- 8 expansion services are deployed: Bazarr, Lidarr, Readarr, Audiobookshelf,
  Komga, AdGuard Home, CrowdSec, and Vaultwarden. (Uptime Kuma and n8n were
  removed from scope by decision.)
- The nzbdav category rollout is applied: categories now support music, books,
  audiobooks, and comics alongside the original movie/TV paths.
- `.env` contains locally generated values for Vaultwarden and is gitignored
  with mode `0600`. Never commit or print those values.

## Read-only preflight

Run from the repository root:

```bash
git status --short --branch
docker compose config --quiet
bash -n scripts/*.sh tests/*/*.sh
python3 scripts/check_action_pins.py --json
```

Verify the new image tags with Trivy before deployment. Do not add a CVE ignore
for a live runtime vulnerability merely to force the gate green.

Confirm required local values exist without printing them:

```bash
python3 - <<'PY'
from pathlib import Path
keys = {
    "VAULTWARDEN_ADMIN_TOKEN",
}
values = {}
for line in Path(".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        key, value = line.split("=", 1)
        if key in keys:
            values[key] = value
assert all(values.get(key) not in (None, "", "changeme") for key in keys)
print("required expansion secrets are populated")
PY
```

## Phase 1 activation

### Bazarr only

Bazarr does not require an nzbdav category change. After explicit approval,
start only the service and its declared dependencies as needed:

```bash
docker compose up -d bazarr
```

Then verify its health and configure Radarr/Sonarr API connections and subtitle
providers through its native UI.

### Lidarr/Readarr and content servers

Before starting these services, apply the nzbdav category change only when the
queue is empty and the operator explicitly accepts the restart cascade:

```bash
./scripts/update-nzbdav.sh --dry-run
# Review output, then separately authorize the real guarded rollout.
```

The real rollout recreates nzbdav and cascades through the FUSE mount dependents.
Do not use `--force`. Afterward, configure categories `music`, `books`,
`audiobooks`, and `comics`, then register Lidarr/Readarr with Prowlarr.

## Phase 2 activation

### AdGuard Home

1. Start AdGuard without changing router DHCP.
2. Complete the initial web setup at port `3003`.
3. Test DNS from a single client using the host IP.
4. Confirm TCP and UDP port 53 are reachable.
5. Schedule the router DHCP DNS change separately; keep the router DNS as a
   fallback until filtering is confirmed.

Do not switch the LAN DNS during an unrelated stack or Traefik change window.

### CrowdSec

1. Start CrowdSec and confirm its LAPI health.
2. Configure acquisition/parsers and inspect alerts.
3. Create the bouncer key inside the container.
4. Store it only at the gitignored runtime path.
5. Configure the pinned Traefik plugin and middleware.
6. Restart Traefik only after explicit approval.
7. Test a temporary decision and remove it immediately afterward.

The current repository does not activate the Traefik plugin or attach the
middleware, which is intentional.

## Phase 3 activation

### Vaultwarden

- Confirm `VAULTWARDEN_ADMIN_TOKEN` is non-empty and unique.
- Start Vaultwarden only after confirming the backup destination.
- Create the first account and verify `/admin` protection.
- Keep signups disabled after initial setup.

## Rollback

For services not yet started, remove the service block in a reviewed commit or
start only the previous service set. Do not run `docker compose down` for a
partial rollback: it would disrupt the existing stack.

For nzbdav, use the guarded script's documented tag rollback only after the
queue is empty and the FUSE cascade is explicitly approved.

## Verification after an approved activation

```bash
docker compose ps
./tests/health/run-all.sh --service <service>
```

For bind-mounted landing-page changes, restart the landing-page container only
with explicit approval; bind-mounted files can remain stale until restart.
