# Potential Improvements

Over one hundred concrete, evidence-backed recommendations for The Bear Cave: a
catalogue of improvements to the existing stack, a list of **historically used
software to remove** (section 7), and a catalogue of current software worth
adding (section 8).

Counts: **62 numbered improvement items** (sections 1-7 and 9) plus **46
software titles** (section 8) = 108 concrete recommendations, each naming the
file (and line, where stable) that produced the finding, so none requires
re-investigation before it can be acted on.

## How to Read This

**Severity** — `CRITICAL` means a live security or data-loss exposure.
`HIGH` means a real bug or a control that exists but does not work.
`MEDIUM` means a maintainability or reliability gap. `LOW` means hygiene.

**Effort** — `S` is under an hour. `M` is an afternoon. `L` is a project.

Items marked **(verify first)** rest on an assumption that needs a check
against the running stack before the change is applied.

## Priority Shortlist

| # | Item | Severity | Effort |
|---|------|----------|--------|
| 11 | Django dev server is the production entrypoint | CRITICAL | S |
| 1 | control-panel holds a writable Docker socket | CRITICAL | L |
| 2 | promtail holds a Docker socket it never uses | HIGH | S |
| 13 | `CONTROL_PANEL_SECURE_COOKIE` is a dead knob | HIGH | S |
| 14 | `ALLOWED_HOSTS` omits the hostname Traefik routes on | HIGH | S |
| 15 | `STATICFILES_STORAGE` is silently ignored on Django 6.1 | HIGH | S |
| 29 | The Trivy IaC gate is a no-op | HIGH | S |
| 19 | `pytest.ini` `testpaths` names nine directories that do not exist | HIGH | S |

---

# 1. Container & Runtime Security

### 1. control-panel holds a writable Docker socket
**Severity:** CRITICAL · **Effort:** L
**Where:** `docker-compose.yml:488`
**Problem:** `/var/run/docker.sock` is mounted read-write. Any code execution
inside control-panel is equivalent to root on the host — a container can be
started with `/` bind-mounted and `privileged: true`.
**Fix:** No trivial fix exists. control-panel genuinely calls `containers.run`,
`exec_run`, `images.pull` and `volumes.prune`, so a socket proxy that permits
those is near-equivalent to the raw socket. The real fix is to move privileged
operations behind the existing helper socket (`/run/controlpanel-helper.sock`,
already mounted at `docker-compose.yml:496`) with an explicit allowlist of
operations, then drop the Docker socket entirely.

### 2. promtail holds a Docker socket it never uses
**Severity:** HIGH · **Effort:** S
**Where:** `docker-compose.yml:626`
**Problem:** `config/promtail/promtail-config.yaml` uses a `static_configs`
scrape against `/var/lib/docker/containers/*/*-json.log`. There is no
`docker_sd_configs` block and no Docker API call anywhere in the config. The
socket mount grants root-equivalent host access for nothing.
**Fix:** Delete line 626. Nothing else changes.

### 3. cAdvisor runs fully privileged
**Severity:** HIGH · **Effort:** M
**Where:** `docker-compose.yml:785`
**Problem:** `privileged: true` grants every capability plus unrestricted
device access, when cAdvisor documents a narrower supported set.
**Fix:** Replace with `devices: [/dev/kmsg]` (already present at `:787`) plus
`cap_add: [SYS_PTRACE]` and `security_opt: [apparmor:unconfined]`. Confirm
metrics still populate the Grafana container dashboard afterwards.

### 4. cAdvisor mounts the host root filesystem read-write
**Severity:** HIGH · **Effort:** S
**Where:** `docker-compose.yml:792-796`
**Problem:** `/:/rootfs`, `/var/run`, `/sys`, `/var/lib/docker/` and
`/dev/disk/` are all mounted without `:ro`. cAdvisor only reads them.
node-exporter has the same pattern at `docker-compose.yml:766-768` (`/proc`,
`/sys`, `/:/rootfs`), also without `:ro`.
**Fix:** Append `:ro` to each, in both services. `/var/run` may need to stay
writable — **(verify first)** by starting the container and checking for
permission errors in `docker logs cadvisor`.

### 5. No resource limits on any of the 23 services
**Severity:** HIGH · **Effort:** M
**Where:** `docker-compose.yml` (zero matches for `mem_limit`, `cpus`, or
`deploy.resources`)
**Problem:** One runaway container — a Plex transcode storm, a Radarr import
loop, a Loki compaction — can consume all host RAM and take the whole stack
down. There is a `ContainerHighMemory` alert (`config/prometheus/alert-rules.yml:27`)
that fires but cannot prevent anything.
**Fix:** Add `mem_limit` and `cpus` to every service, sized from a week of
cAdvisor data. Start with the known-hungry three: plex, metacache, loki.

### 6. No `no-new-privileges` anywhere
**Severity:** MEDIUM · **Effort:** S
**Where:** `docker-compose.yml` (zero matches for `security_opt`)
**Problem:** A setuid binary inside any container can escalate within that
container.
**Fix:** Add `security_opt: [no-new-privileges:true]` to the shared
`x-common-*` anchor block and apply it to every service that does not need
privilege escalation. cAdvisor is the likely exception.

### 7. Twenty-two of twenty-three services run as root
**Severity:** MEDIUM · **Effort:** L
**Where:** `docker-compose.yml:565` is the only `user:` declaration (watchstate)
**Problem:** `PUID`/`PGID` are defined in `.env.template` and used by exactly
one service. The hotio images (prowlarr, radarr, sonarr) honour `PUID`/`PGID`
via environment; the rest do not.
**Fix:** Set `PUID`/`PGID` env for the three hotio services, and `user:` for
grafana, prometheus, alertmanager, loki and landing-page. **(verify first)** —
each needs its bind-mounted config directory chowned to match, or it will fail
to start.

### 8. Four services have no healthcheck
**Severity:** MEDIUM · **Effort:** S
**Where:** promtail `docker-compose.yml:619`, node-exporter `:758`,
arr-dashboard `:811`, landing-page `:837`
**Problem:** Nineteen of twenty-three services define a healthcheck. These four
do not, so `depends_on: condition: service_healthy` cannot gate on them and a
hung process reads as healthy.
**Fix:** promtail → `wget --spider http://localhost:9080/ready`; node-exporter →
`wget --spider http://localhost:9100/metrics`; landing-page → nginx serves `/`;
arr-dashboard → **(verify first)**, check what the image exposes.

