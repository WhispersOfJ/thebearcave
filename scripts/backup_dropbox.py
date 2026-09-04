#!/usr/bin/env python3
"""
backup_dropbox.py
─────────────────
Stream a single tar archive of everything in The Bear Cave repo that is NOT
media, generated metadata, or secrets straight to Dropbox — the archive is
never written to disk and never fully buffered in RAM.

Design mirrors dropbox-uploader/CLAUDE_CODE_PROMPT.md conventions (same env
vars, same chunked upload-session protocol, same retry/exit-code policy) but
is a self-contained committed implementation: a true streaming session upload
that holds at most two 8 MB chunks in memory, so multi-GB archives stay flat.

What goes in (by default)
─────────────────────────
    everything under the repo checkout, including .git history and untracked
    files on disk, EXCEPT:

    * huge trees          config/plex/, config/nzbdav/, config/_backup-*/
                          config/plex-transcode/
    * runtime state       data/, logs/, usenet/, backups/, .cache/,
                          .memsearch/, .freebuff/, .ruff_cache/, .worktrees/
    * secrets             .env, .env.local, .env.*.local, secrets/,
                          docker-compose.override.yml,
                          config/nzbdav-rclone/rclone.conf (+ its cache/)
    * media               media/
    * generated metadata  *.db, *.db-wal, *.db-shm, logs.db* under the kept
                          config/*/ dirs, their Backups/backup*/restore/ and
                          logs/ dirs, and *.log anywhere   (lift with
                          --include-dbs)
    * generated cache     MediaCover artwork, Sentry crash dumps, and cache/
                          dirs under the kept config/*/ dirs (never lifted)

A snapshot therefore contains the code, docs, compose, workflows, per-app
*settings* (config/*.json|*.xml), and the git object store — but not the
multi-GB sqlite/library state or anything credential-bearing.

Usage
─────
    python3 scripts/backup_dropbox.py                 # stream + upload + prune
    python3 scripts/backup_dropbox.py --dry-run       # full pass, discard archive
    python3 scripts/backup_dropbox.py --include-dbs   # also ship sqlite DBs

Environment (same contract as dropbox-uploader/)
─────────────────────────────────────────────────
    DROPBOX_ACCESS_TOKEN       long-lived token (preferred)
    DROPBOX_REFRESH_TOKEN      OAuth2 refresh token
    DROPBOX_APP_KEY            app key   (required with refresh token)
    DROPBOX_APP_SECRET         app secret (required with refresh token)

Requires the `requests` package (Arch: pacman -S python-requests) and GNU tar.

Exit codes: 0 success · 1 upload error · 2 auth/config error · 3 bad args
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

# ── Network lib is imported lazily so the module (and its unit tests) import
#    cleanly on machines/CI without `requests`. ──────────────────────────────

CHUNK_SIZE = 8 * 1024 * 1024          # Dropbox sweet spot for session API
MAX_RETRIES = 4
RETRY_BACKOFF = [1, 2, 4, 8]          # seconds

DBX_UPLOAD_URL          = "https://content.dropboxapi.com/2/files/upload"
DBX_SESSION_START_URL   = "https://content.dropboxapi.com/2/files/upload_session/start"
DBX_SESSION_APPEND_URL  = "https://content.dropboxapi.com/2/files/upload_session/append_v2"
DBX_SESSION_FINISH_URL  = "https://content.dropboxapi.com/2/files/upload_session/finish"
DBX_LIST_FOLDER_URL     = "https://api.dropboxapi.com/2/files/list_folder"
DBX_DELETE_URL          = "https://api.dropboxapi.com/2/files/delete_v2"

REPO_DEFAULT = Path(__file__).resolve().parent.parent   # repo root
DEFAULT_DROPBOX_DIR = "/Backups/cave"
DEFAULT_KEEP = 30

# ─────────────────────────────────────────────────────────────────────────────
#  Exclusion model
# ─────────────────────────────────────────────────────────────────────────────
#  Member names inside the archive are relative to the repo root and start
#  with "./" (tar -C <root> -cf - .). Patterns below use that form.
#  The categories mirror docs/operations/dropbox-backup.md — keep in sync.

EXCLUDE_CATEGORIES: dict[str, list[str]] = {
    "huge-trees": [
        "./config/plex",
        "./config/plex-transcode",
        "./config/nzbdav",
        "./config/_backup-*",
    ],
    "runtime": [
        "./data",
        "./logs",
        "./usenet",
        "./backups",
        "./.cache",
        "./.memsearch",
        "./.freebuff",
        "./.ruff_cache",
        "./.worktrees",
        "./tmp",
    ],
    "secrets": [
        "./.env",
        "./.env.local",
        "./.env.*.local",
        "./secrets",
        "./docker-compose.override.yml",
        "./config/nzbdav-rclone/rclone.conf",
        "./config/nzbdav-rclone/cache",
    ],
    "media": ["./media"],
    # Regenerable per-app cache/artwork/crash trees inside the *kept*
    # config/<app>/ dirs: poster/cover artwork (config/radarr/MediaCover was
    # 25 GB and config/sonarr/MediaCover 2.9 GB on 2026-09-04), crash dumps,
    # and cache dirs. Not configuration — NEVER lifted, not even by
    # --include-dbs (that flag ships databases, not gigabytes of jpgs).
    "generated-cache": [
        "./config/*/MediaCover",
        "./config/*/Sentry",
        "./config/*/cache",
        "./config/*/.cache",
    ],
    # Generated metadata (sqlite state + its backup/log dirs) inside the
    # *kept* config/<app>/ dirs. Everything in config/plex|nzbdav is already
    # excluded wholesale by "huge-trees". Lifted by --include-dbs.
    "metadata": [
        "./config/*/*.db",
        "./config/*/*.db-wal",
        "./config/*/*.db-shm",
        "./config/*/*/*.db",
        "./config/*/Backups",
        "./config/*/backup*",
        "./config/*/restore",
        "./config/*/logs",
        "./*.log",
        "./config/*/*.log",
    ],
    "hygiene": [
        "./__pycache__",
        "./.pytest_cache",
        "./*.pyc",
    ],
}


def build_exclude_patterns(include_dbs: bool = False) -> list[str]:
    """Flatten the exclusion model into tar --exclude patterns.

    include_dbs=True lifts only the "metadata" category (sqlite DBs, WAL/SHM,
    per-app Backups/ and logs/ dirs) so callers can opt into shipping the
    library state; huge trees, media, and secrets are never lifted.
    """
    patterns: list[str] = []
    for category, members in EXCLUDE_CATEGORIES.items():
        if include_dbs and category == "metadata":
            continue
        patterns.extend(members)
    return patterns


def snapshot_stem(now: Optional[datetime.datetime] = None) -> str:
    """UTC timestamped archive stem: thebearcave-backup-YYYYMMDD-HHMMSS."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return f"thebearcave-backup-{now:%Y%m%d-%H%M%S}"


