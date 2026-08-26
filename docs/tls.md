# TLS & Certificates

How The Bear Cave terminates HTTPS with a locally-trusted CA — so all `*.nip.io`
hostnames show a valid padlock instead of a browser warning.

---

## The model

The stack lives on a **private LAN** (`192.168.4.20`), and every service is
reachable via `*.192.168.4.20.nip.io` hostnames. Let's Encrypt can **never**
issue certificates for those names: the ACME HTTP-01 challenge requires a
publicly reachable host, and a private IP fails validation. (This is why the
`certificatesResolvers` block is absent from `config/traefik/traefik.yml` —
attempting it just spams errors and falls back to Traefik's self-signed cert.)

Instead, the stack runs its **own Certificate Authority** (via
[mkcert](https://github.com/FiloSottile/mkcert)):

```
mkcert root CA (rootCA.pem, rootCA-key.pem)
   └── wildcard leaf:  *.192.168.4.20.nip.io + 192.168.4.20 + localhost
         └── Traefik defaultCertificate → every router with tls=true
```

The leaf is wired in as Traefik's **default certificate** through the dynamic
config (`config/traefik/dynamic/tls.yml`), so **all** nip.io hostnames get the
valid cert with zero per-router configuration.

## Files

| Path | Content | Tracked? |
|------|---------|----------|
| `~/.local/share/mkcert/rootCA.pem` | Root CA certificate (server) | No (out of repo) |
| `~/.local/share/mkcert/rootCA-key.pem` | Root CA **private key** — never leaves the server | No (out of repo) |
| `config/traefik/certs/bearcave.pem` | Wildcard leaf cert (mounted into traefik) | Gitignored |
| `config/traefik/certs/bearcave-key.pem` | Leaf **private key** (mounted into traefik) | Gitignored |
| `config/traefik/certs/rootCA.pem` | Public root CA — served by landing page for device trust | Gitignored |
| `config/traefik/dynamic/tls.yml` | Default-certificate wiring | ✅ committed |

## First-time setup (server)

```bash
# 1. Install mkcert (v1.4.4+), user-local
curl -sL -o ~/.local/bin/mkcert https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v1.4.4-linux-amd64
chmod +x ~/.local/bin/mkcert

# 2. Create + trust the CA in the system store (writes /usr/local/share/ca-certificates)
sudo ~/.local/bin/mkcert -install

# 3. Generate the wildcard leaf for all nip.io hostnames
cd /home/bear/TheBearCave
~/.local/bin/mkcert -cert-file config/traefik/certs/bearcave.pem \
                    -key-file config/traefik/certs/bearcave-key.pem \
                    "*.${HOST_IP}.nip.io" "${HOST_IP}" "localhost"

# 4. Restart traefik (first time only — it hot-reloads cert files afterwards)
docker compose up -d traefik
```

> The server's own CA trust (step 2) only affects the host. **Each device** you
> browse from needs the CA installed too — see `scripts/trust-ca.sh`.

## Trusting the CA on other devices

The root CA is published by `scripts/trust-ca.sh` to the landing page (nginx
serves it at `/rootCA.pem`), then installed per-device:

```bash
./scripts/trust-ca.sh        # publishes rootCA.pem + prints per-platform steps
```

Fetch it from `https://bearcave.192.168.4.20.nip.io/rootCA.pem` and follow the
printed steps for Linux / macOS / Windows / iOS / Android. Only the public
certificate is served — never the key.

**Security note:** anyone with `rootCA.pem` *and* `rootCA-key.pem` can mint
certificates for your domains. Only the server holds the key — devices get the
certificate alone, which is safe to share over the LAN.

## Renewal

The leaf is valid ~2.5 years. Regenerate with the mkcert command above —
Traefik's file provider (`watch=true`) hot-reloads the new cert, no restart.
The CA itself is valid ~10 years; when it expires, repeat the full setup and
re-install the new `rootCA.pem` on every device.

## Going back to self-signed (or real public certs)

- **Remove the local CA entirely:** delete `config/traefik/dynamic/tls.yml`,
  `config/traefik/certs/*`, and run `sudo mkcert -uninstall`. Traefik falls
  back to its built-in self-signed cert.
- **Real public certificates:** point a public domain at this host (port
  forward 80/443), then re-add the `certificatesResolvers` block with a valid
  `ACME_EMAIL` in `.env` and `tls.certresolver=letsencrypt` labels on routers.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Warning still shows on one device | CA not installed there yet — run `scripts/trust-ca.sh` and follow its steps for that OS |
| `ERR_CERT_AUTHORITY_INVALID` but cert is mkcert-signed | Browser cached the old Traefik default cert — hard-reload / restart browser |
| Android Chrome refuses the CA | Chrome requires the CA to be installed via Settings (not the download alone); see the Android steps |
| iOS shows "not trusted" | Forgot step 3 (Certificate Trust Settings → enable full trust) |
| Cert expired | Regenerate the leaf (renewal above) |
