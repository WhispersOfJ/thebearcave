"""Engine for the scoped Sonarr missing-search wrapper."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request

from search_missing_scoped_checkpoint import CheckpointError, CheckpointStore

DEFAULT_URL = "http://localhost:8989/api/v3"
DEFAULT_TIMEOUT = 60
DEFAULT_BATCH = 20
DEFAULT_GAP = 60
DEFAULT_QUIET_WINDOW = 10
QUEUE_PAGE_SIZE = 100
HISTORY_PAGE_SIZE = 100
COMMAND_POLL_INTERVAL = 1
COMMAND_WAIT_TIMEOUT = 300
VERIFY_POLL_INTERVAL = 1


def _default_checkpoint_path():
    state_home = os.environ.get("XDG_STATE_HOME")
    root = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return str(root / "thebearcave" / "search-missing-scoped.json")


DEFAULT_CHECKPOINT_PATH = _default_checkpoint_path()


def _as_int(value):
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _total_records(value):
    parsed = _as_int(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _parse_air_date(value):
    """Parse an ISO air date to timezone-aware UTC, or None when absent."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_planned_missing(record, now):
    """Reproduce /wanted/missing semantics for one episode record.

    A record is searchable when it is monitored, has no file yet, and has
    already aired. Undated and future episodes are excluded by the wanted
    endpoint and would only waste grabs, so they are excluded here too.
    """
    if record.get("monitored", True) is False or record.get("hasFile"):
        return False
    air_date = _parse_air_date(record.get("airDateUtc"))
    return air_date is not None and air_date <= now


