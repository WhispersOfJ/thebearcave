#!/usr/bin/env python3
"""Focused regression tests for the scoped Sonarr search engine."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = load("search_missing_scoped_core", SCRIPTS / "search_missing_scoped_core.py")
checkpoint_mod = load(
    "search_missing_scoped_checkpoint", SCRIPTS / "search_missing_scoped_checkpoint.py"
)

failures = 0


def check(label, condition):
    global failures
    if condition:
        print(f"  [PASS] {label}")
    else:
        failures += 1
        print(f"  [FAIL] {label}")


def episode(series_id, season, number, episode_id=None):
    return {
        "id": episode_id or series_id * 1000 + season * 100 + number,
        "seriesId": series_id,
        "seasonNumber": season,
        "episodeNumber": number,
        "monitored": True,
        "hasFile": False,
        "lastSearchTime": None,
    }


class FakeSonarr:
    """Small API-shaped fake with controllable queue/history state."""

    def __init__(self, missing):
        self.missing = missing
        self.queue = []
        self.history = []
        self.posted = []
        self.command_polls = 0
        self.queue_reads = 0
        self.history_available = True
        self.next_command = 41
        self.late_queue = None
        self.parse_results = {}

    def fetch_missing(self, series_ids=None):
        if series_ids:
            return [record for record in self.missing
                    if record["seriesId"] in series_ids]
        return list(self.missing)

    def fetch_queue_records(self):
        self.queue_reads += 1
        if self.late_queue and self.queue_reads >= self.late_queue[0]:
            self.queue.extend(self.late_queue[1])
            self.late_queue = None
        return list(self.queue)

    @staticmethod
    def queue_key(record):
        download_id = record.get("downloadId")
        if download_id is not None:
            return f"download:{download_id}"
        return f"queue:{record.get('id')}"

    def fetch_queue_keys(self):
        return frozenset(self.queue_key(record) for record in self.queue)

    @staticmethod
    def grab_key(record):
        return (str(record.get("date") or ""), int(record.get("id") or 0))

    @staticmethod
    def is_grabbed(record):
        event_type = record.get("eventType")
        return event_type == 1 or str(event_type).casefold() == "grabbed"

    def fetch_grab_watermark(self):
        if not self.history_available:
            raise RuntimeError("history unavailable")
        return max((self.grab_key(record) for record in self.history),
                   default=("", 0))

    def fetch_grab_history(self, stop_at=None):
        if not self.history_available:
            raise RuntimeError("history unavailable")
        return list(self.history)

    def parse_title(self, title):
        return self.parse_results.get(
            title, {"series": None, "episodes": []}
        )

    def post_command(self, command):
        self.posted.append(command)
        command_id = self.next_command
        self.next_command += 1
        return {"id": command_id, "status": "queued"}

    def command_status(self, command_id):
        self.command_polls += 1
        return {
            "id": command_id, "status": "completed", "result": "successful"
        }


def config(path, *, apply=True, checkpoint=True, verify=False, batch=20,
           series=(1,), quiet=1):
    return mod.SearchConfig(
        series_ids=series, all_series=False, batch_size=batch, gap=0,
        quiet_window=quiet, checkpoint=checkpoint, verify=verify,
        apply=apply, timeout=5, checkpoint_path=str(path),
    )


def run_checkpoint_tests():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "search.json"
        client = FakeSonarr([
            episode(1, 1, 1), episode(1, 2, 1),
        ])
        first = mod.SearchEngine(client, config(path, batch=1)).run()
        data = json.loads(path.read_text())
        groups = [group for batch in data["batches"] for group in batch["groups"]]
        check("checkpoint is created before applied work completes",
              first.summary.startswith("checkpoint after") and len(client.posted) == 1)
        check("checkpoint records scope, group identity, and command lifecycle",
              data["config"]["scope"] == {"mode": "series", "seriesIds": [1]}
              and groups[0]["identity"]["episodeIds"] == [1101]
              and groups[0]["command"]["id"] == 41
              and groups[0]["command"]["status"] == "completed"
              and groups[0]["command"]["result"] == "successful"
              and groups[0]["verification"]["status"] == "not_requested")

        verified_path = Path(directory) / "verified.json"
        verified_client = FakeSonarr([episode(1, 1, 1)])
        verified_config = config(
            verified_path, batch=1, verify=True, quiet=1
        )
        verified_first = mod.SearchEngine(
            verified_client, verified_config
        ).run()
        verified_posts = len(verified_client.posted)
        verified_resume = mod.SearchEngine(
            verified_client, verified_config
        ).run(resume=True)
        verified_data = json.loads(verified_path.read_text())
        check("completed and verified group is skipped on resume",
              verified_first.exit_code == 0
              and verified_data["batches"][0]["groups"][0]["verification"]["status"] == "ok"
              and verified_resume.exit_code == 0
              and verified_resume.reports[0].skipped_groups == 1
              and len(verified_client.posted) == verified_posts)

        resumed = mod.SearchEngine(client, config(path, batch=1)).run(resume=True)
        check("explicit resume skips completed verified group and runs next group",
              resumed.summary == "complete" and len(client.posted) == 2
              and client.posted[1]["episodeIds"] == [1201])
        check("resume never reposts the already completed group",
              client.posted.count({"name": "EpisodeSearch", "episodeIds": [1101]}) == 1)

        interrupted = json.loads(path.read_text())
        interrupted_group = interrupted["batches"][1]["groups"][0]
        interrupted_group["status"] = "running"
        interrupted_group["verification"] = {
            "status": "pending", "historyAvailable": None,
            "historyCount": 0, "queueCount": 0,
        }
        interrupted["batches"][1]["groups"][0] = interrupted_group
        checkpoint_mod.CheckpointStore(path).write(interrupted)
        before_resume_posts = len(client.posted)
        resumed_interrupted = mod.SearchEngine(
            client, config(path, batch=1)
        ).run(resume=True)
        check("interrupted known-command group resumes by polling, not reposting",
              resumed_interrupted.exit_code == 0
              and len(client.posted) == before_resume_posts
              and client.command_polls >= 2)

        mismatch = mod.SearchEngine(client, config(path, batch=2, series=(2,))).run(
            resume=True
        )
        check("resume rejects scope/config mismatch before any POST",
              mismatch.exit_code == 1
              and "does not match" in mismatch.summary
              and len(client.posted) == 2)

        path.write_text("{broken", encoding="utf-8")
        corrupt = mod.SearchEngine(client, config(path)).run(resume=True)
        check("corrupt checkpoint fails closed before any POST",
              corrupt.exit_code == 1 and "unreadable" in corrupt.summary
              and len(client.posted) == 2)

        path.write_text(json.dumps({"version": 1}), encoding="utf-8")
        incomplete = mod.SearchEngine(client, config(path)).run(resume=True)
        check("incomplete checkpoint fails closed before any POST",
              incomplete.exit_code == 1 and len(client.posted) == 2)

        ambiguous = json.loads(path.read_text())
        ambiguous = {
            "version": 1,
            "config": mod.SearchConfig(
                series_ids=(1,), all_series=False, batch_size=1, gap=0,
                quiet_window=1, checkpoint=True, verify=False, apply=True,
                timeout=5, checkpoint_path=str(path),
            ).checkpoint_config(),
            "batches": [{
                "number": 1,
                "groups": [{
                    "identity": {"seriesId": 1, "seasonNumber": 1, "episodeIds": [1101]},
                    "status": "running",
                    "command": {"id": None, "status": None, "result": None},
                    "snapshot": {"watermark": ["", 0], "beforeIds": []},
                    "verification": {"status": "pending", "historyAvailable": None,
                                     "historyCount": 0, "queueCount": 0},
                }],
            }],
        }
        checkpoint_mod.CheckpointStore(path).write(ambiguous)
        ambiguous_result = mod.SearchEngine(
            client, config(path, batch=1)
        ).run(resume=True)
        check("ambiguous running checkpoint refuses to POST",
              ambiguous_result.exit_code == 1
              and "ambiguous" in ambiguous_result.summary
              and len(client.posted) == 2)

        dry_path = Path(directory) / "dry.json"
        dry_client = FakeSonarr([episode(1, 1, 1)])
        dry = mod.SearchEngine(
            dry_client, config(dry_path, apply=False, checkpoint=True)
        ).run()
        check("dry-run posts nothing and writes no checkpoint",
              dry.exit_code == 0 and not dry_client.posted and not dry_path.exists())

        no_checkpoint = mod.SearchEngine(
            FakeSonarr([episode(1, 1, 1)]),
            config(Path(directory) / "disabled.json", checkpoint=False),
        ).run()
        check("checkpoint-disabled apply remains a single-pass run",
              no_checkpoint.exit_code == 0)

        bypass_path = Path(directory) / "bypass.json"
        bypass_client = FakeSonarr([episode(1, 1, 1)])
        bypass_config = config(bypass_path, batch=1)
        first_bypass = mod.SearchEngine(bypass_client, bypass_config).run()
        bypass_posts = len(bypass_client.posted)
        bypass_config = config(bypass_path, batch=1, checkpoint=False)
        bypass = mod.SearchEngine(bypass_client, bypass_config).run()
        check("--yes refuses to bypass an existing checkpoint",
              first_bypass.exit_code == 0
              and bypass.exit_code == 1
              and "checkpoint exists" in bypass.summary
              and len(bypass_client.posted) == bypass_posts)

        fallback_client = FakeSonarr([episode(1, 1, 1)])
        fallback_client.history_available = False
        fallback_client.queue = [{
            "downloadId": "fallback", "seriesId": 1,
            "episodeId": 1101, "title": "fallback",
        }]
        fallback_client.parse_results["fallback"] = {
            "series": {"id": 1, "title": "Show"},
            "episodes": [{"id": 1101}],
        }
        fallback = mod.SearchEngine(
            fallback_client,
            config(Path(directory) / "fallback.json", verify=True,
                   checkpoint=False, apply=False),
        ).run()
        check("history-unavailable verification falls back to queue-only",
              fallback.exit_code == 0
              and fallback.reports[0].verification.history_available is False)

        fallback_verifier = mod.Verifier(fallback_client, {1}, {1101})
        fallback_report = fallback_verifier.verify_once(
            mod.VerificationSnapshot(("", 0), frozenset())
        )
        check("queue-only fallback still inspects new queue items",
              fallback_report.history_available is False
              and fallback_report.queue_count == 1
              and not fallback_report.offenders)


def run_verifier_tests():
    client = FakeSonarr([])
    client.history = [{
        "id": 10, "date": "2026-09-01T00:00:00Z", "eventType": 1,
        "seriesId": 1, "episodeId": 999, "commandId": 4,
        "sourceTitle": "unrelated", "downloadId": "old",
    }]
    client.parse_results["wrong current"] = {
        "series": {"id": 99, "title": "Wrong Show"}, "episodes": [{"id": 1}]
    }
    client.parse_results["right current"] = {
        "series": {"id": 1, "title": "Right Show"}, "episodes": [{"id": 101}]
    }
    client.history.extend([
        {
            "id": 11, "date": "2026-09-02T00:00:00Z", "eventType": "grabbed",
            "seriesId": 1, "episodeId": 101, "commandId": 7,
            "sourceTitle": "wrong current", "downloadId": "current-wrong",
        },
        {
            "id": 12, "date": "2026-09-02T00:00:01Z", "eventType": "grabbed",
            "seriesId": 1, "episodeId": 999, "commandId": 88,
            "sourceTitle": "unrelated", "downloadId": "unrelated-new",
        },
    ])
    verifier = mod.Verifier(client, {1}, {101})
    snapshot = mod.VerificationSnapshot(("2026-09-01T00:00:00Z", 10), frozenset())
    report = verifier.verify_once(snapshot, command_id=7)
    check("history attribution catches current grab and ignores unrelated grab",
          report.history_available and report.history_count == 1
          and len(report.offenders) == 1
          and report.offenders[0]["downloadId"] == "current-wrong")

    late_client = FakeSonarr([])
    late_client.parse_results["late"] = {
        "series": None, "episodes": []
    }
    late_client.late_queue = (2, [{
        "downloadId": "late", "seriesId": None, "title": "late"
    }])
    late_verifier = mod.Verifier(late_client, {1}, {101})
    late_snapshot = mod.VerificationSnapshot(("", 0), frozenset())
    original_monotonic = mod.time.monotonic
    original_sleep = mod.time.sleep
    ticks = iter((0, 0, 2))
    mod.time.monotonic = lambda: next(ticks)
    mod.time.sleep = lambda _seconds: None
    try:
        late = late_verifier.verify_until_quiet(late_snapshot, 1, command_id=7)
    finally:
        mod.time.monotonic = original_monotonic
        mod.time.sleep = original_sleep
    check("quiet-window verification catches a late unknown-series queue item",
          len(late.offenders) == 1 and late.offenders[0]["downloadId"] == "late")

    late_history = FakeSonarr([])
    late_history.parse_results["late history"] = {
        "series": None, "episodes": []
    }
    late_history.history = []
    late_history.history_late = (2, {
        "id": 1, "date": "2026-09-02T00:00:00Z", "eventType": "grabbed",
        "seriesId": 1, "episodeId": 101, "sourceTitle": "late history",
        "downloadId": "late-history",
    })
    original_history = late_history.fetch_grab_history
    history_reads = {"n": 0}

    def fetch_late_history(stop_at=None):
        history_reads["n"] += 1
        if (late_history.history_late
                and history_reads["n"] >= late_history.history_late[0]):
            late_history.history.append(late_history.history_late[1])
            late_history.history_late = None
        return original_history(stop_at)

    late_history.fetch_grab_history = fetch_late_history
    late_history_verifier = mod.Verifier(late_history, {1}, {101})
    late_history_snapshot = mod.VerificationSnapshot(("", 0), frozenset())
    original_monotonic = mod.time.monotonic
    original_sleep = mod.time.sleep
    ticks = iter((0, 0, 2))
    mod.time.monotonic = lambda: next(ticks)
    mod.time.sleep = lambda _seconds: None
    try:
        late_history_report = late_history_verifier.verify_until_quiet(
            late_history_snapshot, 1, command_id=7
        )
    finally:
        mod.time.monotonic = original_monotonic
        mod.time.sleep = original_sleep
    check("quiet-window verification catches a late history-only grab",
          len(late_history_report.offenders) == 1
          and late_history_report.offenders[0]["downloadId"] == "late-history")

    unknown = FakeSonarr([])
    unknown.queue = [{"downloadId": "unknown", "seriesId": None, "title": "mystery"}]
    unknown_verifier = mod.Verifier(unknown, {1}, {101})
    unknown_report = unknown_verifier.verify_once(
        mod.VerificationSnapshot(("", 0), frozenset())
    )
    check("unknown-series queue items are always verification suspects",
          len(unknown_report.offenders) == 1)


def run_planning_tests():
    missing = [episode(1, 1, 2), episode(1, 1, 1), episode(2, 1, 1)]
    groups = mod.build_groups(missing)
    check("planning groups by season and sorts episodes",
          [(group["seriesId"], group["seasonNumber"]) for group in groups]
          == [(1, 1), (2, 1)]
          and [item["episodeNumber"] for item in groups[0]["episodes"]] == [1, 2])
    check("batch size never splits a season",
          len(mod.split_batches(groups, 1)) == 2)


def run_fast_planning_tests():
    """The --all fetch reproduces /wanted/missing semantics exactly."""
    from datetime import datetime, timezone
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    base = {
        "monitored": True, "hasFile": False,
        "airDateUtc": "2026-09-01T00:00:00Z",
    }
    check("aired monitored missing episode is planned",
          mod._is_planned_missing(dict(base), now))
    check("episode with a file is not planned",
          not mod._is_planned_missing(dict(base, hasFile=True), now))
    check("unmonitored episode is not planned",
          not mod._is_planned_missing(dict(base, monitored=False), now))
    check("future episode is not planned (wanted/missing parity)",
          not mod._is_planned_missing(
              dict(base, airDateUtc="2026-09-04T00:00:00Z"), now))
    check("undated episode is not planned (wanted/missing parity)",
          not mod._is_planned_missing(dict(base, airDateUtc=None), now))
    check("naive air date compares as UTC",
          mod._is_planned_missing(dict(base, airDateUtc="2026-09-01T00:00:00"),
                                  now))
    check("garbage air date is not planned",
          not mod._is_planned_missing(dict(base, airDateUtc="not-a-date"), now))


def main():
    run_planning_tests()
    run_fast_planning_tests()
    run_checkpoint_tests()
    run_verifier_tests()
    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
