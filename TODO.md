# TODO — Stack Projects

Ordered project backlog for the stack, drawn from the 2026-09-02 session
(post-slim-down maintenance era). Each entry records the compatibility
research done at write time so work never duplicates what already exists.

> **Working style reminder (AGENTS.md):** every task below ships on its own
> task-named worktree + PR. "For the stack" means **host-runnable, API-backed,
> one job each** — no new always-on containers unless the entry explicitly
> says otherwise (the 2026-08-30 slim-down record is the cautionary tale).

---

## 1. Nightly maintenance-verification digest

One host-runnable job that asserts the maintenance actually happened, then
prints a single morning summary:

- `~/.stack-disk-reclaim.log` updated since the last 04:00 run
- no failed user/system timers (`systemctl --user --failed` empty)
- dotfiles pushed (`.dotfiles` `main` matches `origin/main`; job script exits 0)
- Radarr/Sonarr DB sizes under the `check_radarr_db_size.py` threshold
- NzbDAV queue empty

**Compatibility research (2026-09-02):** NOT built. Host-side health units
exist (`stack-health-check`, `stack-plex-health-monitor`, `stack-plex-report`,
`stack-arr-backup` under `~/.config/systemd/user/`) but none aggregates these
signals. Would have caught the 17-day silent dotfiles-push failure and the
dead media-stack cron entries within 24h. Optional Discord ping via the
existing `DISCORD_WEBHOOK_URL` pattern (alertmanager removed Discord alerting).

## 2. `stack-audit-residue` — retired-service/path residue checker

Scan compose, `.env.template`, docs, workflows, crontab, and user timers for
references to retired services and dead paths (the automated form of the
exhaustive-removal checklist, AGENTS.md landmine #7).

**Compatibility research (2026-09-02):** NOT built. This session found such
residue by hand (media-stack cron entries, node-exporter-era
`stack-health-metrics` timer, poster/letterboxd syncs into the retired
`/home/bear/Claude/media-stack`). Pattern precedent:
`scripts/check_mount_drift.py` / `check_secret_drift.py` (failing `check_*`
script + guard wiring in `validate.yml` / `nightly-healthcheck.yml`).

## 3. Config-drift checker — running images vs compose pins

Surface containers whose running image differs from the compose pin
(unpackerr `0.15.2` running vs `v0.16.1` pinned; Plex on an older digest than
compose's pin — both found manually this session).

**Compatibility research (2026-09-02):** NOT built — drift checking exists only
for mounts (`check_mount_drift.py`) and secrets (`check_secret_drift.py`).
Follow the same `check_*` + CI-guard pattern. Distinct from #2 (this is
*current-config* drift, not retired residue).

## 4. Bazarr re-adoption (fresh implementation)

Subtitle capability, retired 2026-08-30 for OOM crash-looping at 128m — not
for being useless. Re-adopt per `docs/services/lifecycle.md` convention: fresh
tracked implementation (never a copy from `archive/`), real memory cap
(512m–1g), DB hygiene, Sonarr wiring, Prowlarr sync, trivy baseline.

**Compatibility research (2026-09-02):** retired by decision, no watcher;
re-adoption would raise the service count above 8 and total mem caps
(≈12.1g/22g today) — deliberate scoping decision needed before starting.

## 5. Radarr DB growth-trend predictor

`check_radarr_db_size.py` (gate) and `prune_radarr_db.py` (remediation) exist;
nothing *predicts* when the next prune is needed from growth history.

**Compatibility research (2026-09-02):** gate + remediation live (AGENTS.md
landmine #9). Add a size-history record (SQLite or flat log) and trend the
growth rate — turns the incident into a calendar entry.

## 6. "What's watchable tonight" — thin read-only view

Plex unwatched + Radarr/Sonarr recently-added + Seerr request state, rendered
via the existing host-published APIs (no container — a "dashboard that isn't
a dashboard").

**Compatibility research (2026-09-02):** NOT built. `arr-dashboard` and
`landing-page` were retired by decision in the slim-down; this is the thin,
API-only shape that avoids their failure mode. Reuse the `stack-*` bash
function API surface (`__arr_api` / `__plex_api` / `__seerr_api` helpers).

## 7. Request → arrival notifier

Seerr request approved → Radarr/Sonarr grab → download complete → Plex scan →
one Discord ping. The minimal useful slice of retired watchstate.

**Compatibility research (2026-09-02):** NOT built. watchstate retired by
decision. Seerr + Unpackerr were *retained* in the slim-down precisely for
request handling/extraction — this wires their outcomes into a single
notification chain. Webhook env pattern precedent: `DISCORD_WEBHOOK_URL`.

## 8. Media-stack activity feed (thin)

RSS/JSON of imports, upgrades, deletions via the *arr apps' existing webhook
events — a small listener, no container.

**Compatibility research (2026-09-02):** NOT built. Radar/Sonarr webhook events
are already configured endpoints; nothing consumes them today.

---

### Compatibility notes shared by all entries

- Host RAM headroom is ~9.8g of 22g after the slim-down rebalance; new
  always-on services are the exception, not the default.
- Reuse the `stack-*` bash surface and `scripts/` guard pattern
  (`check_*` + test + `validate.yml`/`nightly-healthcheck.yml` wiring).
- Every new workflow file is actionlint-gated; pre-commit gates local + CI
  hook parity (gitleaks/ruff/shellcheck/check-yaml/EOF/whitespace).
- Release-worthy changes (`feat:`/`fix:`) trigger release-please; keep
  `docs:`/`chore:` out of release scope unless a release is intended.