@dataclass(frozen=True)
class SearchConfig:
    """Validated execution settings owned by the engine."""

    series_ids: tuple[int, ...] | None
    all_series: bool
    batch_size: int = DEFAULT_BATCH
    gap: int = DEFAULT_GAP
    quiet_window: int = DEFAULT_QUIET_WINDOW
    checkpoint: bool = True
    verify: bool = False
    apply: bool = False
    timeout: int = DEFAULT_TIMEOUT
    checkpoint_path: str = ""
    base_url: str = DEFAULT_URL

    def validate(self):
        if self.batch_size < 1:
            return "batch must be greater than zero"
        if self.gap < 0:
            return "gap cannot be negative"
        if self.quiet_window < 1:
            return "quiet window must be greater than zero"
        if self.timeout < 1:
            return "timeout must be greater than zero"
        if self.all_series and self.series_ids:
            return "--all cannot be combined with series IDs"
        if not self.all_series and not self.series_ids:
            return "at least one series or --all is required"
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            return "Sonarr URL is required"
        if self.apply and self.checkpoint and not self.checkpoint_path:
            return "checkpoint path is required for applied runs"
        return None

    def checkpoint_config(self):
        if self.all_series:
            scope = {"mode": "all", "seriesIds": None}
        else:
            scope = {
                "mode": "series",
                "seriesIds": sorted(set(self.series_ids or ())),
            }
        return {
            "scope": scope,
            "url": self.base_url.rstrip("/"),
            "batchSize": self.batch_size,
            "gap": self.gap,
            "quietWindow": self.quiet_window,
            "checkpoint": self.checkpoint,
            "verify": self.verify,
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class VerificationSnapshot:
    """Batch-start observations used to identify new queue/history records."""

    watermark: tuple[str, int] | None
    before_ids: frozenset[str]

    def as_checkpoint(self):
        return {
            "watermark": list(self.watermark) if self.watermark is not None else None,
            "beforeIds": sorted(self.before_ids),
        }

    @classmethod
    def from_checkpoint(cls, data):
        watermark = data["watermark"]
        return cls(
            tuple(watermark) if watermark is not None else None,
            frozenset(data["beforeIds"]),
        )


@dataclass(frozen=True)
class VerificationReport:
    history_available: bool
    history_count: int
    queue_count: int
    observations: int = 0
    offenders: tuple[dict, ...] = ()


@dataclass
class BatchReport:
    number: int
    total: int
    episodes: int
    commands: tuple[dict, ...]
    groups: tuple[dict, ...]
    dry_run: bool
    command_failed: bool = False
    verification: VerificationReport | None = None
    skipped_groups: int = 0


@dataclass
class RunResult:
    exit_code: int
    summary: str
    missing_count: int = 0
    group_count: int = 0
    batch_count: int = 0
    reports: list[BatchReport] = field(default_factory=list)
    offenders: tuple[dict, ...] = ()

    def __iter__(self):
        """Retain the prior ``code, summary = run(...)`` interface."""
        yield self.exit_code
        yield self.summary


class SonarrClient:
    """Own Sonarr transport and API response shaping."""

    def __init__(self, base_url, api_key, timeout=DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, path, method="GET", body=None):
        return _request(self.base_url, self.api_key, path, method, body,
                        self.timeout)

    def fetch_missing(self, series_ids=None):
        records = []
        if series_ids:
            for series_id in series_ids:
                response = self.request(f"/episode?seriesId={series_id}")
                if not isinstance(response, list):
                    raise RuntimeError(
                        f"/episode returned an unexpected shape for series {series_id}"
                    )
                now = datetime.now(timezone.utc)
                records.extend(
                    record for record in response
                    if _is_planned_missing(record, now)
                )
            return records

        # /wanted/missing paginates with SQLite OFFSET scans: every page
        # re-scans the full wanted set, and deep pages here measure 20-33s
        # (~75 minutes to plan a 50k-episode library). Enumerate the series
        # with missing episodes from statistics instead, then fetch each
        # series' episodes through the fast indexed endpoint. The monitored /
        # no-file / aired filter reproduces the wanted endpoint exactly
        # (verified: 50,876 records on the live library in ~7s).
        series = self.request("/series?includeStatistics=true")
        if not isinstance(series, list):
            raise RuntimeError("/series returned an unexpected shape")
        now = datetime.now(timezone.utc)
        for item in series:
            statistics = item.get("statistics") or {}
            if (_as_int(statistics.get("episodeCount")) or 0) <= (
                    _as_int(statistics.get("episodeFileCount")) or 0):
                continue
            series_id = item.get("id")
            response = self.request(f"/episode?seriesId={series_id}")
            if not isinstance(response, list):
                raise RuntimeError(
                    f"/episode returned an unexpected shape for series {series_id}"
                )
            records.extend(
                record for record in response
                if _is_planned_missing(record, now)
            )
        return records

    def _fetch_pages(self, endpoint, page_size):
        records = []
        page = 1
        while True:
            separator = "&" if "?" in endpoint else "?"
            response = self.request(
                f"{endpoint}{separator}page={page}&pageSize={page_size}"
            )
            if not isinstance(response, dict):
                raise RuntimeError(f"{endpoint} returned an unexpected shape")
            page_records = response.get("records") or []
            records.extend(page_records)
            total = _total_records(response.get("totalRecords"))
            if not page_records or (
                    total is not None and len(records) >= total):
                return records
            page += 1

    @staticmethod
    def queue_key(record):
        download_id = record.get("downloadId")
        if download_id is not None and str(download_id):
            return f"download:{download_id}"
        row_id = record.get("id")
        if row_id is not None:
            return f"queue:{row_id}"
        fallback = {
            "seriesId": record.get("seriesId"),
            "episodeId": record.get("episodeId"),
            "title": record.get("title"),
            "added": record.get("added"),
        }
        return "content:" + json.dumps(fallback, sort_keys=True, separators=(",", ":"))

    def fetch_queue_records(self):
        return self._fetch_pages(
            "/queue?includeUnknownSeriesItems=true", QUEUE_PAGE_SIZE
        )

    def fetch_queue_keys(self):
        return frozenset(self.queue_key(record)
                         for record in self.fetch_queue_records())

    @staticmethod
    def grab_key(record):
        date = str(record.get("date") or "")
        identifier = _as_int(record.get("id")) or 0
        return date, identifier

    @staticmethod
    def is_grabbed(record):
        event_type = record.get("eventType")
        return event_type == 1 or str(event_type).casefold() == "grabbed"

    def fetch_grab_history(self, stop_at=None, first_page_only=False):
        """Read newest grabbed events, stopping once a prior watermark is met."""
        records = []
        page = 1
        while True:
            response = self.request(
                "/history?eventType=1&sortKey=date&sortDirection=descending"
                f"&page={page}&pageSize={HISTORY_PAGE_SIZE}"
            )
            if not isinstance(response, dict):
                raise RuntimeError("/history returned an unexpected shape")
            raw_records = response.get("records") or []
            page_records = [
                record for record in raw_records
                if _as_int(record.get("id")) and self.is_grabbed(record)
            ]
            records.extend(page_records)
            if first_page_only:
                return records
            if stop_at is not None and page_records and all(
                    self.grab_key(record) <= stop_at
                    for record in page_records):
                return records
            total = _total_records(response.get("totalRecords"))
            if not raw_records or (
                    total is not None and page * HISTORY_PAGE_SIZE >= total):
                return records
            page += 1

    def fetch_grab_watermark(self):
        records = self.fetch_grab_history(first_page_only=True)
        return max((self.grab_key(record) for record in records),
                   default=("", 0))

    def parse_title(self, title):
        return self.request(
            f"/parse?title={urllib.parse.quote(title, safe='')}"
        )

    def post_command(self, command):
        return self.request("/command", "POST", command)

    def command_status(self, command_id):
        return self.request(f"/command/{command_id}")


def _request(base_url, api_key, path, method="GET", body=None,
             timeout=DEFAULT_TIMEOUT):
    """Send an API request and decode its JSON response."""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw.decode()) if raw else {}


