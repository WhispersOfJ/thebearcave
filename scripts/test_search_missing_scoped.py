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
  * --verify aborts on a grab that fails before it is ever queue-visible
    (caught via the grabbed-history watermark), treats unknown-series
    queue items as suspects, ignores pre-existing grabs via the watermark,
    and falls back to the queue diff alone when the history API is
    unavailable
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
    history_records = []
    queue_paths = []
    command_paths = []
    history_paths = []
    parse_map = {}
    posted = []
    post_n = {"n": 0}
    command_polls = {}
    sim = {"append_queue": True, "append_history": True,
           "new_series_id": 1, "history_fails": False,
           "command_fails": False, "bulk_history": 0}

    def stub(base_url, api_key, path, method="GET", body=None, timeout=None):
        if path.startswith("/wanted/missing"):
            return {"totalRecords": len(missing_records), "records": missing_records}
        if path.startswith("/episode"):
            sid = int(path.split("seriesId=", 1)[1].split("&", 1)[0])
            return [r for r in missing_records if r["seriesId"] == sid]
        if path.startswith("/queue"):
            queue_paths.append(path)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
            page = int(query.get("page", [1])[0])
            size = int(query.get("pageSize", [100])[0])
            records = queue_records[(page - 1) * size:page * size]
            return {"totalRecords": len(queue_records), "records": records}
        if path.startswith("/history"):
            history_paths.append(path)
            if sim["history_fails"]:
                raise RuntimeError("history unavailable")
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
            page = int(query.get("page", [1])[0])
            size = int(query.get("pageSize", [100])[0])
            records = sorted(history_records,
                             key=lambda r: r["id"], reverse=True)
            records = records[(page - 1) * size:page * size]
            return {"totalRecords": len(history_records), "records": records}
        if path.startswith("/parse"):
            title = urllib.parse.unquote(path.split("title=", 1)[1])
            return parse_map.get(title, {"series": None, "episodes": []})
        if path.startswith("/command/") and method == "GET":
            command_paths.append(path)
            command_id = path.rsplit("/", 1)[1]
            polls = command_polls.setdefault(command_id, 0)
            command_polls[command_id] += 1
            return {"id": int(command_id),
                    "status": "completed" if sim["command_fails"] else
                    ("started" if polls == 0 else "completed"),
                    "result": "failed" if sim["command_fails"] else
                    ("unknown" if polls == 0 else "successful")}
        if path.startswith("/command") and method == "POST":
            posted.append(body)
            # Simulate the grab appearing after each search: in the queue
            # and/or in the grabbed-history watermark (or neither, for the
            # instant-failure case).
            post_n["n"] += 1
            if sim["append_queue"]:
                queue_records.append({"id": 900 + post_n["n"],
                                      "downloadId": f"dl-new-{post_n['n']}",
                                      "seriesId": sim["new_series_id"],
                                      "title": "Show.S01E01.WEB"})
            if sim["append_history"]:
                for extra in range(max(1, sim["bulk_history"])):
                    history_records.append({"id": 10000 + post_n["n"] * 1000 + extra,
                                            "eventType": 1,
                                            "seriesId": sim["new_series_id"],
                                            "episodeId": 101,
                                            "downloadId": f"dl-new-{post_n['n']}-{extra}",
                                            "sourceTitle": "Show.S01E01.WEB"})
            command_polls["1"] = 0
            return {"id": 1, "status": "queued"}
        raise AssertionError(f"unexpected path: {path}")

    orig_request = mod._request
    orig_sleep = mod.time.sleep
    mod.time.sleep = lambda _seconds: None
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
        check("apply waits for the asynchronous command to finish",
              "/command/1" in command_paths)

        # A valid parse for a different series than this batch is still
        # unsafe and must abort.
        sim["new_series_id"] = 99
        parse_map = {"Show.S01E01.WEB": {"series": {"id": 99, "title": "Other Show"},
                                         "episodes": [{"id": 101}]}}
        posted.clear()
        queue_records = []
        history_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("verify rejects a valid parse outside the searched series",
              code == 2 and "verify-abort" in summary)
        sim["new_series_id"] = 1

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

        # A grab that fails before it is ever queue-visible must still
        # abort: it exists in grabbed history (the watermark) even though
        # the queue never sees it (the wire-to-wire 430-failure case).
        missing_records = [ep(1, 1, 1, last=None)]
        parse_map = {}
        queue_records = []
        history_records = []
        posted.clear()
        sim["append_queue"] = False   # download dies before queue insertion
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("verify aborts on a grab that never reaches the queue",
              code == 2 and "verify-abort" in summary)
        sim["append_queue"] = True

        # Unknown-series queue items are suspects, and the queue fetch must
        # include unknown-series items so they are not a second blind spot.
        queue_paths.clear()
        parse_map = {}
        queue_records = []
        history_records = []
        posted.clear()
        sim["new_series_id"] = None
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("unknown-series queue item is a verify offender",
              code == 2 and "verify-abort" in summary)
        check("queue fetch includes unknown-series items",
              len(queue_paths) > 0 and all(
                  "includeUnknownSeriesItems=true" in p for p in queue_paths))
        sim["new_series_id"] = 1

        # Pre-existing grabs (id <= watermark) are ignored even when their
        # titles would parse NO_MATCH.
        missing_records = [ep(1, 1, 1, last=None)]
        parse_map = {"Show.S01E01.WEB": {"series": {"id": 1, "title": "Show"},
                                         "episodes": [{"id": 101}]}}
        history_records = [{"id": 5000, "eventType": 1, "seriesId": 1,
                            "downloadId": "dl-old-grab",
                            "sourceTitle": "Old.Grab.NO.MATCH"}]
        queue_records = []
        posted.clear()
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("pre-existing grabs are ignored via the watermark",
              code == 0 and "complete" in summary)

        # History API unavailable: the queue diff still runs (fallback).
        parse_map = {"Show.S01E01.WEB": {"series": {"id": 1, "title": "Show"},
                                         "episodes": [{"id": 101}]}}
        queue_records = []
        history_records = []
        posted.clear()
        sim["history_fails"] = True
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("queue-diff verify still works when history is unavailable",
              code == 0 and "complete" in summary)
        sim["history_fails"] = False

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

        # A failed asynchronous search may have created partial grabs; verify
        # still runs and reports a wrong-show result before the command error.
        sim["command_fails"] = True
        sim["append_queue"] = True
        parse_map = {}
        posted.clear()
        queue_records = []
        history_records = []
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=True, apply=True)
        check("failed async search still verifies partial grabs", code == 2
              and "verify-abort" in summary)

        # Without verification, the same terminal command failure is returned
        # directly and no checkpoint is reported.
        sim["append_queue"] = False
        sim["append_history"] = False
        posted.clear()
        code, summary = mod.run("http://x/api/v3", "k", series_ids=[1],
                                all_series=False, batch_size=20, gap=0,
                                checkpoint=False, verify=False, apply=True)
        check("failed async search stops without verification", code == 1
              and "did not complete" in summary)
        sim["append_queue"] = True
        sim["append_history"] = True
        sim["command_fails"] = False

        # More than one page of post-watermark grabs is fully inspected.
        command_paths.clear()
        history_paths.clear()
        sim["bulk_history"] = 101
        long_title = "Show." + ("VeryLong.Release.Name." * 12) + "S01E01.WEB"
        parse_map[long_title] = {"series": {"id": 1, "title": "Show"},
                                 "episodes": [{"id": 101}]}
        queue_records = [{"id": n, "downloadId": f"dl-old-{n}",
                          "seriesId": 1, "title": "Old.Show.S01E01"}
                         for n in range(1, 101)]
        queue_records.append({"id": 101, "downloadId": "dl-long",
                              "seriesId": 1, "title": long_title})
        check("paged queue verification keeps the full title",
              mod.verify_new_items("http://x/api/v3", "k",
                                   {f"dl-old-{n}" for n in range(1, 101)},
                                   {1}) == (True, []))
        history_records = [{"id": n, "date": "2026-09-01T00:00:00Z",
                            "eventType": "grabbed", "seriesId": 1,
                            "sourceTitle": "Old.Show.S01E01"}
                           for n in range(100, 0, -1)]
        parse_map["Old.Show.S01E01"] = {"series": {"id": 1, "title": "Show"},
                                         "episodes": [{"id": 101}]}
        watermark = mod.fetch_grab_watermark("http://x/api/v3", "k")
        history_records.extend({"id": 1000 + n, "date": "2026-09-02T00:00:00Z",
                                "eventType": "grabbed", "seriesId": 1,
                                "sourceTitle": "Old.Show.S01E01"}
                               for n in range(101))
        available, offenders, count = mod.new_grab_offenders(
            "http://x/api/v3", "k", watermark, {1})
        check("history verification paginates all new grabs",
              available and not offenders and count == 101
              and any("page=2" in p for p in history_paths))
        sim["bulk_history"] = 0

        # fetch_missing honors the --series filter, and invalid run bounds
        # fail before any API request or search command.
        missing_records = [ep(1, 1, 1, last=None), ep(2, 1, 1, last=None)]
        got = mod.fetch_missing("http://x/api/v3", "k", series_ids=[1])
        check("fetch_missing filters to the requested series",
              [g["seriesId"] for g in got] == [1])
        check("zero batch size is rejected", mod.run(
            "http://x/api/v3", "k", [1], False, 0, 0, False, False, False)[0] == 1)
        check("negative gap is rejected", mod.run(
            "http://x/api/v3", "k", [1], False, 1, -1, False, False, False)[0] == 1)
    finally:
        mod._request = orig_request
        mod.time.sleep = orig_sleep

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
