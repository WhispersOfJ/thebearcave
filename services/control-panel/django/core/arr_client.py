"""Shared Radarr/Sonarr config + helpers — backward-compatible re-export hub.

This module re-exports every symbol that callers previously imported from
here, but the implementations now live in focused modules:

  core/arr_config  — ARR_APPS, QUEUE_ARR_APPS, RADARR_APPS, SONARR_APPS,
                     PROWLARR_CFG, HOST_CONFIG_DIR
  core/arr_movie   — get_movie_or_episode, item_is_monitored,
                     blocklist_and_research, radarr_root_folder_and_profile,
                     radarr_quality_profile_id_by_name, radarr_ensure_tags,
                     radarr_add_movie
  core/arr_series  — sonarr_root_folder_and_profile, sonarr_add_series
  core/formatters  — human_size

New code should import directly from the focused modules. This file
exists only so existing callers don't break.
"""
import re

from core.api_base import ServiceError

# --- config ---
from core.arr_config import (  # noqa: F401
    ARR_APPS,
    HOST_CONFIG_DIR,
    PROWLARR_API_KEY,
    PROWLARR_CFG,
    QUEUE_ARR_APPS,
    RADARR_APPS,
    SONARR_APPS,
)

# --- formatters ---
from core.formatters import human_size  # noqa: F401

# --- nzbdav re-export (kept for callers that import from here) ---
from core.nzbdav_client import NZBDAV_API_KEY, NZBDAV_URL, nzbdav_api  # noqa: F401

# --- movie operations ---
from core.arr_movie import (  # noqa: F401
    blocklist_and_research,
    get_movie_or_episode,
    item_is_monitored,
    radarr_add_movie,
    radarr_ensure_tags,
    radarr_quality_profile_id_by_name,
    radarr_root_folder_and_profile,
)

# --- series operations ---
from core.arr_series import (  # noqa: F401
    sonarr_add_series,
    sonarr_root_folder_and_profile,
)

# --- local helpers (small enough to keep here) ---

import httpx

from core.arr_config import ARR_APPS as _ARR_APPS, QUEUE_ARR_APPS as _QUEUE_ARR_APPS, RADARR_APPS as _RADARR_APPS


def format_eta(seconds: float) -> str:
    if seconds == float("inf") or seconds < 0:
        return "unknown"
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d{hours:02d}h"
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def arr_command(app_name: str, command: str) -> dict:
    if app_name not in _ARR_APPS:
        raise ServiceError(f"Unknown app '{app_name}'.", status=404)
    cfg = _ARR_APPS[app_name]
    url = f"{cfg['url']}/api/{cfg['api']}/command"
    try:
        r = httpx.post(url, json={"name": command}, headers={"X-Api-Key": cfg["key"]}, timeout=15)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ServiceError(f"{cfg['label']} {command} failed: {e}")
    return cfg


def require_queue_app(app_name: str) -> dict:
    if app_name not in _QUEUE_ARR_APPS:
        raise ServiceError(f"'{app_name}' isn't supported here - only radarr and sonarr have a queue.", status=404)
    return _ARR_APPS[app_name]


def arr_queue(app_name: str) -> list[dict]:
    cfg = _ARR_APPS[app_name]
    params = {"pageSize": 250, "includeUnknownMovieItems": "true"}
    params["includeMovie" if app_name in _RADARR_APPS else "includeEpisode"] = "true"
    try:
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/queue", params=params, headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ServiceError(f"{cfg['label']} queue lookup failed: {e}")
    return r.json().get("records", [])


def stuck_queue_items(app_name: str) -> list[dict]:
    return [q for q in arr_queue(app_name) if q.get("trackedDownloadStatus") in ("warning", "error")]


def import_candidate_queue_items(app_name: str) -> list[dict]:
    return [
        q for q in arr_queue(app_name)
        if q.get("trackedDownloadStatus") in ("warning", "error")
        or q.get("trackedDownloadState") == "importPending"
    ]


