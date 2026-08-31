# Usage: stack-worktree <task-branch>
# Creates a task-named git worktree and branch per the AGENTS.md Worktree
# Discipline: one worktree per task, named by the task, branched off
# origin/main, with the main checkout left clean.
#   stack-worktree docs/foo   -> branch docs/foo,  worktree ../wt-foo
#   stack-worktree fix-bar    -> branch fix-bar,   worktree ../wt-fix-bar
function stack-worktree --description 'Create a task-named git worktree and branch (AGENTS.md Worktree Discipline)'
    if test (count $argv) -ne 1
        echo "Usage: stack-worktree <task-branch>  e.g. stack-worktree docs/foo" >&2
        return 1
    end
    set -l branch $argv[1]

    # Task names are lowercase and dash-separated, optionally type-prefixed
    # (docs/foo, fix-bar, ci/quality-always-run, ...).
    if not string match -rq '^[a-z][a-z0-9-]*(/[a-z][a-z0-9-]*)?$' -- $branch
        fmt_error "Invalid task name '$branch' (use e.g. docs/foo or fix-bar)"
        return 1
    end

    set -l repo_root (git rev-parse --show-toplevel 2>/dev/null)
    if test -z "$repo_root"
        fmt_error "Not inside the repository"
        return 1
    end

    if git show-ref --verify --quiet "refs/heads/$branch"
        fmt_error "Branch '$branch' already exists locally; delete it or pick a different task name"
        return 1
    end

    # A twin attempt may exist on the remote only — pushed but unmerged, or
    # a stale branch from an earlier run. Refuse rather than fork a second
    # branch with the same name.
    if git show-ref --verify --quiet "refs/remotes/origin/$branch"
        fmt_error "Branch '$branch' already exists on origin (stale or in-flight); delete it or pick a different task name"
        return 1
    end

    set -l slug (string split -r -m 1 / -- $branch)[-1]
    set -l wt_path (path dirname -- $repo_root)/wt-$slug

    # A deleted worktree directory can leave a stale registration behind;
    # `test -e` misses it and `git worktree add` then fails cryptically.
    # Refuse and point at the one-line fix.
    if git worktree list --porcelain | string match -q "worktree $wt_path"
        fmt_error "Worktree '$wt_path' is registered but missing on disk; run 'git worktree prune' and retry"
        return 1
    end

    if test -e "$wt_path"
        fmt_error "Worktree path '$wt_path' already exists"
        return 1
    end

    git fetch -q origin main 2>/dev/null
    if not git worktree add -b $branch "$wt_path" origin/main
        fmt_error "Failed to create worktree (is origin/main available?)"
        return 1
    end

    cd "$wt_path"
    fmt_success "Worktree ready: branch $branch at $wt_path"
end
