#!/usr/bin/env python3
"""Guard against Prowlarr orphan references (the *arr-family sibling of
AGENTS.md landmine #8).

Prowlarr shares the *arr SQLite architecture. Orphaned references here mean an
indexer or indexer<->application mapping that points at a deleted entity. Check
the SQLite DB directly, read-only, for:

  * Indexers.DownloadClientId -> a deleted DownloadClients row (Id 0 is the
    "no download client" sentinel and is always valid).
  * Indexers.AppProfileId     -> a deleted AppSyncProfiles row.
  * ApplicationIndexerMapping.IndexerId -> a deleted Indexer row.
  * ApplicationIndexerMapping.AppId     -> a deleted Applications row.

Read-only and safe to run while Prowlarr is live. Exit codes:
  0  every reference resolves
  1  one or more orphan references found
  2  the Prowlarr DB could not be located or read (operational; treat as skip)

Usage:
  python3 scripts/check_prowlarr_refs.py
  python3 scripts/check_prowlarr_refs.py --db /path/to/prowlarr.db
  PROWLARR_DB=/path/to/prowlarr.db python3 scripts/check_prowlarr_refs.py
"""

import argparse
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "config" / "prowlarr" / "prowlarr.db"


def _connect(db_path):
    uri = f"file:{urllib.parse.quote(str(db_path))}?mode="
    last = None
    for mode in ("ro", "immutable"):
        try:
            return sqlite3.connect(uri + mode, uri=True, timeout=15)
        except (sqlite3.Error, OSError) as exc:
            last = exc
    raise last


def _has_table(con, name) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def find_orphans(db_path) -> list:
    """Return [(kind, id, name, ref_label, ref_id)] for every orphan reference."""
    con = _connect(db_path)
    out = []
    try:
        # Only run the checks whose referenced table exists (older/fresh schemas
        # may not have DownloadClients or the mapping table yet).
        if _has_table(con, "DownloadClients"):
            for idx, name, client in con.execute(
                "SELECT Id, Name, DownloadClientId FROM Indexers "
                "WHERE DownloadClientId != 0 AND DownloadClientId NOT IN "
                "(SELECT Id FROM DownloadClients) ORDER BY Id").fetchall():
                out.append(("download-client", idx, name, "DownloadClientId", client))
        if _has_table(con, "AppSyncProfiles"):
            for idx, name, prof in con.execute(
                "SELECT Id, Name, AppProfileId FROM Indexers "
                "WHERE AppProfileId NOT IN (SELECT Id FROM AppSyncProfiles) "
                "ORDER BY Id").fetchall():
                out.append(("app-sync-profile", idx, name, "AppProfileId", prof))
        if con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ApplicationIndexerMapping'"
        ).fetchone():
            if _has_table(con, "Indexers"):
                for mid, idx, name in con.execute(
                    "SELECT m.Id, m.IndexerId, m.RemoteIndexerName FROM "
                    "ApplicationIndexerMapping m LEFT JOIN Indexers i ON i.Id = m.IndexerId "
                    "WHERE i.Id IS NULL ORDER BY m.Id").fetchall():
                    out.append(("mapping-indexer", mid, name, "IndexerId", idx))
            if _has_table(con, "Applications"):
                for mid, app, name in con.execute(
                    "SELECT m.Id, m.AppId, m.RemoteIndexerName FROM "
                    "ApplicationIndexerMapping m LEFT JOIN Applications a ON a.Id = m.AppId "
                    "WHERE a.Id IS NULL ORDER BY m.Id").fetchall():
                    out.append(("mapping-app", mid, name, "AppId", app))
        return out
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("PROWLARR_DB", str(DEFAULT_DB)))
    args = ap.parse_args()
    path = Path(args.db)
    if not path.is_file():
        print(f"prowlarr DB not found at {path}; skipping (set PROWLARR_DB or --db)")
        return 2
    try:
        orphans = find_orphans(path)
    except (sqlite3.Error, OSError) as exc:
        print(f"CHECK FAILED: could not read prowlarr DB {path}: {exc}")
        return 2

    if orphans:
        for kind, fid, name, ref, rid in orphans:
            print(f"  {kind}: id {fid} '{name}' -> {ref} {rid} (deleted target)")
        print(f"CHECK FAILED: {len(orphans)} orphan reference(s); remove or re-point "
              "them in Prowlarr (reassign download client / app sync profile, or "
              "delete stale app indexer mappings).")
        return 1
    print("OK: every indexer reference resolves (download client, app sync profile, "
          "application mappings).")
    return 0


if __name__ == "__main__":
    sys.exit(main())