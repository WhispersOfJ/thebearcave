# Contributing to the Bear Cave

Thanks for wanting to contribute! These guidelines explain how to open good
issues and well-formed pull requests for this repository, what the review
process looks like, and how to report problems. Following them saves everyone
time.

This repository is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold it. Instances of abusive or unacceptable
behavior should be reported to the address in that document.

## Table of contents

- [Before you start](#before-you-start)
- [Reporting bugs](#reporting-bugs)
- [Requesting features](#requesting-features)
- [Making changes](#making-changes)
- [Worktree discipline](#worktree-discipline)
- [Commit and PR conventions](#commit-and-pr-conventions)
- [Validation checklist](#validation-checklist)
- [Code style](#code-style)
- [Review and merge](#review-and-merge)
- [Getting help](#getting-help)

## Before you start

- **Check existing work.** Search issues and open/merged PRs before opening a
  new one — your bug may already be filed or fixed on `main`.
- **Read the docs.** Start with `AGENTS.md` (the system reference) and the
  relevant service doc under `docs/services/`. The architecture overview is in
  `docs/architecture.md`, and the operational landmines you must never trip
  are in `AGENTS.md` and `docs/landmines.md`.
- **Know the scope.** This is a slim, 8-service media stack with strict CI.
  Changes must keep the stack robust and the docs honest; retiring or adding a
  service is a big change and should be proposed first.

## Reporting bugs

Use the **Bug report** issue template (`.github/ISSUE_TEMPLATE/bug_report.yml`).
A good report includes:

- What you did, what you expected, and what actually happened.
- Which service(s) were involved (Plex, NzbDAV/rclone, Radarr/Sonarr/Prowlarr,
  Seerr/Unpackerr, CI/CD, scripts).
- How to reproduce, with exact commands.
- Relevant logs or screenshots (scrub credentials first).
- The stack versions (`stack-version`) and any error text verbatim.

Before filing, check the known failure modes in `AGENTS.md` ("Historical Issues
and Landmines") — several recurring problems (FUSE mount staleness, orphaned
*arr references, DB bloat) are documented there with their fixes.

## Requesting features

Use the **Feature request** issue template
(`.github/ISSUE_TEMPLATE/feature_request.yml`). Describe the problem you want
solved, not just a solution, and note which service or area it affects.

## Making changes

Every change to this repository flows through a pull request. `main` is
branch-protected — nobody pushes to it directly — and **all work happens on
dedicated git worktrees, one worktree per task** (see
[Worktree discipline](#worktree-discipline) and
[docs/worktree-lifecycle.md](docs/worktree-lifecycle.md)).

1. Create a task-named worktree off `origin/main`.
2. Make exactly this task's changes inside it — never mix unrelated work.
3. Run the [validation checklist](#validation-checklist).
4. Commit with a Conventional Commit message and push the branch.
5. Open a PR against `main` (the PR template
   [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)
   attaches automatically — fill it in).
6. Address review feedback; keep the branch up to date with `main`.

## Worktree discipline

Mandatory, effective 2026-08-31. One worktree per task, named by the task,
never mixed with unrelated work. The main checkout stays clean and is used for
reference only.

The `stack-worktree` helper creates the task-named branch and worktree in one
command (raw `git` equivalents and the full lifecycle are in
[docs/worktree-lifecycle.md](docs/worktree-lifecycle.md)):

```fish
stack-worktree docs/fix-readme     # branch docs/fix-readme at ../wt-fix-readme
```

- Task names are lowercase and dash-separated, optionally type-prefixed
  (`docs/`, `feat/`, `fix/`, `ci/`, `chore/`).
- `stack-worktree` refuses when a worktree/branch for that task already exists
  locally or on the remote, so check for a twin under a *different* name too:
  `git worktree list`.
- After the PR merges, remove the worktree and delete the branch:
  `git worktree remove <path>` and `git branch -D <branch>` if it survived.

## Commit and PR conventions

**PR titles and commit messages must be Conventional Commits** — enforced by
the `pr-lint` workflow. Allowed types:

```
feat  fix  docs  style  refactor  perf  test  build  ci  chore  revert  docker
```

Examples: `fix: bound install verification with a timeout`,
`feat: add stack-plex-markers`, `docs: add contributing guidelines`.

- Release behavior: `release-please` opens a release PR only for `feat:` and
  `fix:` commits. `ci:`, `docs:`, `chore:`, etc. land silently without a
  release — do not expect a version bump for docs-only changes.
- PR titles follow the same convention; the subject must not start with a
  space.
- Linear history: merges are squash or rebase only — never merge commits.

## Validation checklist

Run these before opening a PR (they mirror what CI runs):

```bash
docker compose config --quiet
bash -n scripts/*.sh tests/*/*.sh
bash tests/fish/test_fish_functions.sh --offline
fish services/fish-functions/scripts/gen-completions.fish --check
python3 scripts/check_compose_mounts.py
./tests/health/run-all.sh
```

- `validate.yml` runs compose validation, env coverage, shellcheck, ruff, and
  actionlint; `nightly-healthcheck.yml` re-validates everything daily.
- If you change a fish function, regenerate completions
  (`fish services/fish-functions/scripts/gen-completions.fish`) so the
  completion-drift check stays green, and run the offline fish smoke test.
- Live checks (e.g. `./tests/integration/test_pipeline.sh`, the full fish
  smoke suite) run against the real stack on the host — never rely on them in
  CI, and never run mutating ones against active queued work.

## Code style

- **Python:** Ruff (see `.github/workflows/validate.yml`); match the existing
  check-script conventions (read-only DB access, `0/1/2` exit codes,
  CI-safe pure-logic tests under `scripts/test_*.py`).
- **Shell:** ShellCheck-clean, POSIX-ish bash for CI; `bash -n` must pass.
- **Fish:** `fish_indent`-clean (a missing trailing newline fails CI), one
  command per file under `services/fish-functions/functions/`, shared
  `fmt_*` helpers from `__cli_format.fish`, and repo-root resolution via
  `$BEARCAVE_REPO_DIR` (see `conf.d/bearcave-env.fish`).
- **Workflows:** third-party actions are SHA-pinned with a `# tag` comment;
  GitHub Actions are validated by `actionlint` (see `docs/ci-cd.md`).

## Review and merge

- The branch-protection ruleset requires the CI checks and a Conventional
  Commit title to pass. If `main` advances while your PR is open, rebase and
  push with `--force-with-lease` (never force-push blindly; fetch and rebase a
  clean local commit first).
- Merges are squash merges via `gh pr merge <number> --squash --delete-branch`,
  followed by `git worktree remove` for cleanup.
- After merge, delete the local branch if the worktree check-out kept it.

## Getting help

- `stack-help` lists every terminal command in the repo.
- Service documentation lives in `docs/services/`; CI/CD policy in
  `docs/ci-cd.md`; testing conventions in `docs/testing.md`.
- For security issues, follow `docs/security.md` and report privately rather
  than opening a public issue.
- Ask in a GitHub discussion or on an issue before large or cross-cutting
  changes (service additions/retirements, networking, CI restructuring).