def build_groups(missing):
    """Group missing episodes by season and order by lastSearchTime."""
    groups = {}
    for record in missing:
        key = (record["seriesId"], record["seasonNumber"])
        groups.setdefault(key, []).append(record)
    ordered = []
    for (series_id, season_number), episodes in groups.items():
        searches = [
            episode["lastSearchTime"] for episode in episodes
            if episode.get("lastSearchTime")
        ]
        ordered.append({
            "seriesId": series_id,
            "seasonNumber": season_number,
            "episodes": sorted(
                episodes, key=lambda episode: episode["episodeNumber"]
            ),
            "last_search": min(searches) if searches else None,
        })
    ordered.sort(key=lambda group: (
        group["last_search"] or "0000-01-01T00:00:00Z",
        group["seriesId"], group["seasonNumber"],
    ))
    return ordered


def split_batches(groups, batch_size):
    """Chunk groups without splitting a season search."""
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    batches, current, count = [], [], 0
    for group in groups:
        if current and count + len(group["episodes"]) > batch_size:
            batches.append(current)
            current, count = [], 0
        current.append(group)
        count += len(group["episodes"])
    if current:
        batches.append(current)
    return batches


def search_commands_for(batch):
    """Build Sonarr season/episode search commands for one batch."""
    commands = []
    for group in batch:
        if len(group["episodes"]) > 1:
            commands.append({
                "name": "SeasonSearch",
                "seriesId": group["seriesId"],
                "seasonNumber": group["seasonNumber"],
            })
        else:
            commands.append({
                "name": "EpisodeSearch",
                "episodeIds": [group["episodes"][0]["id"]],
            })
    return commands


def group_identity(group):
    return {
        "seriesId": group["seriesId"],
        "seasonNumber": group["seasonNumber"],
        "episodeIds": [episode["id"] for episode in group["episodes"]],
    }


def _command_result(record):
    status = str(record.get("status") or "").casefold()
    if status in {"failed", "cancelled", "canceled", "aborted"}:
        return False
    if status == "completed":
        return str(record.get("result") or "").casefold() in {
            "successful", "success",
        }
    return None


def wait_for_command(client, response, on_update=None):
    """Wait for a posted command; None means the bounded wait timed out."""
    command_id = _as_int(response.get("id")) if isinstance(response, dict) else None
    if command_id is None or command_id < 1:
        return False, {"id": None, "status": None, "result": None}

    def state(record):
        return {
            "id": command_id,
            "status": record.get("status"),
            "result": record.get("result"),
        }

    current = state(response)
    if on_update:
        on_update(current)
    result = _command_result(response)
    if result is not None:
        return result, current

    deadline = time.monotonic() + COMMAND_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        current = state(client.command_status(command_id))
        if on_update:
            on_update(current)
        result = _command_result(current)
        if result is not None:
            return result, current
        time.sleep(min(COMMAND_POLL_INTERVAL,
                       max(0, deadline - time.monotonic())))
    return None, current


