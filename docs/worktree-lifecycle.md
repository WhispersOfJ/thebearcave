# Task Worktree Lifecycle

The canonical way to make any change to this repository, per the
[AGENTS.md Worktree Discipline](../AGENTS.md): one task-named worktree per
task, never mixed with unrelated work, delivered to `main` via a pull
request. `main` is branch-protected, so every change flows through this
cycle.

The `stack-worktree` helper performs steps 1–2 automatically; the raw `git`
commands are shown alongside for reference.

## 1. Create the task worktree

With the helper (creates branch + worktree off `origin/main`, then drops you
into it):

```fish
stack-worktree docs/fix-readme    # branch docs/fix-readme at ../wt-fix-readme
```

Raw git:

```bash
cd /path/to/thebearcave
git fetch origin main
git worktree add -b docs/fix-readme ../wt-fix-readme origin/main
cd ../wt-fix-readme
```

Task names are lowercase and dash-separated, optionally type-prefixed
(`docs/`, `feat/`, `fix/`, `ci/`, `chore/`). One worktree per task: an
unrelated need gets its own worktree, never commits stacked on this one.

## 2. Edit

Make only this task's changes inside the worktree, and review them:

```bash
$EDITOR README.md
git diff                # shows exactly this task's changes
```

## 3. Validate

Run the checks CI will run:

```bash
docker compose config --quiet
bash -n scripts/*.sh tests/*/*.sh
bash tests/fish/test_fish_functions.sh --offline
fish services/fish-functions/scripts/gen-completions.fish --check
```

## 4. Commit and push

```bash
git add README.md
git commit -m "docs: fix readme"
git push -u origin docs/fix-readme
```

## 5. Open a PR

```bash
gh pr create --base main --head docs/fix-readme \
  --title "docs: fix readme" \
  --body "One-line summary of the task."
```

The branch protection ruleset requires `validate`, `check`, the quality
checks, and a Conventional Commit title to pass before merging. If `main`
advances while the PR is open, rebase and force-push:

```bash
git fetch origin main
git rebase origin/main
git push --force-with-lease
```

## 6. Merge

Linear history means squash or rebase only:

```bash
gh pr merge <number> --squash --delete-branch
```

## 7. Remove the worktree

Run from the main checkout (not from inside the worktree):

```bash
cd /path/to/thebearcave
git worktree remove ../wt-fix-readme
```

If the local branch survived `--delete-branch` (it was checked out in the
worktree), delete it too:

```bash
git branch -D docs/fix-readme
```

The task is complete; nothing is left behind.