### 9. Ten services publish host ports while also routed through Traefik
**Severity:** MEDIUM · **Effort:** M
**Where:** `docker-compose.yml` — ports `9696, 7878, 8989, 3000, 5055, 8765,
8420, 11011, 8705, 8080`
**Problem:** Every one of these services is reachable on the LAN directly,
bypassing Traefik entirely. Any authentication added at the proxy (see item 18)
would be trivially sidestepped.
**Fix:** Once each service is confirmed working over its `*.nip.io` route,
delete the `ports:` block. Keep only Traefik's `80:80` and `443:443`. Retain
individual ports behind a compose profile for debugging.

### 10. control-panel mounts `/mnt`, `/proc` and the repo config directory writable
**Severity:** MEDIUM · **Effort:** S
**Where:** `docker-compose.yml:489-491` and `:495`
**Problem:** `/mnt:/mnt`, `./config:/host-config` and `/proc:/host-proc` are all
read-write. Diagnostics code (`host/services/diagnostics.py`) only reads
`/host-proc`.
**Fix:** `/proc:/host-proc:ro` is safe now. `/mnt` and `./config` need
**(verify first)** — grep `host/` and `host_actions/` for writes to those
paths before changing.

---

# 2. Application Security

### 11. Django's development server is the production entrypoint
**Severity:** CRITICAL · **Effort:** S
**Where:** `services/control-panel/django/Dockerfile:33`
**Problem:** `CMD ["python", "manage.py", "runserver", "0.0.0.0:8420"]`. Django
documents `runserver` as unsuitable for production: it is single-threaded,
performs no security auditing, and reloads on file change. This is the process
serving a panel that controls the Docker socket.
**Fix:** Add `gunicorn` to `requirements-prod.txt` and change to
`CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8420", "--workers", "3", "--access-logfile", "-"]`.
Whitenoise (already in `MIDDLEWARE`) keeps serving static files.

### 12. No transport or cookie security settings
**Severity:** HIGH · **Effort:** S
**Where:** `services/control-panel/django/config/settings.py`
**Problem:** None of `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`,
`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_REFERRER_POLICY`,
`SECURE_CONTENT_TYPE_NOSNIFF`, `CSRF_TRUSTED_ORIGINS` or `X_FRAME_OPTIONS` is
set. `SecurityMiddleware` is installed but has nothing to enforce.
**Fix:** Add the block, gated on `not DEBUG`. Include
`CSRF_TRUSTED_ORIGINS = [f"https://panel.{HOST_IP}.nip.io"]`, which is required
for POSTs through Traefik regardless. Validate with `manage.py check --deploy`.

### 13. `CONTROL_PANEL_SECURE_COOKIE` is a dead knob
**Severity:** HIGH · **Effort:** S
**Where:** set at `docker-compose.yml:482`, read nowhere in `config/settings.py`
**Problem:** The variable is plumbed through compose and `.env.template`,
implying session cookies are secured. Nothing reads it. Session cookies are
sent over plain HTTP on the direct port (item 9).
**Fix:** Either wire it to `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` as
part of item 12, or delete it from compose and `.env.template`. A knob that
lies is worse than no knob.

### 14. `ALLOWED_HOSTS` omits the hostname Traefik routes on
**Severity:** HIGH · **Effort:** S
**Where:** `services/control-panel/django/config/settings.py:15`; router rule at
`docker-compose.yml:501`
**Problem:** `ALLOWED_HOSTS` is built from `HOST_IP`, `localhost`, `127.0.0.1`
and `[::1]`. Traefik routes `panel.${HOST_IP}.nip.io`. That Host header is not
in the list, so requests through the proxy return `400 Bad Request`.
**Fix:** Append `f"panel.{host_ip}.nip.io"` when `HOST_IP` is set. Check
`core/middleware.py`'s `VerifySameOriginMiddleware` allowlist for the same gap.

### 15. `STATICFILES_STORAGE` is silently ignored on Django 6.1
**Severity:** HIGH · **Effort:** S
**Where:** `services/control-panel/django/config/settings.py:107`
**Problem:** `STATICFILES_STORAGE` was superseded by the `STORAGES` dict in
Django 5.1 and no longer has any effect on 6.1 (`requirements.txt` pins
`Django==6.1`). Whitenoise therefore falls back to plain static serving: no
gzip/brotli compression, no hashed manifest, so cache-busting does not work and
`htmx.min.js` (52 KB) ships uncompressed on every cold load.
**Fix:**
```python
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```
Confirm `collectstatic` in `Dockerfile:29` emits `.gz`/`.br` files afterwards.

### 16. No logging configuration
**Severity:** MEDIUM · **Effort:** S
**Where:** `services/control-panel/django/config/settings.py`; mount at
`docker-compose.yml:495` (`./logs/control-panel:/logs`)
**Problem:** There is no `LOGGING` dict. A log directory is mounted and stays
empty. Unhandled exceptions reach stdout via Django's default only, so
`envelope_exception_handler` failures and Docker API errors are unstructured
and unsearchable in Loki.
**Fix:** Add a `LOGGING` dict with a JSON formatter on stdout (promtail already
collects container stdout) and a rotating file handler at `/logs/app.log`. Set
`django.request` and `django.security` to `WARNING`.

### 17. Twenty-four secrets are injected as plain environment variables
**Severity:** MEDIUM · **Effort:** M
**Where:** `docker-compose.yml:462-483`; empty `secrets/` directory
**Problem:** API keys, the Django secret key, the admin password and the
Discord webhook all appear in `docker inspect` output, in `/proc/<pid>/environ`
for anything sharing the PID namespace, and in any crash dump. A `secrets/`
directory exists and is gitignored, but no compose `secrets:` block was ever
written.
**Fix:** Move the highest-value four (`CONTROL_PANEL_SECRET_KEY`,
`CONTROL_PANEL_ADMIN_PASSWORD`, `PLEX_TOKEN`, `DISCORD_WEBHOOK_URL`) to compose
file secrets, and read `*_FILE` variants in `settings.py`. Fully solving this
is item 17 of the software section (SOPS).

