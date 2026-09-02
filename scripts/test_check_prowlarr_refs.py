#!/usr/bin/env python3
"""Regression test for scripts/check_prowlarr_refs.py.

Verified cases (throwaway SQLite DB, no live Prowlarr):
  * clean DB - indexer with sentinel client 0 + valid app profile + valid mapping
  * an indexer referencing a deleted download client IS flagged
  * an indexer referencing a deleted AppSyncProfile IS flagged
  * an ApplicationIndexerMapping row with a missing IndexerId / AppId IS flagged
  * the DownloadClientId 0 "none" sentinel is never flagged (even with an empty
    DownloadClients table)

Run by validate.yml and nightly-healthcheck.yml, and locally via
`python3 scripts/test_check_prowlarr_refs.py`. Exits 0 on success, 1 otherwise.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_prowlarr_refs.py"

spec = importlib.util.spec_from_file_location("check_prowlarr_refs", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_db(clients, profiles, indexers, apps, mappings) -> str:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    f.close()
    con = sqlite3.connect(f.name)
    for name, ddl in {
        "DownloadClients": "(Id INTEGER PRIMARY KEY, Name TEXT)",
        "AppSyncProfiles": "(Id INTEGER PRIMARY KEY, Name TEXT)",
        "Indexers": "(Id INTEGER PRIMARY KEY, Name TEXT, DownloadClientId INTEGER, AppProfileId INTEGER)",
        "Applications": "(Id INTEGER PRIMARY KEY, Name TEXT)",
        "ApplicationIndexerMapping": "(Id INTEGER PRIMARY KEY, IndexerId INTEGER, AppId INTEGER, RemoteIndexerName TEXT)",
    }.items():
        con.execute(f"CREATE TABLE {name} {ddl}")
    for i, n in clients:
        con.execute("INSERT INTO DownloadClients (Id, Name) VALUES (?, ?)", (i, n))
    for i, n in profiles:
        con.execute("INSERT INTO AppSyncProfiles (Id, Name) VALUES (?, ?)", (i, n))
    for i, n, c, p in indexers:
        con.execute("INSERT INTO Indexers (Id, Name, DownloadClientId, AppProfileId) "
                    "VALUES (?, ?, ?, ?)", (i, n, c, p))
    for i, n in apps:
        con.execute("INSERT INTO Applications (Id, Name) VALUES (?, ?)", (i, n))
    for i, idx, app, name in mappings:
        con.execute("INSERT INTO ApplicationIndexerMapping (Id, IndexerId, AppId, RemoteIndexerName) "
                    "VALUES (?, ?, ?, ?)", (i, idx, app, name))
    con.commit()
    con.close()
    return f.name


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name} expected {want!r}, got {got!r}")
            failures += 1

    # Clean: client 0 sentinel, app profile 1 present, valid mapping.
    clean = make_db(
        [(5, "nzbdav")], [(1, "Default")],
        [(1, "NZBGeek", 0, 1), (2, "omgwtfnzbs", 5, 1)],
        [(1, "Radarr")], [(1, 2, 1, "NZBGeek")],
    )
    expect("clean DB: no orphans", mod.find_orphans(clean), [])

    # Dangling download client (client 9 missing) and app profile (99 missing).
    bad_client = make_db(
        [(5, "nzbdav")], [(1, "Default")],
        [(1, "NZBGeek", 9, 1)],  # client 9 deleted
        [], [],
    )
    got = mod.find_orphans(bad_client)
    expect("deleted download client IS flagged",
           any(g[0] == "download-client" and g[4] == 9 for g in got), True)

    bad_profile = make_db(
        [(5, "nzbdav")], [(1, "Default")],
        [(1, "NZBGeek", 0, 99)],  # app profile 99 deleted
        [], [],
    )
    got = mod.find_orphans(bad_profile)
    expect("deleted app sync profile IS flagged",
           any(g[0] == "app-sync-profile" and g[4] == 99 for g in got), True)

    # Mapping orphans: one row's IndexerId missing, one row's AppId missing.
    map_bad = make_db(
        [], [(1, "Default")],
        [(1, "NZBGeek", 0, 1)],
        [(1, "Radarr")],
        [(1, 99, 1, "Ghost"),    # indexer 99 deleted
         (2, 1, 99, "Orphan")],  # app 99 deleted
    )
    got = mod.find_orphans(map_bad)
    kinds = {g[0] for g in got}
    expect("mapping orphans IS flagged (both kinds)",
           {"mapping-indexer", "mapping-app"}.issubset(kinds), True)

    for p in (clean, bad_client, bad_profile, map_bad):
        os.unlink(p)

    if failures == 0:
        print("test_check_prowlarr_refs: all assertions passed")
        return 0
    print(f"test_check_prowlarr_refs: {failures} assertion(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
