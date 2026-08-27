# CI/CD

Everything about how this repo is built, tested, and released on GitHub Actions —
and the two policies every operator must know: **actions are SHA-pinned** and
**workflows are actionlint-gated**.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `validate.yml` | push/PR to `main` | The gate: compose validation, `.env.template` coverage, shellcheck, ruff, bash syntax, **actionlint**, Django + exporter unit tests |
| `release-please.yml` | push to `main` | Conventional-commit release automation: bumps version, updates CHANGELOG, opens the release PR (needs `RELEASE_PLEASE_TOKEN` — see below) |
| `trivy-scan.yml` | push/PR to `main` + weekly | CVE-scan all 22 images, IaC config scan, commits `STAGE-4-CVE-BASELINE.md` |
| `dotnet-ci.yml` | push/PR to `main` | Build/format/test/coverage/NuGet CVE audit for metacache |
| `docker-publish.yml` | push to `main` | Build + push metacache to GHCR, nightly Trivy rescan |
| `codeql.yml` | push/PR to `main` + weekly | CodeQL security analysis (Python + C#) |
| `nightly-healthcheck.yml` | nightly (schedule) | Compose/Dockerfile/script/config validation against a live stack |
| `pr-labeler.yml` | `pull_request_target` | Auto-labels PRs by size and changed paths |
| `pr-lint.yml` | `pull_request_target` | Enforces Conventional Commits in PR titles |
| `stale.yml` | schedule | Auto-closes stale issues/PRs |
| `secret-guard.yml` | push/PR to `main` | Fails when a workflow references a secret not declared in `.github/required-secrets.json`, or a declared secret's `.env.template` var is missing |
| `cert-expiry-check.yml` | weekly + dispatch | Probes the Traefik HTTPS certificate and alerts via Discord before it expires |
| `disk-cleanup.yml` | weekly + dispatch | Prunes Docker images/volumes/build cache when disk usage crosses a threshold, alerts via Discord |
| `pin-drift-check.yml` | weekly + dispatch | Verifies all third-party action pins are current; opens/closes a `pin-drift` issue |

`dependabot.yml` (not a workflow) drives weekly version updates for Docker,
pip, NuGet, and GitHub Actions.

## Pinned actions policy

Every third-party action in `.github/workflows/` is pinned to a **full commit
SHA**, with the version recorded as a trailing comment:

```yaml
- uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
```

**Why:** a tag like `v5` is a mutable reference — it can be retargeted or
force-pushed, and a compromised or hijacked tag would silently inject code
into CI. A 40-char SHA is immutable.

**How to upgrade an action** (deliberate, documented, manual):

```bash
# 1. Resolve the commit SHA behind the tag you want
gh api repos/{owner}/{repo}/commits/{new-tag} --jq .sha

# 2. Update the uses: line in every workflow that references it:
#      uses: owner/repo@<that-sha> # <new-tag>
# 3. Run actionlint (below) and push — validate.yml re-checks everything.
```

**Dependabot limitation:** the `github-actions` ecosystem cannot update
SHA-pinned actions — it only bumps tag/major refs. That is intentional: action
upgrades are now explicit review points rather than silent weekly bumps.
Dependabot continues to update Docker, pip, and NuGet as normal.

## Actionlint gate

`validate.yml` runs **actionlint** on every push and PR to `main`. It is the
first line of defense for workflow files and fails CI early on:

- Invalid workflow YAML / syntax
- Bad expressions (e.g. `${{ size }}` where `size` isn't defined)
- Invalid `uses:` references, wrong action inputs, missing `with:` args
- **Shellcheck findings in `run:` blocks** — the runner has shellcheck
  preinstalled, so inline scripts are linted too, not just `scripts/*.sh`

The actionlint binary itself is downloaded in the workflow from the pinned
release (currently `v1.7.12`) — no third-party action is involved.

**Replicate CI locally before pushing:**

```bash
curl -sSL -o /tmp/actionlint.tar.gz \
  https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz
tar -xzf /tmp/actionlint.tar.gz -C /tmp actionlint
/tmp/actionlint .github/workflows/*.yml   # add shellcheck to PATH to match CI exactly
```

## Secrets used by CI

| Secret | Where it lives | Why |
|--------|----------------|-----|
| `RELEASE_PLEASE_TOKEN` | GitHub Actions secret (synced from `.env` via `./scripts/setup.sh --sync-github-secrets`) | Release PRs opened with a PAT get validate.yml run on them (the default `GITHUB_TOKEN` path is skipped by GitHub's recursion guard) |

The manifest `.github/required-secrets.json` is the source of truth — the
`secret-guard.yml` workflow fails if a workflow uses a secret that isn't
declared there, or a declared secret's `.env.template` variable disappears.

## Safe workflow-change checklist

1. Edit the workflow; **run actionlint locally** first (command above).
2. Push to a branch and open a PR — validate.yml runs on PRs too.
3. Confirm the `Validate` run is green before merging.
4. If you pinned/upgraded an action, mention the old → new SHA in the PR.