### 18. No authentication in front of any service
**Severity:** HIGH · **Effort:** M
**Where:** `config/traefik/dynamic/` contains only `tls.yml`;
`docker-compose.yml` has two `middlewares` label references total
**Problem:** Prowlarr, Radarr, Sonarr, Grafana, Prometheus, Alertmanager,
cAdvisor and the Traefik dashboard (`api.dashboard: true`,
`config/traefik/traefik.yml:7`) are all reachable unauthenticated by anything on
the LAN. Only control-panel has its own login.
**Fix:** Short term — a `basicAuth` middleware in
`config/traefik/dynamic/auth.yml` applied to every router. Long term — Authelia
forward-auth (see software section). Note this is only worth doing alongside
item 9; otherwise the direct ports bypass it.

---

# 3. Testing & Coverage

### 19. `pytest.ini` names nine directories that do not exist
**Severity:** HIGH · **Effort:** S
**Where:** `services/control-panel/django/pytest.ini:4`
**Problem:** `testpaths` lists 21 entries. Nine — `ratings`, `seerr`,
`prowlarr`, `radarr`, `sonarr`, `mdblist`, `letterboxd`, `plex`, `posters`,
`arr` — are leftovers from before the Django migration. pytest silently skips
missing paths, so an app whose test directory is later renamed disappears from
the suite with no warning.
**Fix:** Reduce `testpaths` to the twelve real app directories. Better: drop
`testpaths` entirely and let pytest discover from the project root, so a new app
is covered the moment it is created.

### 20. The largest file in the repo has one test file
**Severity:** HIGH · **Effort:** L
**Where:** `services/control-panel/django/cli/api/views.py` (867 lines);
`cli/` contains one `test_*.py`
**Problem:** This module backs 95 API-driven fish functions
(`services/fish-functions/`). It is the widest blast radius in the codebase and
the thinnest test coverage relative to size.
**Fix:** Split by domain first — the file is well past the 800-line ceiling in
`CLAUDE.md` — then write per-endpoint tests. `host/tests/test_api.py`
(396 lines) is the pattern to copy.

### 21. The UI app is effectively untested
**Severity:** MEDIUM · **Effort:** M
**Where:** `services/control-panel/django/ui/` — `views.py` is 230 lines, one
test file
**Problem:** Every HTMX-driven page in the panel renders through here. A broken
template or a changed context key fails silently in CI and loudly in the browser.
**Fix:** Add smoke tests asserting HTTP 200 and one distinguishing string per
route, plus a test that every route in `ui/urls.py` is reachable while
authenticated and redirects while not.

### 22. Ruff lints 2 directories and skips 197 Python files
**Severity:** MEDIUM · **Effort:** S
**Where:** `.github/workflows/validate.yml` — `ruff check scripts/ tests/`
**Problem:** All 197 tracked `.py` files under `services/` — the entire Django
application and the nzbdav exporter — are unlinted.
**Fix:** Change to `ruff check .` and add a `[tool.ruff]` section in a root
`pyproject.toml` with `exclude = ["archive", "**/migrations"]`. Expect a large
first-run diff; land the autofixable rules in one commit.

### 23. No coverage threshold despite pytest-cov being installed
**Severity:** MEDIUM · **Effort:** S
**Where:** `services/control-panel/django/requirements.txt` pins
`pytest-cov==7.1.0`; nothing invokes it
**Problem:** `CLAUDE.md` and the global rules both mandate 80% coverage. Nothing
measures it, so the number is aspirational.
**Fix:** `pytest --cov=. --cov-report=term-missing --cov-fail-under=<current>` in
`validate.yml`, with the floor set to today's measured value and ratcheted up.
A falling floor is caught immediately; an ambitious one that never passes is not.

### 24. The exporter test step cannot fail
**Severity:** MEDIUM · **Effort:** S
**Where:** `.github/workflows/validate.yml`, final step
**Problem:** `python -m pytest test_exporter.py -v 2>/dev/null || echo "No tests
found or tests skipped"` swallows every failure and discards stderr.
`test_exporter.py` is 271 lines of real tests that can never turn CI red. The
step also `pip install requests prometheus_client` by hand rather than using the
service's own requirements.
**Fix:** Drop the `|| echo` and the `2>/dev/null`. Install from
`services/nzbdav-exporter/requirements.txt` (create it if absent).

### 25. `backup.sh` has no restore test
**Severity:** HIGH · **Effort:** M
**Where:** `scripts/backup.sh` (232 lines); `tests/` holds three shell scripts
**Problem:** An untested restore path is an unverified backup. The script
archives *arr databases, control-panel SQLite and secrets, and nothing ever
confirms the archive can be unpacked into a working stack.
**Fix:** Add `tests/integration/test_backup_restore.sh`: back up, restore into a
scratch directory, assert each SQLite file passes `PRAGMA integrity_check` and
that the restored `.env` parses. Run it in `nightly-healthcheck.yml`.

### 26. No end-to-end test of the core pipeline
**Severity:** MEDIUM · **Effort:** L
**Where:** `tests/integration/test_pipeline.sh` exists; scope unverified
**Problem:** The stack's entire purpose is request → download → import → serve →
play. `CLAUDE.md` requires verifying that full pipeline. No test asserts it.
**Fix:** Extend `test_pipeline.sh` into a staged check against the live stack:
add via Seerr API, poll Radarr queue, wait for import, confirm the file appears
under `media/movies/`, confirm Plex returns it from a library search. Gate each
stage on a timeout so a hang fails rather than blocks.

---

# 4. Supply Chain & CI

### 27. Eleven images float on mutable tags
**Severity:** HIGH · **Effort:** M
**Where:** `docker-compose.yml`
**Problem:** Seven `:latest` (cadvisor, watchstate, infinidysk, arr-dashboard,
plex, prometheus, alertmanager, node-exporter, rclone), three `:release`
(prowlarr, radarr, sonarr), and two with no tag at all (`ghcr.io/seerr-team/seerr`,
`golift/unpackerr`). Two deploys a week apart produce different stacks, and a
rollback cannot reproduce the previous one.
**Fix:** Pin every image to an explicit version tag, matching the pattern
already used for cleanuparr (`2.10.5`), grafana (`13.2.0`), loki (`3.7.6`),
promtail (`3.6.11`) and traefik (`v3.7`).

