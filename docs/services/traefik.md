# Traefik

Reverse proxy for all web UIs except Plex.

| | |
|---|---|
| **Image** | `traefik:v3.1` |
| **Ports** | 80 (HTTP→HTTPS redirect), 443 (HTTPS) |
| **Networks** | `bearcave`, `traefik` |
| **Healthcheck** | `traefik healthcheck --ping` (API port) |

## Role

- Routes every service's web UI by hostname via Docker labels
- Terminates TLS with Let's Encrypt certificates
- Dashboard at `https://traefik.HOST_IP.nip.io` (basic-auth protected)

## Configuration

Static config: `config/traefik/traefik.yml`
Dynamic config dir: `config/traefik/dynamic/`

```yaml
# config/traefik/traefik.yml (key sections)
api:
  dashboard: true
entryPoints:
  web:      # :80 → redirect to websecure
  websecure: # :443 → TLS
certificatesResolvers:
  letsencrypt:
    acme:
      email: ${ACME_EMAIL}
providers:
  docker:
    exposedByDefault: false   # only services with traefik.enable=true get routes
  file:
    directory: /etc/traefik/dynamic
```

## Per-service labels

Each proxied service carries labels in `docker-compose.yml`:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.<name>.rule=Host(`<name>.${HOST_IP}.nip.io`)"
  - "traefik.http.services.<name>.loadbalancer.server.port=<port>"
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TRAEFIK_DASHBOARD_AUTH` | `htpasswd -nB admin` output with `$` escaped as `$$` |
| `HOST_IP` | Used in every router rule's `nip.io` hostname |

## Troubleshooting

- **Dashboard 401** — regenerate auth: `htpasswd -nB admin | sed 's/\$/\$\$/g'`
- **Certificates not issuing** — Let's Encrypt HTTP-01 challenge needs port 80 reachable
  from the internet; on a pure LAN, use a self-signed resolver or nip.io with `tls: {}`
- **Service not routing** — confirm the target service has `traefik.enable=true`;
  `exposedByDefault: false` means unlabeled services are invisible
- **Healthcheck** — `/ping` must be on an entrypoint Traefik exposes; the compose
  healthcheck probes the API port
