# Landing Page

Nginx service portal — the front door that links to every service.

| | |
|---|---|
| **Image** | `nginx:alpine` |
| **Port** | 8000 (host) → 80 |
| **Network** | `bearcave` |
| **Files** | `services/landing-page/index.html`, `services/landing-page/nginx.conf` |

## Role

- Quick Links panel to every service UI
- Also reachable via Traefik at `https://bearcave.HOST_IP.nip.io`

## Customizing

Edit `services/landing-page/index.html` (static HTML, no build step) and recreate:

```bash
docker compose up -d --force-recreate landing-page
```

## Notes

- Serves from a read-only bind of `index.html` + `nginx.conf`
- Both direct (`:8000`) and proxied (`bearcave.…nip.io`) entry points exist —
  pick one as the canonical link for your bookmarks