### 28. No digest pinning
**Severity:** MEDIUM · **Effort:** S
**Where:** `docker-compose.yml` (after item 27)
**Problem:** Even a version tag can be retargeted at the registry. The repo
already applies full-SHA pinning to GitHub Actions
(`.github/workflows/*.yml` header comments) — the same reasoning applies to
images.
**Fix:** `image: name:tag@sha256:...`, refreshed by Renovate (software section).

### 29. The Trivy IaC gate is a no-op
**Severity:** HIGH · **Effort:** S
**Where:** `.github/workflows/trivy-scan.yml:93`
**Problem:** `trivy config --severity HIGH,CRITICAL --exit-code 1 ... || true`.
The `|| true` discards the exit code the `--exit-code 1` flag exists to produce.
The following line prints "non-blocking for now". Every Dockerfile and compose
misconfiguration in this document would be reported and ignored.
**Fix:** Generate a `.trivyignore` from today's findings, drop the `|| true`, and
work the ignore file down. A gate that never fails provides only the appearance
of coverage.

### 30. actionlint is downloaded without checksum verification
**Severity:** MEDIUM · **Effort:** S
**Where:** `.github/workflows/validate.yml`, "Actionlint" step
**Problem:** `curl -sSL` from a GitHub release URL, untarred and executed. The
repo pins every action to a full commit SHA precisely to defend against this
class of substitution, then bypasses it here.
**Fix:** Record the release's SHA-256 and `sha256sum -c` before extracting; or
use `rhysd/actionlint`'s official action pinned to a SHA, consistent with the
rest of the file.

### 31. A 1.8 MB generated file is tracked in git
**Severity:** MEDIUM · **Effort:** S
**Where:** `STAGE-4-CVE-BASELINE.md`
**Problem:** 1.8 MB of the repo's ~2 MB total. It is generated output that
`trivy-scan.yml`'s `report` job rewrites on every push to main, so every scan
adds another full copy to history. Clone size grows without bound.
**Fix:** Publish it as a workflow artifact or a GitHub Pages page and remove it
from the tree. Purging it from history needs `git filter-repo` and a
force-push — coordinate that separately.

### 32. No SBOM generation
**Severity:** MEDIUM · **Effort:** S
**Where:** `.github/workflows/docker-publish.yml`
**Problem:** Trivy scans the image but nothing records what is in it. When the
next Log4Shell lands, answering "are we affected" means rescanning every image
rather than querying a stored bill of materials.
**Fix:** `docker/build-push-action` supports `sbom: true` and
`provenance: mode=max`. Two lines.

### 33. Published images are unsigned
**Severity:** MEDIUM · **Effort:** S
**Where:** `.github/workflows/docker-publish.yml`
**Problem:** `ghcr.io/<owner>/thebearcave-metacache` carries no signature, so
nothing distinguishes an image this pipeline built from one pushed by anyone
holding a `packages:write` token.
**Fix:** `sigstore/cosign-installer` plus keyless `cosign sign` using the
workflow's OIDC identity. No key management required.

### 34. `validate.yml` runs in full on every documentation edit
**Severity:** LOW · **Effort:** S
**Where:** `.github/workflows/validate.yml`, `on:` block
**Problem:** No `paths:` filter. A typo fix in a README triggers compose
validation, shellcheck, ruff, actionlint and the whole Django suite.
**Fix:** Add `paths-ignore: ["**.md", "docs/**"]` — but keep markdown edits
running whatever lints markdown, if anything is added later.

### 35. No local pre-commit gate
**Severity:** MEDIUM · **Effort:** S
**Where:** no `.pre-commit-config.yaml`
**Problem:** Every check runs only in CI. Secrets, lint failures and broken
compose files are caught minutes after commit rather than before it. `secret-guard.yml`
exists, which means a leaked key is caught after it is already in history.
**Fix:** `.pre-commit-config.yaml` with `gitleaks`, `ruff`, `shellcheck`,
`check-yaml` and `end-of-file-fixer`. Document `pre-commit install` in
`docs/quick-start.md`.

### 36. Two of three built images are never published
**Severity:** LOW · **Effort:** M
**Where:** `docker-compose.yml:449` (control-panel), `:683` (nzbdav-exporter);
`docker-publish.yml` covers metacache only
**Problem:** control-panel and nzbdav-exporter rebuild from source on the host
at every deploy. That makes deploys slow, makes rollback mean "check out the old
commit and rebuild", and leaves both images out of the CVE scanning pipeline
that metacache gets.
**Fix:** Extend `docker-publish.yml` to a matrix over all three Dockerfiles, and
switch compose to `image:` with a pinned tag.

---

# 5. Operations & Reliability

### 37. Loki has no retention policy
**Severity:** HIGH · **Effort:** S
**Where:** `config/loki/loki-config.yaml` — `compactor` is configured at `:41`,
`limits_config` at `:32`, but no `retention_period` and no
`retention_enabled: true`
**Problem:** The compactor is present but retention is off, so log volume grows
until the disk fills. `HostDiskCritical` (`alert-rules.yml:62`) will fire — after
the fact.
**Fix:** `limits_config.retention_period: 720h` and
`compactor.retention_enabled: true`, `compactor.delete_request_store: filesystem`.

### 38. Log rotation covers 9 of 23 services
**Severity:** MEDIUM · **Effort:** S
**Where:** `docker-compose.yml` — `logging: *common-logging` appears 9 times
**Problem:** The other fourteen use Docker's default `json-file` driver with no
`max-size` or `max-file`, so their logs grow unbounded independently of Loki.
**Fix:** Apply the existing `*common-logging` anchor to every service. It is a
one-line addition per block and the anchor already exists.

