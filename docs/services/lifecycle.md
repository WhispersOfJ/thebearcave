# Service Lifecycle & Retirement

Tracks services that have been **retired** from the active stack and whether /
how they can come back. "Retired" means removed from `docker-compose.yml` and the
supporting files (landing page registry, docs, tests, scripts, AGENTS.md) — distinct
from a temporary outage. Every retirement here is deliberate: the service was either
superseded, no longer fits, or is gated on an external condition.

A retired service either has a **re-adoption watcher** (an automated upstream watch
that pings the stack when the blocker clears) or is retired **by decision** (no plan to
return, kept only in `archive/`).

## Why this page exists

Removal is expensive and easy to get wrong — the AGENTS.md landmine checklist runs to
compose, config, env vars, Prowlarr sync, landing page registry, docs, tests, scripts,
and the trivy baseline. This page records the reference so nobody has to re-derive what
was retired, why, and what it would take to bring it back.

## Retired services

| Service | Retired | Reason | Re-adoption watcher | Where it went |
|---------|---------|--------|---------------------|---------------|
| `cleanuparr` | 2026-08-29 | Torrent-only; no SABnzbd/Usenet client, so nothing to monitor in the Usenet-only stack | ✅ `cleanuparr-sabnzbd-watch.yml` | removed (no archive) |
| `uptime-kuma` | 2026-08-29 | Dropped from expansion scope by decision (image still CVE-blocked at the time) | ❌ none (decision) | removed (no archive) |
| `control-panel` (Django) | 2026-08-27 | Django backend superseded — fish functions call services directly, landing page probes via nginx | ❌ none (archived) | `archive/control-panel/` |

## Services with an active re-adoption watcher

### cleanuparr

- **Why it was retired:** Cleanuparr v2.x only supports torrent clients
  (qBittorrent / Deluge / Transmission / rTorrent). This stack is Usenet-only, and with
  no SABnzbd-compatible client there was nothing for it to monitor, so it was removed
  end to end (commit `4604423`).
- **Watcher:** [`.github/workflows/cleanuparr-sabnzbd-watch.yml`](../../.github/workflows/cleanuparr-sabnzbd-watch.yml)
  — daily 06:23 UTC + manual dispatch. It reads the latest upstream
  `Cleanuparr/Cleanuparr` release; when the release notes mention SABnzbd/Usenet it
  opens a `cleanuparr-adopt` issue in this repo (with the full re-adoption checklist)
  and posts a Discord alert. Idempotent — one alert per adoption issue; a stale open
  issue is closed if upstream stops reporting the feature as shipped.
- **Choosing the signal matters:** the upstream feature request (#137) is closed as
  **`not_planned`** and its duplicates (#263/#273) closed as duplicates, so **issue
  state is intentionally not used** as a shipped signal — only release-notes text is
  trusted. Open SABnzbd PRs are reported as an informational in-flight note, not an alert.
- **To adopt when it fires:** follow the checklist in the `cleanuparr-adopt` issue — it
  mirrors the removal in reverse (compose service, NzbDAV SABnzbd-compatible download
  client at `nzbdav:3000`, `CLEANUPARR_URL`, landing page registry, docs/tests, trivy
  baseline).

## Retired by decision (no watcher)

### uptime-kuma

Removed from the 10-service expansion by decision (commit `ad04cf8`) while its image
was still CVE-blocked, rather than gated behind a re-scan. All files — workflow, docs,
spec references, and local images — were removed. There is no watcher and no plan to
return unless monitoring needs change; the service count in AGENTS.md reflects this.

### control-panel (Django)

The Django control panel was removed in Phase 4 (commit `faf4127`) after its role was
superseded: fish functions call the *arr/dashboard APIs directly, and the landing page
probes health through nginx. Its files live in `archive/control-panel/` for reference.
No watcher — this was a deliberate teardown, not a hold for return.

> **Convention:** `archive/` content is reference material and is never revived into the
> active stack; any return must be a fresh, tracked implementation, not a copy.

## How to add a re-adoption watcher

When retiring a service that could return if an external condition clears:

1. **Pick a reliable "so it can come back" signal** — prefer an objective upstream
   artifact (release-note text, a shipped image tag with known-good CVE state). Avoid
   signals that lie: an issue being *closed* is not proof of shipping (it may be
   `not_planned` or a duplicate).
2. **Make it idempotent** — open one tracking issue per detection and reuse it, so an
   always-true signal alerts once, not every run.
3. **Escalate through the stack's alert channel** — Discord via the existing
   `secrets.DISCORD_WEBHOOK_URL` pattern (skip gracefully when unset).
4. **Mirror the removal in the adoption checklist** so the fix is mechanical.
5. Wire the workflow into `docs/ci-cd.md` and run `actionlint` — every workflow is
   actionlint-gated in CI.