def disable_autoredownload_if_storm(app_name: str, failed_pending_count: int, threshold: int) -> bool:
    if failed_pending_count < threshold:
        return False
    cfg = _ARR_APPS[app_name]
    try:
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/config/downloadclient", headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        current = r.json()
        if not current.get("autoRedownloadFailed"):
            return False
        current["autoRedownloadFailed"] = False
        r = httpx.put(f"{cfg['url']}/api/{cfg['api']}/config/downloadclient/{current['id']}", json=current,
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


IMPORTING_TEST_TIMEOUT_S = 40
IMPORTING_TEST_MB = 5


def dd_test_file(container, file_path: str) -> tuple[bool, str]:
    try:
        result = container.exec_run(
            cmd=["timeout", str(IMPORTING_TEST_TIMEOUT_S), "dd", f"if={file_path}", "of=/dev/null", "bs=1M",
                 f"count={IMPORTING_TEST_MB}"],
            demux=True,
        )
    except Exception as e:
        return False, f"exec failed: {e}"
    if result.exit_code == 0:
        return True, "readable"
    stderr = b""
    if result.output and result.output[1]:
        stderr = result.output[1]
    return False, stderr.decode(errors="replace").strip() or f"dd exited {result.exit_code}"


def find_candidate_files(container, output_path: str) -> tuple[str, list[str]]:
    """Returns (status, files): 'missing' if output_path doesn't exist on
    disk at all, 'empty' if the path exists but has no file worth testing,
    or 'ok' with the files found."""
    exists = container.exec_run(cmd=["test", "-e", output_path])
    if exists.exit_code != 0:
        return "missing", []
    find_result = container.exec_run(cmd=["find", output_path, "-maxdepth", "2", "-type", "l"])
    files = [f for f in find_result.output.decode(errors="replace").splitlines() if f.strip()]
    if not files:
        find_result = container.exec_run(cmd=["find", output_path, "-maxdepth", "2", "-type", "f"])
        files = [f for f in find_result.output.decode(errors="replace").splitlines() if f.strip()]
    return ("ok", files) if files else ("empty", [])


def importing_queue_targets(app_name: str) -> list[dict]:
    items = [q for q in arr_queue(app_name) if q.get("trackedDownloadState") == "importing"]
    by_download: dict[str, dict] = {}
    for q in items:
        key = q.get("downloadId") or str(q["id"])
        target = by_download.setdefault(key, {
            "queueIds": [], "title": q.get("title"), "outputPath": q.get("outputPath"),
            "seriesId": q.get("seriesId"), "movieId": q.get("movieId"),
        })
        target["queueIds"].append(q["id"])
    return list(by_download.values())


# Matches Radarr/Sonarr dedup suffixes like "(2)" but not year suffixes like
# "(2020)" — requires 1-3 digits to avoid false positives on 4-digit years.
DEDUP_SUFFIX_RE = re.compile(r"\s\(\d{1,3}\)(\.[A-Za-z0-9]+)?$")


def dedup_suffix_hit(name: str | None) -> bool:
    if not name:
        return False
    base = name.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    return bool(DEDUP_SUFFIX_RE.search(stem))


def current_queue_output_path(app_name: str, target_id: int, id_field: str) -> str | None:
    for q in arr_queue(app_name):
        if q.get(id_field) == target_id:
            return q.get("outputPath")
    return None


def arr_sizeleft_snapshot(app_name: str) -> dict[int, int]:
    try:
        records = arr_queue(app_name)
    except ServiceError:
        return {}
    return {q["id"]: q.get("sizeleft") or 0 for q in records if q.get("sizeleft")}


def wanted_missing_total(app_name: str) -> int:
    cfg = _ARR_APPS[app_name]
    try:
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/wanted/missing", params={"pageSize": 1},
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ServiceError(f"{cfg['label']} wanted/missing lookup failed: {e}")
    return r.json().get("totalRecords", 0)


RECENT_IMPORT_LOOKBACK_HOURS = 6
RECENT_IMPORT_SAMPLE_SIZE = 200
MIN_RATE_WINDOW_HOURS = 0.25


def recent_import_rate_per_hour(app_name: str) -> tuple[float, int]:
    """Returns (rate_per_hour, sample_count). Rate is 0 if there aren't at
    least 2 qualifying events, or the newest one is older than
    RECENT_IMPORT_LOOKBACK_HOURS."""
    cfg = _ARR_APPS[app_name]
    try:
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/history",
                       params={"pageSize": RECENT_IMPORT_SAMPLE_SIZE, "sortKey": "date", "sortDirection": "descending"},
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ServiceError(f"{cfg['label']} history lookup failed: {e}")
    records = r.json().get("records", [])
    events = [rec for rec in records if rec.get("eventType") in cfg["import_events"]]
    if len(events) < 2:
        return 0.0, len(events)
    from datetime import datetime, timezone
    newest = datetime.fromisoformat(events[0]["date"].replace("Z", "+00:00"))
    oldest = datetime.fromisoformat(events[-1]["date"].replace("Z", "+00:00"))
    if (datetime.now(timezone.utc) - newest).total_seconds() > RECENT_IMPORT_LOOKBACK_HOURS * 3600:
        return 0.0, len(events)
    span_hours = max((newest - oldest).total_seconds() / 3600, MIN_RATE_WINDOW_HOURS)
    return len(events) / span_hours, len(events)