### 39. Alert coverage has four operational blind spots
**Severity:** MEDIUM · **Effort:** M
**Where:** `config/prometheus/alert-rules.yml` — 12 rules
**Problem:** The existing rules cover container health, host disk/memory, FUSE
staleness and target liveness, which is a good base. Missing: backup freshness
(nothing alerts if `backup.sh` stops running), TLS certificate expiry, disk
*fill rate* as opposed to level (a 20 GB/hour trend is actionable hours before
`HostDiskHigh` fires), and Plex reachability from outside the stack.
**Fix:** Add a `node_textfile` collector timestamp written by `backup.sh` plus a
staleness rule; add blackbox-exporter for cert expiry and external probes; add a
`predict_linear` rule on `node_filesystem_avail_bytes`.

### 40. control-panel runs on SQLite
**Severity:** MEDIUM · **Effort:** L
**Where:** `services/control-panel/django/config/settings.py:75`
**Problem:** SQLite serialises writes with a whole-database lock. With HTMX
polling, session writes on every request (`SESSION_ENGINE` is the DB backend)
and a multi-worker gunicorn (item 11), `database is locked` becomes likely
rather than theoretical. No `timeout` or WAL pragma is set.
**Fix:** Immediate mitigation — `"OPTIONS": {"timeout": 20, "init_command": "PRAGMA journal_mode=WAL;"}`.
Proper fix — PostgreSQL (software section), with `SESSION_ENGINE` moved to
`cached_db` or Redis.

### 41. `setup.sh` is a 444-line monolith
**Severity:** LOW · **Effort:** M
**Where:** `scripts/setup.sh`
**Problem:** Past the 400-line guidance in the global coding-style rules. It is
the first thing a fresh install runs, so a failure two-thirds of the way through
leaves an unclear partial state.
**Fix:** Split into `scripts/setup/` steps (`00-preflight.sh`, `10-env.sh`,
`20-certs.sh`, `30-dirs.sh`, `40-compose.sh`) with `setup.sh` as an idempotent
driver that can resume from any step.

### 42. Nothing checks the stack from outside itself
**Severity:** MEDIUM · **Effort:** M
**Where:** monitoring tier is entirely in-stack; `nightly-healthcheck.yml`
validates compose syntax only
**Problem:** If Traefik dies, or the host loses network, or Prometheus itself
stops, no alert can leave the machine to say so. Alertmanager's notification
path runs on the same host it is monitoring.
**Fix:** Gatus on a second device, or an external dead-man's switch
(healthchecks.io) pinged by a host cron. See software section.

### 43. `services/watchtower/` is an empty directory
**Severity:** LOW · **Effort:** S
**Where:** `services/watchtower/` — empty; zero references in
`docker-compose.yml`
**Problem:** Suggests a service exists that does not. Anyone reading
`services/` assumes automatic image updates are configured. They are not.
**Fix:** Delete the directory. If automatic updates are wanted, use Diun for
notify-only (software section) — Watchtower auto-pulling onto floating tags
(item 27) would make the reproducibility problem worse, not better.

### 44. Backups are local-only with no verification
**Severity:** HIGH · **Effort:** M
**Where:** `scripts/backup.sh` writes to `./backups/`
**Problem:** Backups live on the same disk as the data they protect. A disk
failure, an `rm -rf`, or ransomware takes both. Nothing prunes old archives and
nothing confirms an archive is readable after it is written.
**Fix:** restic with an off-box repository (software section), `restic check
--read-data-subset` on a schedule, and a retention policy. Pair with the backup
freshness alert from item 39.

---

# 6. Architecture & Repo Hygiene

### 45. `archive/` carries two dead projects in the working tree
**Severity:** LOW · **Effort:** S
**Where:** `archive/media-stack/`, `archive/metacacharr/`
**Problem:** Roughly 350 KB including a 196 KB `tmdb_audit_report.csv` and a
64 KB `DESIGN.md` that is byte-identical to `services/metacache/DESIGN.md`.
Every grep, every ruff run and every shellcheck invocation has to explicitly
exclude it — `validate.yml` already lists `archive` in three separate ignore
paths.
**Fix:** Delete it. Git history preserves everything; tag the last commit that
contained it as `pre-archive-removal` if reassurance is wanted.

### 46. A working spec document sits at the repo root
**Severity:** LOW · **Effort:** S
**Where:** `fish-functions-rewrite-spec.md` (21 KB)
**Problem:** The root holds README, CLAUDE.md, AGENTS.md, CHANGELOG — orientation
documents — plus this one implementation spec and the 1.8 MB CVE baseline
(item 31). The signal-to-noise ratio at the entry point matters.
**Fix:** Move to `docs/services/fish-functions-spec.md`, alongside the sixteen
service docs already in `docs/services/`.

### 47. The two largest subsystems have no entry in `docs/services/`
**Severity:** MEDIUM · **Effort:** M
**Where:** `services/fish-functions/` (240 `.fish` files),
`services/host-tools/` — neither appears in `docs/services/`
**Problem:** Sixteen service docs exist and cover every container. The 240 fish
functions and the host-tools helpers — the primary operator interface — have
only their own in-directory READMEs. `CLAUDE.md` requires a README with purpose,
configuration and troubleshooting for every service.
**Fix:** Two docs following the shape of `docs/services/control-panel.md`,
including the function index and the systemd units under `services/host-tools/`.

### 48. Host ports are hardcoded
**Severity:** LOW · **Effort:** S
**Where:** `docker-compose.yml` — every `ports:` entry is a literal
**Problem:** cAdvisor claims `8080`, one of the most commonly contested ports on
any host. Changing it means editing compose rather than `.env`.
**Fix:** If item 9 is not adopted, move each to `${SERVICE_PORT:-default}` and
document them in `.env.template`. Move cAdvisor off 8080 regardless.

### 49. No compose profiles
**Severity:** LOW · **Effort:** S
**Where:** `docker-compose.yml` — zero `profiles:` keys
**Problem:** All 23 containers start together. The monitoring tier (loki,
promtail, grafana, prometheus, alertmanager, node-exporter, cadvisor,
nzbdav-exporter — eight containers) cannot be skipped on a constrained host or
during a media-path debugging session.
**Fix:** `profiles: [monitoring]` on those eight and `profiles: [debug]` on the
direct-port mappings from item 9. `docker compose --profile monitoring up -d`
keeps the default path unchanged.