def compression_flag(compression: str) -> list[str]:
    return {"gzip": ["-z"], "none": []}[compression]


def start_tar(root: Path, patterns: list[str], compression: str,
              verbose: bool = False) -> subprocess.Popen:
    """Spawn GNU tar writing the filtered archive to stdout.

    The caller must consume (or close) proc.stdout, then check the exit code
    via finish_tar(). Nothing is written to disk by this process.
    """
    cmd = ["tar", "-C", str(root), "-cf", "-"] + compression_flag(compression)
    for pattern in patterns:
        cmd += ["--exclude", pattern]
    cmd.append(".")
    if verbose:
        print(f"tar: {' '.join(cmd)}", file=sys.stderr)
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def finish_tar(proc: subprocess.Popen) -> None:
    """Close the tar child after its stdout was fully consumed and surface
    failures (e.g. unreadable files under the root)."""
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(
            f"tar failed (exit {proc.returncode}): {err.strip()[:500]}"
        )


def iter_tar_chunks(proc: subprocess.Popen,
                    chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Read the tar child's stdout in bounded chunks. The child is reaped by
    finish_tar() once the caller's loop ends."""
    assert proc.stdout is not None
    while True:
        chunk = proc.stdout.read(chunk_size)
        if not chunk:
            break
        yield chunk


# ─────────────────────────────────────────────────────────────────────────────
#  Dropbox transport (raw HTTP via requests — same endpoints/policy as
#  dropbox-uploader/dropbox_upload.py, but streams without materialising)
# ─────────────────────────────────────────────────────────────────────────────

def _requests():
    try:
        import requests  # noqa: PLC0415
        return requests
    except ImportError as exc:  # pragma: no cover
        print(
            "error: the 'requests' package is required "
            "(Arch: sudo pacman -S python-requests)",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


def get_token() -> str:
    """Return a valid access token from DROPBOX_ACCESS_TOKEN or the OAuth2
    refresh trio. Exit 2 when none is configured (matches the uploader
    helper's contract)."""
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    if token:
        return token

    refresh = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
    key = os.environ.get("DROPBOX_APP_KEY", "").strip()
    secret = os.environ.get("DROPBOX_APP_SECRET", "").strip()
    if not (refresh and key and secret):
        print(
            "error: set DROPBOX_ACCESS_TOKEN  or  DROPBOX_REFRESH_TOKEN + "
            "DROPBOX_APP_KEY + DROPBOX_APP_SECRET\n"
            "see docs/operations/dropbox-backup.md → Auth",
            file=sys.stderr,
        )
        raise SystemExit(2)

    requests = _requests()
    resp = requests.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": key,
            "client_secret": secret,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"error: token refresh failed HTTP {resp.status_code}: "
              f"{resp.text[:300]}", file=sys.stderr)
        raise SystemExit(2)
    return resp.json()["access_token"]


def _headers(token: str, api_args: dict) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps(api_args),
    }