class Verifier:
    """Own current-batch correlation and conservative title verification."""

    def __init__(self, client, expected_series_ids, expected_episode_ids):
        self.client = client
        self.expected_series_ids = frozenset(
            _as_int(value) for value in expected_series_ids
            if _as_int(value) is not None
        )
        self.expected_episode_ids = frozenset(
            _as_int(value) for value in expected_episode_ids
            if _as_int(value) is not None
        )

    def capture(self):
        """Watermark history before taking the queue snapshot."""
        try:
            watermark = self.client.fetch_grab_watermark()
        except Exception:
            watermark = None
        return VerificationSnapshot(watermark, self.client.fetch_queue_keys())

    def _parse_and_classify(self, title, reported_series_id, download_id,
                            allow_missing_reported_series=False):
        try:
            parsed = self.client.parse_title(title)
        except Exception as exc:
            parsed = {"series": None, "episodes": []}
            parse_error = f"parse error: {exc}"
        else:
            parse_error = None
        parsed_series = parsed.get("series") or {}
        parsed_series_id = _as_int(parsed_series.get("id"))
        reported_series_id = _as_int(reported_series_id)
        episodes = parsed.get("episodes") or []
        if (parse_error
                or not episodes
                or parsed_series_id not in self.expected_series_ids
                or (reported_series_id is not None
                    and reported_series_id != parsed_series_id)
                or (reported_series_id is None
                    and not allow_missing_reported_series)):
            return {
                "downloadId": download_id,
                "title": title,
                "seriesId": reported_series_id,
                "parsed": (
                    parse_error
                    or parsed_series.get("title")
                    or "NO_MATCH"
                ),
            }
        return None

    def _history_current(self, record, snapshot, command_ids):
        download_id = record.get("downloadId")
        if download_id is not None:
            queue_key = f"download:{download_id}"
            if queue_key in snapshot.before_ids:
                return False
        episode_id = _as_int(record.get("episodeId"))
        if "commandId" in record and record.get("commandId") is not None:
            return _as_int(record.get("commandId")) in command_ids
        return episode_id in self.expected_episode_ids

    def history_offenders(self, snapshot, command_id=None):
        """Return attributed new grabs; Sonarr history has no command ID today."""
        if snapshot.watermark is None:
            return False, [], 0, set()
        command_ids = {_as_int(command_id)} if _as_int(command_id) else set()
        records = self.client.fetch_grab_history(stop_at=snapshot.watermark)
        new_records = [
            record for record in records
            if self.client.grab_key(record) > snapshot.watermark
            and self.client.is_grabbed(record)
            and self._history_current(record, snapshot, command_ids)
        ]
        offenders = []
        download_ids = set()
        for record in new_records:
            download_id = record.get("downloadId")
            if download_id is not None:
                download_ids.add(str(download_id))
            offender = self._parse_and_classify(
                str(record.get("sourceTitle") or "?"),
                record.get("seriesId"),
                download_id,
                allow_missing_reported_series=True,
            )
            if offender:
                offenders.append(offender)
        return True, offenders, len(new_records), download_ids

    def queue_observations(self, snapshot, history_download_ids, command_id=None):
        observations = []
        offenders = []
        for record in self.client.fetch_queue_records():
            if self.client.queue_key(record) in snapshot.before_ids:
                continue
            download_id = record.get("downloadId")
            series_id = _as_int(record.get("seriesId"))
            raw_episode_ids = record.get("episodeIds")
            if raw_episode_ids is None:
                raw_episode_ids = [record.get("episodeId")]
            episode_ids = {
                parsed_id for parsed_id in (_as_int(value) for value in raw_episode_ids)
                if parsed_id is not None
            }
            if "commandId" in record and record.get("commandId") is not None:
                current = _as_int(record.get("commandId")) == _as_int(command_id)
            else:
                current = (
                    (download_id is not None
                     and str(download_id) in history_download_ids)
                    or bool(episode_ids & self.expected_episode_ids)
                    or (not episode_ids and series_id in self.expected_series_ids)
                    or series_id is None
                )
            if not current:
                continue
            observations.append(record)
            offender = self._parse_and_classify(
                str(record.get("title") or record.get("name") or "?"),
                series_id,
                download_id,
            )
            if offender:
                offenders.append(offender)
        return len(observations), offenders

    @staticmethod
    def merge_offenders(*groups):
        merged = {}
        for group in groups:
            for offender in group:
                key = offender.get("downloadId") or (
                    offender.get("title"), offender.get("seriesId"),
                    offender.get("parsed"),
                )
                merged[key] = offender
        return tuple(merged.values())

    def verify_once(self, snapshot, command_id=None):
        try:
            (history_available, history_offenders, history_count,
             history_download_ids) = self.history_offenders(snapshot, command_id)
        except Exception:
            history_available, history_offenders, history_count, history_download_ids = (
                False, [], 0, set()
            )
        queue_count, queue_offenders = self.queue_observations(
            snapshot, history_download_ids, command_id
        )
        return VerificationReport(
            history_available=history_available,
            history_count=history_count,
            queue_count=queue_count,
            observations=history_count + queue_count,
            offenders=self.merge_offenders(history_offenders, queue_offenders),
        )

    def verify_until_quiet(self, snapshot, quiet_window, command_id=None):
        """Poll through one bounded post-command verification window."""
        deadline = time.monotonic() + quiet_window
        latest = VerificationReport(False, 0, 0)
        while True:
            latest = self.verify_once(snapshot, command_id)
            if latest.offenders:
                return latest
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return latest
            time.sleep(min(VERIFY_POLL_INTERVAL, remaining))