### 50. No architecture decision records
**Severity:** LOW · **Effort:** M
**Where:** `docs/` has architecture, security, tls, landmines, ci-cd — all
descriptive
**Problem:** `docs/landmines.md` records what broke, which is valuable, but not
why the current design was chosen. Several decisions here are non-obvious and
will be re-litigated: why no ACME/Let's Encrypt (answered in a comment at
`config/traefik/traefik.yml:22-28`, where nobody will look for it), why SQLite over
Postgres, why hotio images over linuxserver, why Whitenoise over nginx for
static files.
**Fix:** `docs/decisions/NNNN-title.md`, one page each: context, decision,
consequences. Start by promoting the four above out of code comments.

---

# 7. Historically Used Software — Removal Recommendations

Software that once powered this stack (or its media-stack / metacacharr
predecessors) and is now dead weight in the working tree, superseded, or no
longer deployed. Each item below removes a historically used tool rather than
adding a new one.

### 51. Recyclarr config is an 80 MB clone of two external repos, and Recyclarr is not deployed
**Severity:** HIGH · **Effort:** M
**Where:** `config/recyclarr/` — 80 MB total: `resources/trash-guides` (73 MB) + `resources/config-templates` (1.4 MB); `docker-compose.yml` has zero `recyclarr` references
**Problem:** The directory carries a full clone of the TRaSH-Guides and
config-templates GitHub repos, checked into the working tree. Recyclarr is not
a compose service and does not run. Every commit, clone, grep and `shellcheck`
walk drags 80 MB of somebody else's git history around, and a stale snapshot
actively misleads anyone reading the config for current custom-format values.
**Fix:** Delete `config/recyclarr/`. If quality profiles are wanted, run
Recyclarr as a pinned container fed a thin `settings.yml` synced from the live
TRaSH repo, or use Profilarr (section 8).

### 52. checkrr is not deployed yet its scan output ships in the working tree
**Severity:** MEDIUM · **Effort:** S
**Where:** `data/checkrr-final/` — 1.4 MB of `badfiles-*.csv`, `redownload-*.csv`, `redownload-commands-*.txt`, `verified-dead-*.csv` and `checkrr.yaml`; zero compose references
**Problem:** checkrr (dead-download scanner) is historically used software whose
one-off August 2026 scan output was left where every grep walks it. The CSVs are
1,300+ lines of stale facts about files that have since moved, redownloaded or
been pruned.
**Fix:** Archive the scan report elsewhere (or keep only the summary in
docs/), delete `data/checkrr-final/`, and remove the directory from the
backup script so stale CSVs do not keep getting re-backed up.

### 53. `data/alertmaker` is an empty leftover directory
**Severity:** LOW · **Effort:** S
**Where:** `data/alertmaker/` — 0 files
**Problem:** An empty directory from a previously used (historically used)
notify helper. It reserves a name and adds a line to every `ls`, with no purpose.
**Fix:** Delete it.

### 54. `services/watchtower/` is an empty directory from a retired auto-updater
**Severity:** LOW · **Effort:** S
**Where:** `services/watchtower/` — 0 files; item 43 flagged it, this is the removal action
**Problem:** Watchtower was the historically used auto-update tool. It is gone
(no compose service), and the empty directory is the last remnant, implying
auto-updates are configured when they are not.
**Fix:** Delete `services/watchtower/`. If automated image upkeep is wanted,
use **Diun** (section 8) for notify-only bumping instead of auto-pulling onto
floating tags.

### 55. Seerr supersedes Overseerr — do not re-add the ancestor
**Severity:** LOW · **Effort:** S
**Where:** the stack runs `ghcr.io/seerr-team/seerr` (docker-compose.yml); `archive/metacacharr/DESIGN.md:955` still discusses "Overseerr, ..." as if it were live
**Problem:** Overseerr is the historically used request manager; Seerr is its
actively maintained fork already used here. Any doc, script or mental model that
reaches for "Overseerr" targets software this stack deliberately replaced.
**Fix:** When scope touches requests, standardise on Seerr. Update the stale
`DESIGN.md` reference (or rely on archive removal, item 45).

### 56. Dependabot is the historically used dependency updater; Renovate is the go-forward
**Severity:** LOW · **Effort:** S
**Where:** `.github/dependabot.yml` (still present); the existing config drives
NuGet/Docker/pip updates weekly
**Problem:** The repo's own supply-chain section (item 37 of the software
catalog) already argues Renovate understands image tags *and* digests in a way
Dependabot cannot. Keeping both configured means two sources of update truth.
**Fix:** Decide one. If Renovate is adopted, delete `dependabot.yml` and its
scale/interval settings plus the `github-actions` ecosystem entry to avoid
double PRs. If Renovate is not adopted, keep Dependabot and drop the Renovate
recommendation.

### 57. The media-stack fish-function rewrite spec is a historical deliverable at the repo root
**Severity:** LOW · **Effort:** S
**Where:** `fish-functions-rewrite-spec.md` (21 KB) — superseded by the rewrite
itself, merged in commit `979d769`
**Problem:** The spec that drove the rewrite is now archive-calibre history, but
it sits beside README/CLAUDE/AGENTS at the repo's entry point, suggesting it is
a living orientation doc.
**Fix:** Move to `docs/services/fish-functions-spec.md` (item 46) or into
`archive/`. Keep only the orientation docs at the root.

---

# 8. Software Suggestions

Additions worth making to the stack, each tied to a specific gap above. None of
these are historically used tools from the removed set (section 7); every entry
here is a current, maintained project.

## Authentication and edge

**Authelia** — forward-auth provider for Traefik. Closes item 18 for every
service at once, with 2FA and per-service access rules, instead of the shared
password a `basicAuth` middleware gives. Requires item 9 first, or the direct
ports bypass it entirely. Runs as one container plus a config file; Redis
optional for session persistence.

**Pocket ID** — a lighter alternative to Authelia if passkey-only login is
acceptable. Far less configuration, no user database to manage. Worth preferring
if the user list is one person.

**CrowdSec** with the Traefik bouncer — behavioural blocking from Traefik's
access log (already written to `/var/log/traefik/access.log` per
`config/traefik/traefik.yml`). Only worth it if anything is ever exposed beyond
the LAN.

## Docker socket containment

