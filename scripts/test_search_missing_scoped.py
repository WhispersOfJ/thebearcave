#!/usr/bin/env python3
"""Regression test for scripts/search_missing_scoped.py.

Verifies the pure planning logic and the guarded sweep loop:

  * wanted/missing records are grouped by (series, season) and ordered
    by lastSearchTime (never-searched first) so checkpoints resume in a
    deterministic order
  * batches cap episodes at --batch while never splitting a season group
  * multi-episode seasons issue SeasonSearch, single episodes
    EpisodeSearch (mirroring Sonarr's own search flow)
  * dry-run issues zero POST /command calls and still runs the --verify
    pre-flight read-only
  * --verify passes when new queue items parse to their own series,
    aborts with rc 2 and the offenders listed on NO_MATCH or a
    different-series parse, and ignores pre-existing queue items
  * checkpoints stop after the first batch; --yes runs every batch

Runs against importable pure-Python logic (no live Sonarr needed), so it
works on the CI runner. Run by .github/workflows/validate.yml and locally
via `python3 scripts/test_search_missing_scoped.py`. Exits 0 when every
assertion holds, 1 otherwise.
"""

import importlib.util
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "search_missing_scoped.py"

# Import the tool as a module (it has no package-relative imports).
spec = importlib.util.spec_from_file_location("search_missing_scoped", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = 0


def check(label, cond):
    global failures
    if cond:
        print(f"  [PASS] {label}")
    else:
        failures += 1
        print(f"  [FAIL] {label}")


def ep(sid, sn, num, last=None, eid=None):
    return {"id": eid or (sid * 1000 + sn * 100 + num), "seriesId": sid,
            "seasonNumber": sn, "episodeNumber": num,
            "title": f"Show.S{sn:02d}E{num:02d}", "monitored": True,
            "lastSearchTime": last}


def main():
    # --- grouping + ordering (checkpoint/resume determinism) ---
    missing = [
        ep(1, 1, 1, last="2026-09-01T10:00:00Z"),
        ep(1, 1, 2, last="2026-09-01T10:00:00Z"),
        ep(1, 2, 1, last="2026-09-01T08:00:00Z"),
        ep(2, 1, 1, last=None),
        ep(1, 2, 2, last="2026-09-01T09:00:00Z"),
    ]
    groups = mod.build_groups(missing)
    check("groups by (series, season), oldest-search first, never-searched first",
          [(g["seriesId"], g["seasonNumber"]) for g in groups] ==
          [(2, 1), (1, 2), (1, 1)])
    check("group episodes are sorted by episode number",
          [e["episodeNumber"] for e in groups[2]["episodes"]] == [1, 2])
    check("never-searched group reports last_search None",
          groups[0]["last_search"] is None)

    # --- batch boundaries ---
    small = mod.build_groups([ep(1, s, n, last=None)
                              for s in (1, 2, 3, 4, 5) for n in (1, 2, 3)])
    sizes = [sum(len(g["episodes"]) for g in b) for b in mod.split_batches(small, 10)]
    check("batches cap episodes at --batch", sizes == [9, 6])
    big = mod.build_groups([ep(1, 1, n, last=None) for n in range(1, 26)])
    big_batches = mod.split_batches(big, 20)
    check("oversized season group is never split",
          len(big_batches) == 1 and len(big_batches[0][0]["episodes"]) == 25)

    # --- command shape mirrors Sonarr ---
    cmds = mod.search_commands_for(
        mod.build_groups([ep(1, 1, 1, last=None), ep(1, 1, 2, last=None),
                          ep(2, 2, 1, last=None)]))
    check("multi-episode season issues SeasonSearch",
          {"name": "SeasonSearch", "seriesId": 1, "seasonNumber": 1} in cmds)
    check("single-episode season issues EpisodeSearch",
          {"name": "EpisodeSearch", "episodeIds": [2201]} in cmds)

    # --- stubbed sweep loop ---
    missing_records = []
    queue_records = []
    parse_map = {}
    posted = []
    post_n = {"n": 0}

    def stub(base_url, api_key, path, method="GET", body=None, timeout=None):
        if path.startswith("/wanted/missing"):
            return {"totalRecords": len(missing_records), "records": missing_records}
        if path.startswith("/episode"):
            sid = int(path.split("seriesId=", 1)[1].split("&", 1)[0])
            return [r for r in missing_records if r["seriesId"] == sid]
        if path.startswith("/queue"):
            return {"totalRecords": len(queue_records), "records": queue_records}
        if path.startswith("/parse"):
            title = urllib.parse.unquote(path.split("title=", 1)[1])
            return parse_map.get(title, {"series": None, "episodes": []})
        if path.startswith("/command") and method == "POST":
            posted.append(body)
            # Simulate the grab appearing in the queue after each search.
            post_n["n"] += 1
            queue_records.append({"id": 900 + post_n["n"],
                                  "downloadId": f"dl-new-{post_n['n']}",
                                  "seriesId": 1, "title": "Show.S01E01.WEB"})
            return {"id": 1}
        raise AssertionError(f"unexpected path: {path}")

    orig_request = mod._request
    mod._request = stub
    try:
        # Dry-run: nothing posted, verify pre-flight still runs read-only.
        missing_records = [ep(1, 1, 1, last=None), ep(1, 1, 2, last=None),
                           ep(1, 2, 1, last=None)]
        queue_records = []
        parse_map = {}
        posted.clear()
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=True, verify=True, apply=False)
        check("dry-run posts no search commands", posted == [] and code == 0)

        # Verify passes when the new item parses to its own series.
        missing_records = [ep(1, 1, 1, last=None)]  # one episode -> one POST
        parse_map = {"Show.S01E01.WEB": {"series": {"id": 1, "title": "Show"},
                                         "episodes": [{"id": 101}]}}
        posted.clear()
        queue_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("verify passes when new item parses to its own series",
              code == 0 and "complete" in summary)
        check("verify pass posts the episode search command",
              {"name": "EpisodeSearch", "episodeIds": [1101]} in posted)

        # Verify aborts on NO_MATCH (the ARK-into-TPB-Animated class).
        parse_map = {}
        posted.clear()
        queue_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("verify aborts with rc 2 on NO_MATCH grab",
              code == 2 and "verify-abort" in summary)

        # Verify aborts on a different-series parse.
        parse_map = {"Show.S01E01.WEB": {"series": {"id": 99, "title": "Other Show"},
                                         "episodes": [{"id": 1}]}}
        posted.clear()
        queue_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("verify aborts on a different-series parse",
              code == 2 and "verify-abort" in summary)

        # Verify ignores items that existed before the batch (parse would
        # fail for the old item, but it is not in the new-item set).
        parse_map = {"Show.S01E01.WEB": {"series": {"id": 1, "title": "Show"},
                                         "episodes": [{"id": 101}]}}
        queue_records = [{"id": 5, "downloadId": "dl-old", "seriesId": 1,
                          "title": "Old.Show.S01E01"}]
        posted.clear()
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("verify ignores pre-existing queue items",
              code == 0 and "complete" in summary)

        # Checkpoint stops after batch 1; --yes runs every batch.
        missing_records = [ep(1, s, n, last=None) for s in (1, 2)
                           for n in (1, 2, 3)]
        parse_map = {}
        posted.clear()
        queue_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=5, gap=0,
                                checkpoint=True, verify=False, apply=True)
        check("checkpoint stops after the first batch",
              code == 0 and "checkpoint after batch 1" in summary
              and len(posted) == 1)
        posted.clear()
        queue_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=5, gap=0,
                                checkpoint=False, verify=False, apply=True)
        check("--yes runs every batch in one pass",
              code == 0 and "complete" in summary and len(posted) == 2)

        # fetch_missing honors the --series filter.
        missing_records = [ep(1, 1, 1, last=None), ep(2, 1, 1, last=None)]
        got = mod.fetch_missing("http://x/api/v3", "k", series_ids=[1])
        check("fetch_missing filters to the requested series",
              [g["seriesId"] for g in got] == [1])
    finally:
        mod._request = orig_request

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
