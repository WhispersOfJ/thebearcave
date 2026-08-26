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
| `config/ca/rootCA.pem` | Public root CA — served by landing page, mounted into every container for Node | Gitignored |
| `config/ca/ca-bundle.pem` | **Combined** bundle (host public CAs + mkcert root) — mounted into every container as the TLS bundle | Gitignored |
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
./scripts/trust-ca.sh   # publishes rootCA.pem, rebuilds ca-bundle.pem, prints per-platform steps
```

Fetch it from `https://bearcave.192.168.4.20.nip.io/rootCA.pem` and follow the
printed steps for Linux / macOS / Windows / iOS / Android. Only the public
certificate is served — never the key.

**Security note:** anyone with `rootCA.pem` *and* `rootCA-key.pem` can mint
certificates for your domains. Only the server holds the key — devices get the
certificate alone, which is safe to share over the LAN.

## Trusting the CA inside containers

Every service container mounts `config/ca/` read-only at
`/etc/ssl/certs/mkcert/` and points its TLS stack at it via env vars
(anchored `x-ca-env` / `x-ca-mount` in `docker-compose.yml`):

| Env var | Points at | Semantics |
|---------|-----------|-----------|
| `SSL_CERT_FILE` / `CURL_CA_BUNDLE` / `REQUESTS_CA_BUNDLE` | `ca-bundle.pem` | **Replace** the bundle — must contain public CAs too, or external calls break |
| `NODE_EXTRA_CA_CERTS` | `rootCA.pem` | **Append** to the default store — safe with the root alone |

This makes in-stack HTTPS calls to the nip.io hostnames (healthchecks,
*arr webhooks, Plex/Seerr callbacks, Grafana alert URLs) validate without
`-k`. The container images' own bundles are untouched — the mount is an
additional trust root, so public-Internet calls (indexers, usenet, TMDB/TVDB)
keep working.

`ca-bundle.pem` is rebuilt by `scripts/trust-ca.sh` (host store + mkcert
root). After regenerating the CA, run it and recreate the containers
(`docker compose up -d --force-recreate`) so the env/mount changes apply.

The **leaf private key** (`config/traefik/certs/bearcave-key.pem`) is never
mounted into app containers — only traefik itself sees it.

## Automating device trust (Ansible)

For fleets of devices, an [Ansible playbook](../ansible/playbooks/trust-ca.yml)
installs the CA into each device's system store automatically — Linux
(Debian/RHEL), macOS keychain, and Windows Root store, with an optional Firefox
NSS import. The playbook verifies each store actually trusts the CA and is
idempotent, so re-running after everything is green is a no-op.

```bash
cp ansible/hosts.example.yml ansible/hosts.yml   # list your devices
./scripts/ansible-trust-ca.sh                    # wrapper: prereqs + run
```

See [ansible/README.md](../ansible/README.md) for prerequisites (SSH keys,
WinRM, collections) and per-OS notes.

## Renewal

The leaf is valid ~2.5 years. Regenerate with the mkcert command above —
Traefik's file provider (`watch=true`) hot-reloads the new cert, no restart.
The CA itself is valid ~10 years; when it expires, repeat the full setup and
re-install the new `rootCA.pem` on every device (the Ansible playbook makes
this a one-liner).

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
| Container HTTPS call to a nip.io URL fails validation | Recreate the container (`docker compose up -d --force-recreate`) so it picks up the CA mount/env |