**Tecnativa docker-socket-proxy** — a filtering proxy in front of the Docker
API. Important caveat, already established: control-panel calls `containers.run`,
`exec_run`, `images.pull` and `volumes.prune`, and a proxy permitting those is
close to root-equivalent, so it does **not** solve item 1. It does solve Traefik's
socket mount (`docker-compose.yml:76`, which only needs container list/inspect
and is already `:ro`) and any future read-only consumer. Deploy it there; solve
control-panel through the helper socket instead.

## Secrets

**SOPS + age** — encrypt `.env` at rest with a key held outside the repo.
Fixes item 17 properly rather than partially, keeps the file diffable in git,
and adds one decrypt step at deploy. age keys are a single file, so there is no
infrastructure to run.

**Infisical** — a full secret manager with rotation and audit logging. More
capability than a single-operator homelab needs; consider only if the stack
grows past one host.

## Backup

**restic** — deduplicating, encrypted, incremental backups to a remote (S3,
Backblaze B2, SFTP, rclone). Directly addresses item 44. `restic check
--read-data-subset` gives the verification item 25 asks for, and its snapshot
timestamps feed the freshness alert in item 39.

**Backrest** — a web UI and scheduler for restic. Useful if backups should be
inspectable from the control panel rather than the shell.

**healthchecks.io** (hosted, free tier) — a dead-man's switch pinged at the end
of `backup.sh`. If the ping stops, it alerts. Off-host by construction, so it
also partly covers item 42.

**Minio** — an S3-compatible object store that can run on a second disk or box
and act as the off-box target for restic (item 44). Keeps the "remote" off the
same drive as the data it protects while staying fully self-hosted.

**BorgBackup + borgmatic** — an alternative to restic if dedup-and-compress
behaviour is preferred. `borgmatic` adds single-file config and cron wiring
opposite to `restic`'s `--repository` flags. Choose one, not both, to avoid two
backup formats to recover from.

## Monitoring and observability

**Gatus** — a lightweight status page and synthetic checker, ideally on a second
device. Answers item 42: it checks the stack from outside, so a total host
failure produces an alert rather than silence. Config is a single YAML file.

**blackbox-exporter** — Prometheus-native probing. Feeds the TLS-expiry and
external-endpoint alerts from item 39 into the Alertmanager path already
configured, with no new notification channel.

**Dozzle** — live container log tailing in a browser. Complements Loki rather
than duplicating it: Loki is for querying history, Dozzle is for watching a
service start. Read-only socket mount; pair it with docker-socket-proxy.

**Diun** — notifies when a watched image has a new digest. The correct answer to
the empty `services/watchtower/` directory (item 54): it tells you an update
exists and lets you pin deliberately, rather than auto-pulling onto floating
tags and undoing item 27.

**Beszel** — host metrics with a small agent and a clean dashboard. Overlaps
node-exporter, so only worth adding if the per-host dashboards are wanted
without building them in Grafana.

**Karma** — an Alertmanager dashboard with grouping and silencing. Worth it once
item 39 raises the rule count.

**Tautulli** — Plex watch history, per-user statistics, transcode monitoring.
There is currently no visibility into Plex usage at all, and it is the one
service in the stack whose behaviour most affects the host's CPU.

**Netdata** — high-frequency (1s) real-time metrics with a built-in dashboard and
zero-config alerts. Complements Prometheus, which samples every 15s; run both if
a spike between scrapes keeps being missed on Plex transcode storms.

**speedtest-exporter** — runs a periodic Ookla speedtest and exposes
latency/down/up as Prometheus metrics. Directly answers "is the Usenet download
slow because of the provider or my line" during nzbdav troubleshooting.

