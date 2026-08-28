# AdGuard Home

Network-wide DNS ad/tracker blocker — becomes the LAN's DNS resolver via the router's DHCP.

| | |
|---|---|
| **Image** | `adguard/adguardhome:latest` |
| **Port** | 53/53 (tcp+udp), 3003 (web UI) |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:3000/control/health` |
| **Config** | `config/adguard/conf/` + `config/adguard/work/` (gitignored) |
| **Env** | `PUID`/`PGID` (official image supports them — verify at deploy) |

## Role

- Network-wide DNS filtering — ads, trackers, and malware domains blocked for every LAN client
- Becomes **the LAN DNS** via router DHCP (the router advertises `HOST_IP` as DNS)
- Web UI for filtering rules, blocklists, and query logs

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/adguard/conf/` | `/opt/adguardhome/conf` | Config (`AdGuardHome.yaml`) |
| `config/adguard/work/` | `/opt/adguardhome/work` | Data + query logs |

## Ports

| Host | Container | Purpose |
|------|-----------|---------|
| 53/tcp, 53/udp | 53/tcp, 53/udp | DNS service (LAN clients) |
| 3003 | 3000 | Web UI (3000 host taken by nzbdav → 3003) |

## First-run

1. Open `https://adguard.HOST_IP.nip.io` (or `http://HOST_IP:3003`)
2. Complete the setup wizard (web admin port 3000, DNS 53)
3. Add blocklists (default set is fine to start)
4. **LAN DNS cutover** — coordinate the router DHCP change with the user:
   set the router's DNS to `HOST_IP`, keep the router's own DNS as secondary
   until filtering is confirmed (brief DNS disruption when switching)

## Notes

- The built-in **DHCP server is deliberately OFF** (would need `NET_ADMIN` +
  host-network binding) — the router's DHCP stays authoritative
- **Firewall:** the nftables `DOCKER` chain is tcp-only today; verify
  `udp dport 53 accept` appears after first `up` — if the LAN can't resolve
  afterward, that rule is the first place to look
- Host itself keeps using systemd-resolved (stub at 127.0.0.53) — deciding
  whether the host should also filter is separate from the LAN cutover

## Troubleshooting

- **LAN can't resolve after cutover** — check the `udp dport 53` firewall rule,
  then `docker logs adguard` for listener errors.
- **Browsers still show ads** — clients may have cached DNS or a hardcoded
  resolver; flush/renew DHCP leases.