def _post_with_retry(url: str, headers: dict, data: bytes) -> dict:
    """POST with exponential backoff on 429/5xx/network errors; fatal on
    other 4xx (401/403 = bad token → exit 2, 409 = path conflict → 1)."""
    requests = _requests()
    for attempt, wait in enumerate(RETRY_BACKOFF, 1):
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=120)
        except requests.exceptions.RequestException as exc:
            print(f"  network error: {exc} — retry {attempt}/{MAX_RETRIES} "
                  f"in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504):
            print(f"  HTTP {resp.status_code} — retry {attempt}/{MAX_RETRIES} "
                  f"in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code in (401, 403):
            print(f"error: Dropbox auth failed HTTP {resp.status_code} — "
                  "check DROPBOX_* credentials", file=sys.stderr)
            raise SystemExit(2)
        print(f"error: Dropbox API HTTP {resp.status_code}: "
              f"{resp.text[:400]}", file=sys.stderr)
        raise SystemExit(1)
    print("error: exhausted retries", file=sys.stderr)
    raise SystemExit(1)


_EOF = object()   # sentinel: tar chunks are never empty, so this is unambiguous


def upload_session_stream(chunks: Iterator[bytes], dropbox_path: str,
                          overwrite: bool) -> tuple[dict, int]:
    """Chunked upload-session upload with a one-chunk lookahead.

    Dropbox protocol:  start(first chunk) → append_v2(every middle chunk) →
    finish(last chunk).  Because a chunk is only "last" once EOF is known,
    one chunk is held back; it is appended only when the next chunk has been
    read. Peak memory: two chunks (8 MB each), regardless of archive size.
    """
    mode = "overwrite" if overwrite else "add"
    token = get_token()
    it = iter(chunks)

    # First chunk opens the session and is its first payload.
    first = next(it, b"")
    if not first:
        print("error: archive stream was empty — nothing uploaded",
              file=sys.stderr)
        raise SystemExit(1)

    result = _post_with_retry(
        DBX_SESSION_START_URL,
        _headers(token, {"close": False}),
        first,
    )
    session_id = result["session_id"]
    offset = len(first)               # first was uploaded by start()
    sent = offset

    held = next(it, _EOF)             # chunk read but not yet sent anywhere
    while held is not _EOF:
        peek = next(it, _EOF)
        if peek is _EOF:
            # Nothing follows → held is the final chunk → break to finish it.
            break
        # A chunk follows held → held is a middle chunk → append it.
        _post_with_retry(
            DBX_SESSION_APPEND_URL,
            _headers(token, {"cursor": {"session_id": session_id,
                                        "offset": offset},
                             "close": False}),
            held,
        )
        offset += len(held)
        sent += len(held)
        held = peek

    if held is _EOF:
        # Single-chunk stream: the only chunk already rode start(); the
        # finish call commits the session with an empty payload.
        finish_payload = b""
    else:
        finish_payload = held          # final chunk's bytes were never sent
    result = _post_with_retry(
        DBX_SESSION_FINISH_URL,
        _headers(token, {
            "cursor": {"session_id": session_id, "offset": offset},
            "commit": {"path": dropbox_path, "mode": mode,
                       "autorename": not overwrite, "mute": False},
        }),
        finish_payload,
    )
    sent += len(finish_payload)
    return result, sent


def _json_post(url: str, token: str, payload: dict) -> dict:
    requests = _requests()
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"error: Dropbox API HTTP {resp.status_code}: "
              f"{resp.text[:400]}", file=sys.stderr)
        raise SystemExit(1)
    return resp.json()


def select_doomed(names: list[str], keep: int) -> list[str]:
    """Which snapshot names to delete so the newest ``keep`` remain.

    Pure helper (unit-testable without the network): names sort by the
    YYYYMMDD-HHMMSS prefix in the archive stem, so lexical order == age.
    """
    ordered = sorted(names)
    return ordered[:-keep] if len(ordered) > keep else []


def prune_older(folder: str, keep: int) -> int:
    """Delete oldest snapshots in ``folder`` so at most ``keep`` remain.

    Runs only after a successful upload. Returns the number deleted.
    """
    if keep <= 0:
        return 0
    token = get_token()
    entries = _json_post(DBX_LIST_FOLDER_URL, token,
                         {"path": folder, "limit": 1000})["entries"]
    names = [e["name"] for e in entries if e.get(".tag") == "file"]
    deleted = 0
    for name in select_doomed(names, keep):
        _json_post(DBX_DELETE_URL, token, {"path": f"{folder}/{name}"})
        deleted += 1
    return deleted


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stream a tar snapshot of the repo (no media/metadata/"
                    "secrets) to Dropbox without writing it to disk.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--repo", type=Path, default=REPO_DEFAULT,
                        help="checkout to snapshot (default: this repo)")
    parser.add_argument("--dropbox-dir", default=DEFAULT_DROPBOX_DIR,
                        help="Dropbox folder for snapshots (default: "
                             f"{DEFAULT_DROPBOX_DIR})")
    parser.add_argument("--include-dbs", action="store_true",
                        help="also ship sqlite DB/WAL/SHM + per-app "
                             "Backups/logs dirs (metadata category)")
    parser.add_argument("--compression", choices=["gzip", "none"],
                        default="gzip", help="archive compression (default gzip)")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help="retain this many newest snapshots, delete older "
                             f"(default {DEFAULT_KEEP}; 0 = keep all)")
    parser.add_argument("--overwrite", action="store_true",
                        help="overwrite an identically-named snapshot instead "
                             "of letting Dropbox autorename")
    parser.add_argument("--dry-run", action="store_true",
                        help="stream the archive to /dev/null and report "
                             "bytes — no upload, no prune")
    parser.add_argument("--verbose", action="store_true",
                        help="print the tar command and chunk progress")
    args = parser.parse_args(argv)

    root = args.repo.resolve()
    if not root.is_dir():
        print(f"error: --repo is not a directory: {root}", file=sys.stderr)
        return 3

    patterns = build_exclude_patterns(include_dbs=args.include_dbs)
    stem = snapshot_stem()
    ext = ".tar.gz" if args.compression == "gzip" else ".tar"
    dropbox_path = f"{args.dropbox_dir.rstrip('/')}/{stem}{ext}"

    print(f"Snapshot: {root.name} → {dropbox_path}")
    if args.verbose:
        for pattern in patterns:
            print(f"  exclude {pattern}")

    proc = start_tar(root, patterns, args.compression, verbose=args.verbose)
    try:
        if args.dry_run:
            total = 0
            for chunk in iter_tar_chunks(proc):
                total += len(chunk)
            finish_tar(proc)
            print(f"DRY-RUN OK  {stem}{ext} would be {total} bytes "
                  f"({total / 1024 / 1024:.1f} MiB); nothing uploaded")
            return 0

        result, sent = upload_session_stream(
            iter_tar_chunks(proc), dropbox_path, overwrite=args.overwrite)
        finish_tar(proc)
    except SystemExit:
        # Upload/auth failed mid-stream: stop tar so it cannot keep producing
        # into a dead pipe, then re-raise the exit code.
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise
    except Exception as exc:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print(f"error: {exc}", file=sys.stderr)
        return 1

    path_display = result.get("path_display", dropbox_path)
    print(f"OK  {path_display}  ({sent} bytes)")

    try:
        pruned = prune_older(args.dropbox_dir, keep=args.keep)
        if pruned:
            print(f"pruned {pruned} old snapshot(s), keeping the newest "
                  f"{args.keep}")
    except SystemExit as exc:
        # Prune failures shouldn't mask a completed backup, but they must be
        # visible. Report and keep exit 0 only if the upload itself succeeded.
        print(f"warning: prune failed: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
