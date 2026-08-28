# Crowdsec

Intrusion detection with active blocking — LAPI + a Traefik middleware-plugin bouncer.

| | |
|---|---|
| **Image** | `crowdsecurity/crowdsec:latest` |
| **Port** | 18080 (LAPI, external cscli only — optional) |
| **Network** | `bearcave` |
| **Healthcheck** | `cscli lapi status` |
| **Config** | `config/crowdsec/` (gitignored) |
| **Env** | `UID`/`GID` (official image convention — not PUID/PGID), `COLLECTIONS` |

## Role

- Detects bad behavior (brute-force, scans) from logs and blocks offending IPs
- **Active blocking** via the Traefik middleware plugin — the bouncer runs
  *inside* Traefik, not as a sidecar container (see the spec §4.8 decision)
- No Traefik router of its own — LAPI is an API for bouncers/`cscli`, not a web UI

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/crowdsec/` | `/etc/crowdsec` | Config (acquis.d, profiles.yaml, sim decisions) |
| `config/crowdsec/data/` | `/var/lib/crowdsec/data` | Local API database |

Optional (commented out in the draft): mount `/var/run/docker.sock` read-only
for container-log acquisition (Crowdsec's default `docker` source).

## Bouncer wiring (one-time, requires a Traefik restart)

1. `docker exec crowdsec cscli bouncers add traefik-plugin` → write the key to
   `config/crowdsec/bouncer-key` (gitignored) → mount into traefik read-only
2. `experimental.plugins` block in `config/traefik/traefik.yml`
   (`github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin` v1.7.1)
3. `config/traefik/dynamic/crowdsec.yml` middleware — `crowdsecMode: stream`,
   `crowdsecLapiHost: crowdsec:8080`, key via `crowdsecLapiKeyFile`
4. Attach `crowdsec@file` middleware to **every** Traefik-fronted service's
   labels (~20, mechanical). Plex is unaffected (host network, not behind Traefik)

Enabling the plugin restarts Traefik (seconds-long route blip) — stage it
**outside** the AdGuard DHCP cutover window.

## First-run

1. `docker compose up -d crowdsec` — first boot initializes the local API
2. Create the bouncer key (step 1 above) and wire the Traefik plugin
3. Optional community blocklists: `docker exec crowdsec cscli console enroll`
4. Verify: `cscli decisions add --ip <test-ip>` → expect HTTP 403 through any
   nip.io host → remove the decision after

## Notes

- **CVE posture:** kin-openapi v0.137.0 (GHSA-r277-6w6q-xmqw) — no tag clears
  it; fix (0.144.0) exists upstream but isn't rebuilt. Deploy-as-is on the LAN,
  track the upstream release (spec §14)
- LAN-only exposure → value is community blocklists (CAPI) + defense-in-depth;
  keep default ban durations, watch for false positives (`cscli alert list`)
- 128m/0.25 is tight — watch `docker stats` after 48h (parsers can spike)

## Troubleshooting

- **Bouncer not blocking** — check `cscli bouncers list` for the key status and
  Traefik logs for LAPI connection errors; stream mode reconnects every 60s.
- **False positives on LAN clients** — `cscli alert list`, then
  `cscli decisions delete --ip <ip>` and consider allowlisting.