def _checkpoint_group(group):
    return {
        "identity": group_identity(group),
        "status": "pending",
        "command": {"id": None, "status": None, "result": None},
        "snapshot": None,
        "verification": {
            "status": "pending", "historyAvailable": None,
            "historyCount": 0, "queueCount": 0,
        },
    }


def _checkpoint_plan(config, batches):
    return {
        "version": 1,
        "config": config.checkpoint_config(),
        "batches": [
            {
                "number": number,
                "groups": [_checkpoint_group(group) for group in batch],
            }
            for number, batch in enumerate(batches, 1)
        ],
    }


def _verification_checkpoint(report):
    return {
        "status": "aborted" if report.offenders else (
            "ok" if report.history_available else "unavailable"
        ),
        "historyAvailable": report.history_available,
        "historyCount": report.history_count,
        "queueCount": report.queue_count,
    }


def _failed_verification_checkpoint(report):
    return {
        "status": "failed",
        "historyAvailable": report.history_available if report else None,
        "historyCount": report.history_count if report else 0,
        "queueCount": report.queue_count if report else 0,
    }


class SearchEngine:
    """Own planning, command lifecycle, and checkpoint transitions."""

    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.store = (
            CheckpointStore(Path(config.checkpoint_path or DEFAULT_CHECKPOINT_PATH))
            if config.apply else None
        )
        self.checkpoint_path = Path(
            config.checkpoint_path or DEFAULT_CHECKPOINT_PATH
        )
        self._checkpoint_data = None

    def _checkpoint_write(self):
        if self.store is not None and self.config.checkpoint:
            self.store.write(self._checkpoint_data)

    def _config_matches(self, checkpoint):
        return checkpoint.get("config") == self.config.checkpoint_config()

    @staticmethod
    def _groups_from_checkpoint(checkpoint):
        return [
            {
                "number": batch["number"],
                "groups": [group["identity"] for group in batch["groups"]],
            }
            for batch in checkpoint["batches"]
        ]

    @staticmethod
    def _group_from_identity(identity):
        return {
            "seriesId": identity["seriesId"],
            "seasonNumber": identity["seasonNumber"],
            "episodes": [
                {"id": episode_id, "episodeNumber": index + 1}
                for index, episode_id in enumerate(identity["episodeIds"])
            ],
            "last_search": None,
        }

    def _plan_new(self):
        series_ids = None if self.config.all_series else self.config.series_ids
        missing = self.client.fetch_missing(series_ids)
        return missing, split_batches(build_groups(missing), self.config.batch_size)

    def _report_for_batch(self, number, total, groups, dry_run):
        return BatchReport(
            number=number,
            total=total,
            episodes=sum(len(group["episodes"]) for group in groups),
            commands=tuple(search_commands_for(groups)),
            groups=tuple(groups),
            dry_run=dry_run,
        )

    def _apply_group(self, group_state, group, report, verifier):
        status = group_state["status"]
        command = group_state["command"]
        snapshot_data = group_state["snapshot"]
        verification_state = group_state["verification"]
        if status == "completed" and verification_state["status"] in {
                "ok", "not_requested", "unavailable"}:
            report.skipped_groups += 1
            return None
        if status == "failed":
            return "checkpoint contains a failed group; inspect it before resuming"
        if status == "running" and command["id"] is None:
            return "checkpoint has an ambiguous group with no command ID; refusing to POST"

        if status == "pending":
            snapshot = verifier.capture()
            group_state["snapshot"] = snapshot.as_checkpoint()
            group_state["status"] = "running"
            group_state["command"] = {"id": None, "status": None, "result": None}
            self._checkpoint_write()
            try:
                response = self.client.post_command(search_commands_for([group])[0])
            except Exception as exc:
                return f"search command request failed; inspect and resume: {exc}"
            command_id = _as_int(response.get("id")) if isinstance(response, dict) else None
            if command_id is None or command_id < 1:
                return "search command returned no valid command ID; refusing to retry"
            group_state["command"] = {
                "id": command_id,
                "status": response.get("status"),
                "result": response.get("result"),
            }
            self._checkpoint_write()
        else:
            snapshot = VerificationSnapshot.from_checkpoint(snapshot_data)
            response = {
                "id": command["id"],
                "status": command["status"],
                "result": command["result"],
            }

        def update(state):
            group_state["command"] = state
            self._checkpoint_write()

        command_outcome, final_command = wait_for_command(
            self.client, response, update
        )
        group_state["command"] = final_command
        self._checkpoint_write()
        if command_outcome is None:
            group_state["status"] = "running"
            group_state["verification"] = {
                "status": "pending", "historyAvailable": None,
                "historyCount": 0, "queueCount": 0,
            }
            self._checkpoint_write()
            return "search command is still running; re-run with --resume"

        if not command_outcome and not self.config.verify:
            group_state["status"] = "failed"
            group_state["verification"] = _failed_verification_checkpoint(None)
            self._checkpoint_write()
            report.command_failed = True
            return "search command did not complete successfully"

        if self.config.verify:
            verification = verifier.verify_until_quiet(
                snapshot, self.config.quiet_window, final_command["id"]
            )
            report.verification = verification
            group_state["verification"] = _verification_checkpoint(verification)
            if verification.offenders:
                group_state["status"] = "failed"
                self._checkpoint_write()
                return "verification found suspect grab(s)"

        if not command_outcome:
            group_state["status"] = "failed"
            group_state["verification"] = _failed_verification_checkpoint(
                report.verification
            )
            self._checkpoint_write()
            report.command_failed = True
            return "search command did not complete successfully"

        if not self.config.verify:
            group_state["verification"] = {
                "status": "not_requested", "historyAvailable": None,
                "historyCount": 0, "queueCount": 0,
            }
        group_state["status"] = "completed"
        self._checkpoint_write()
        return None

    def run(self, resume=False):
        error = self.config.validate()
        if error:
            return RunResult(1, error)
        if resume and not self.config.apply:
            return RunResult(1, "--resume requires --apply")
        if resume and not self.config.checkpoint:
            return RunResult(1, "--resume requires checkpoints")
        if self.config.apply and not self.config.checkpoint and self.checkpoint_path.exists():
            return RunResult(
                1,
                "checkpoint exists; use --resume without --yes, or remove it after review",
            )

        if self.config.apply and resume:
            try:
                checkpoint = self.store.load()
            except CheckpointError as exc:
                return RunResult(1, str(exc))
            if not self._config_matches(checkpoint):
                return RunResult(1, "checkpoint scope/config does not match this run")
            self._checkpoint_data = checkpoint
            batches = self._groups_from_checkpoint(checkpoint)
            missing_count = sum(
                len(group["episodeIds"])
                for batch in batches for group in batch["groups"]
            )
        elif self.config.apply:
            if self.store is not None and self.store.exists():
                return RunResult(
                    1,
                    "checkpoint exists; pass --resume to continue safely",
                )
            missing, planned_batches = self._plan_new()
            if not missing:
                return RunResult(0, "no missing episodes to search")
            if self.config.checkpoint:
                self._checkpoint_data = _checkpoint_plan(
                    self.config, planned_batches
                )
                self._checkpoint_write()
            batches = [
                {
                    "number": number,
                    "groups": [group_identity(group) for group in batch],
                }
                for number, batch in enumerate(planned_batches, 1)
            ]
            missing_count = len(missing)
        else:
            missing, planned_batches = self._plan_new()
            if not missing:
                return RunResult(0, "no missing episodes to search")
            batches = [
                {"number": number, "groups": batch}
                for number, batch in enumerate(planned_batches, 1)
            ]
            missing_count = len(missing)

        result = RunResult(
            exit_code=0, summary="complete", missing_count=missing_count,
            group_count=sum(len(batch["groups"]) for batch in batches),
            batch_count=len(batches),
        )
        for batch_index, batch in enumerate(batches):
            number = batch["number"]
            groups = [
                self._group_from_identity(identity)
                if self.config.apply else identity
                for identity in batch["groups"]
            ]
            if self.config.apply and self.config.checkpoint:
                states = self._checkpoint_data["batches"][number - 1]["groups"]
            elif self.config.apply:
                states = [_checkpoint_group(group) for group in groups]
            else:
                states = [None] * len(groups)
            batch_had_work = (
                self.config.apply
                and any(state["status"] != "completed" for state in states)
            )
            report = self._report_for_batch(
                number, len(batches), groups, not self.config.apply
            )
            result.reports.append(report)
            if not self.config.apply:
                if self.config.verify:
                    verifier = Verifier(
                        self.client,
                        {group["seriesId"] for group in groups},
                        {episode["id"] for group in groups
                         for episode in group["episodes"]},
                    )
                    report.verification = verifier.verify_until_quiet(
                        verifier.capture(), self.config.quiet_window
                    )
                continue
            for state, group in zip(states, groups):
                verifier = Verifier(
                    self.client,
                    {group["seriesId"]},
                    {episode["id"] for episode in group["episodes"]},
                )
                problem = self._apply_group(state, group, report, verifier)
                if problem:
                    result.exit_code = (
                        2 if report.verification and report.verification.offenders else 1
                    )
                    result.summary = (
                        f"verify-abort: {problem}" if result.exit_code == 2 else problem
                    )
                    result.offenders = (
                        report.verification.offenders
                        if report.verification else ()
                    )
                    return result
            if (self.config.checkpoint and batch_had_work
                    and batch_index < len(batches) - 1):
                result.summary = f"checkpoint after batch {number}/{len(batches)}"
                return result
            if self.config.gap and batch_index < len(batches) - 1:
                time.sleep(self.config.gap)
        return result


def run(base_url, api_key, series_ids, all_series, batch_size, gap,
        checkpoint, verify, apply, timeout=DEFAULT_TIMEOUT,
        quiet_window=DEFAULT_QUIET_WINDOW, checkpoint_path="", resume=False):
    config = SearchConfig(
        series_ids=tuple(series_ids) if series_ids else None,
        all_series=all_series,
        batch_size=batch_size,
        gap=gap,
        quiet_window=quiet_window,
        checkpoint=checkpoint,
        verify=verify,
        apply=apply,
        timeout=timeout,
        checkpoint_path=checkpoint_path or DEFAULT_CHECKPOINT_PATH,
        base_url=base_url,
    )
    return SearchEngine(SonarrClient(base_url, api_key, timeout), config).run(
        resume=resume
    )