**smartctl-exporter** — exports disk SMART attributes the way node-exporter
exports CPU/RAM. The control panel already surfaces SMART health (its
`/disk-health` endpoint); this adds the trend data so alerts can fire *before* a
drive degrades, not after (item 39's fourth blind spot).

**Vector** — a Rust log pipeline that can replace or sit beside promtail for
`journald` or app logs, with far lighter resource use than promtail's Go agent
in high-volume stacks. Only worth swapping once Loki volume is a measured
problem.

**Grafana Tempo** — distributed tracing. Only justified if the control panel's
`envelope_exception_handler` and Docker API retries (item 16) show latency
chasing worth doing; otherwise it is an unused container.

## Media stack additions

**Bazarr** — subtitle acquisition for Radarr and Sonarr. The obvious gap in an
otherwise complete *arr suite.

**Huntarr** — periodically sweeps Radarr/Sonarr for missing and upgradable
items and triggers searches. Fills the gap between Prowlarr finding things and
someone noticing they are absent.

**Profilarr** — quality profile and custom format sync. Complements Recyclarr
(already configured at `config/recyclarr/`) with a UI and versioned profiles.

**Maintainerr** — rule-based media retention: identifies what to remove based on
watch state and age, and hands it to the *arr apps. Relevant because Cleanuparr
handles failed downloads but nothing manages the library's long-term growth,
which is the actual driver of the disk alerts in `alert-rules.yml`.

**Kometa** — collections, overlays and metadata for Plex. Substantial overlap
with what `services/metacache/` does; evaluate whether it replaces part of that
service or duplicates it before adding.

**Notifiarr** — unified notification routing for the whole *arr suite into
Discord. `DISCORD_WEBHOOK_URL` is already in the environment
(`docker-compose.yml:470`); this makes every service use it consistently.

**Tdarr** or **FileFlows** — automated transcoding to reduce Plex's live
transcode load. Only worth it if Tautulli (above) shows transcoding is actually
the bottleneck. Do not add it speculatively.

**Wizarr** — Plex invite and onboarding management. Add only if the stack serves
users beyond the operator.

**Watcharr** — a web watchlist that reads Radarr/Sonarr library lists and lets a
non-technical household member browse "have/want" without touching the *arr
UIs. Complements Seerr when requests are automated but discovery is not.

**Changedetection.io** — polls arbitrary web pages and alerts on diffs. Useful
here to watch indexer-availability pages, provider status boards or pricing
announcements, then feed the result into ntfy/Alertmanager. Optional; skip if
nothing external needs watching.

## Application runtime

**gunicorn** — the fix for item 11, and the smallest high-value change in this
document. One line in `requirements-prod.txt`, one in the Dockerfile.

**PostgreSQL** — replaces SQLite (item 40). Removes the write-lock ceiling and
makes multi-worker gunicorn safe. One container plus a Django `DATABASES` change;
migrate with `dumpdata`/`loaddata`.

**Redis** — Django cache backend and session store. Takes session writes off the
database entirely, which is most of the write pressure in item 40. Also serves
Authelia if that is adopted.

**ntfy** — a tiny self-hosted push-notification server. Gives the stack an
alerting channel that does not depend on a third-party webhook like
`DISCORD_WEBHOOK_URL`; phones subscribe to a topic and Alertmanager/backup
script publish to it. One container, no account.

**Mailpit** — a local, zero-config SMTP catcher. The control panel's Django app
today has no email backend, so any mail (password resets, import failures) falls
back to console. Point Django at Mailpit to get real `Message` objects you can
inspect, or hand them to a relay later — without an external mail provider.

**Komodo** — a maintained, self-hosted image-update notifier with a web UI,
along the lines of the removed Watchtower directory (item 54) but notify-first
and actively developed. Lists every compose service with its pinned vs. newest
digest, so items 27 and 28 can be reviewed in one screen instead of grepping
`docker-compose.yml`.

## Development tooling

**Renovate** — supersedes the existing Dependabot config for this repo's needs:
it understands Docker Compose image tags *and* digests, so it can drive items 27
and 28 continuously rather than as a one-time pinning exercise. Group all *arr
images into a single PR.

**pre-commit + gitleaks** — item 35. `secret-guard.yml` catches leaked secrets
after they are committed; gitleaks catches them before.

**hadolint** — Dockerfile linting for the three Dockerfiles. Would have flagged
item 11's `runserver` CMD pattern and the missing `USER` directive.

**syft + cosign** — SBOM generation and keyless signing for items 32 and 33.
Both are single steps in `docker-publish.yml`.

**dive** — image layer inspection. Useful once the Django image is published
(item 36) to check whether `collectstatic` output and the pip cache are bloating
it.

**just** — a command runner to replace the dispatch logic in `setup.sh`
(item 41). A `justfile` with `just setup`, `just backup`, `just health` is
self-documenting in a way a 444-line bash script is not.

---

# 9. Findings from Tier 1 implementation (this pass)

Items discovered and, where noted, resolved while applying te Tier 1 security
batch. The addressed ones are marked DONE; the rest remain open.

### 58. DONE — control-panel Dockerfile never packaged the `cli` app
**Severity:** HIGH (build-time) · **Effort:** S
**During:** item 11 gunicorn rebuild
**Finding:** `services/control-panel/django/Dockerfile` had no `COPY cli ./cli`
even though INSTALLED_APPS declares `"cli"`. `collectstatic` therefore failed
with `ModuleNotFoundError: No module named 'cli'`, and the running control-panel
image was out of sync with the source (it predated the `cli` app added in commit
32f475c). The image was effectively un-rebuildable until linked.
**Fix (applied):** added `COPY cli ./cli`. Image now builds; 165 static files
collected. Any future app must be added to both INSTALLED_APPS and the COPY list.

### 59. Loki ingestion rate limit silently drops logs during bursts
**Severity:** MEDIUM · **Effort:** S
**During:** item 2 promtail restart
**Finding:** on restart, promtail caught up a large backlog and Loki overflowed
the default per-tenant `ingestion_rate_mb` (4 MB/s), emitting repeated HTTP 429
`ingestion rate limit exceeded` and retrying/dropping batches. This is a
pre-existing Loki limits issue, adjoining item 37.
**Fix:** raise `limits_config.ingestion_rate_mb` (e.g. 64) and
`ingestion_burst_size_mb` in `config/loki/loki-config.yaml`, and add a
`per_stream_rate_limit` guard so one noisy service cannot wedge the pipeline.
Fold into item 37.

### 60. DONE — four cross-service secrets had the `changeme` default
**Severity:** HIGH · **Effort:** M
**During:** post-Tier-1 secret cleanup — resolved this session
**Finding:** `METACACHE_API_KEY`, `WS_API_KEY`, `WS_SYSTEM_SECRET` and
`CONTROL_PANEL_SERVICE_API_KEY` were literal `changeme`, and the control-panel
DB `healthcheck-cron` key hash matched `changeme`.
**Fix (applied):** rotated all four to fresh 32-char hex values in `.env`, then
`--force-recreate`d metacache, watchstate and control-panel, and re-ran
`bootstrap` so the `healthcheck-cron` hash tracks the new service key. Verified
all three healthy, `/healthz` 200, and the DB hash matches the new key (no
longer `changeme`). `.env` now contains zero `changeme` placeholders.

### 61. OFF-BOX backup (item 44) deferred — no destination exists on host
**Severity:** HIGH · **Effort:** L → blocked
**During:** restic decision — skipped this pass by choice (option: "skip restic")
**Finding:** host has a single root disk (938 GB, 70% used) with no second disk,
NAS/SMB/NFS/SFTP endpoint, or cloud credentials, so "restic to an off-box
repository" cannot execute as written. `backup.sh` still writes to local
`backups/` on the same disk.
**Fix (future):** once an off-box destination exists (cloud B2/S3, SFTP host, or
a periodically-attached USB/eSATA drive), install restic, init an encrypted
repo, wrap `backup.sh`, and add `restic check` + a restore-into-scratch smoke
test (item 25). Documented for the operator; no install performed this pass.

### 62. The pre-Tier-1 Trivy "IaC gate" never scanned anything
**Severity:** HIGH (process) · **Effort:** done
**During:** item 29 rewrite
**Finding:** the old command passed three Dockerfiles + compose to one `trivy
config` invocation. Trivy fatally rejects multiple targets (
`multiple targets cannot be specified`), and `docker-compose.yml` is not a valid
misconfig target for `trivy config` (0 files detected). Combined with `|| true`,
the gate produced neither scanned results nor failures.
**Fix (applied):** per-file loop over the three Dockerfiles, `--exit-code 1`,
repo `.trivyignore` (DS-0002 only, deferred to item 7). All three scan clean.
