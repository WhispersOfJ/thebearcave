"""Host maintenance — prune disk, log levels, notify test, stack top.

Extracted from host/services.py. Operations that modify host state
or query external services for maintenance purposes.
"""
import os

import docker
import httpx

from core import settings as settings_core
from core.api_base import ServiceError
from core.arr_client import ARR_APPS, PROWLARR_CFG
from core.docker_client import container_stats, docker_client, project_containers
from core.formatters import human_size

LOG_LEVEL_APPS = {
    "radarr": ARR_APPS["radarr"],
    "sonarr": ARR_APPS["sonarr"],
    "prowlarr": PROWLARR_CFG,
}


def get_settings() -> dict:
    return settings_core.get_settings()


def patch_settings(patch: dict) -> dict:
    return settings_core.update_settings(patch)


def prune_disk() -> str:
    """Prunes dangling images and unused volumes only."""
    try:
        images_result = docker_client.images.prune()
        volumes_result = docker_client.volumes.prune()
    except docker.errors.APIError as e:
        raise ServiceError(f"Prune failed: {e}") from e
    reclaimed = (images_result.get("SpaceReclaimed") or 0) + (volumes_result.get("SpaceReclaimed") or 0)
    return (f"Reclaimed {human_size(reclaimed, fallback='0 B')} "
            f"({len(images_result.get('ImagesDeleted') or [])} image(s), "
            f"{len(volumes_result.get('VolumesDeleted') or [])} volume(s)).")


def log_levels() -> dict:
    """Current logLevel for every Servarr-shaped app."""
    out = {}
    for name, cfg in LOG_LEVEL_APPS.items():
        try:
            r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/config/host", headers={"X-Api-Key": cfg["key"]}, timeout=10)
            r.raise_for_status()
            out[name] = r.json().get("logLevel")
        except Exception as e:
            out[name] = f"error: {e}"
    debug_apps = [n for n, lvl in out.items() if lvl == "debug"]
    msg = f"{len(debug_apps)} app(s) at debug: {', '.join(debug_apps)}" if debug_apps else "All apps at info (or non-debug)."
    return {"message": msg, "levels": out}


def reset_log_levels() -> str:
    """Sets logLevel back to 'info' on every app currently at 'debug'."""
    reset = []
    for name, cfg in LOG_LEVEL_APPS.items():
        try:
            r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/config/host", headers={"X-Api-Key": cfg["key"]}, timeout=10)
            r.raise_for_status()
            current = r.json()
            if current.get("logLevel") != "debug":
                continue
            current["logLevel"] = "info"
            httpx.put(
                f"{cfg['url']}/api/{cfg['api']}/config/host/{current['id']}",
                headers={"X-Api-Key": cfg["key"], "Content-Type": "application/json"},
                json=current,
                timeout=10,
            ).raise_for_status()
            reset.append(name)
        except Exception as e:
            print(f"log-levels-reset: failed for {name}: {e}")
    if not reset:
        return "Nothing to reset - no app was at debug."
    return f"Reset {len(reset)} app(s) to info: {', '.join(reset)}"


def notify_test() -> str:
    """Sends a test message through the Discord webhook."""
    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not discord_webhook_url:
        raise ServiceError("DISCORD_WEBHOOK_URL not set.")
    try:
        r = httpx.post(discord_webhook_url, json={"content": "Control Panel test notification"}, timeout=10)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise ServiceError(f"Discord notification failed: {e}") from e
    return "Test notification sent."


def stack_top(by: str = "cpu", limit: int = 10) -> dict:
    """Top containers by CPU or memory."""
    if by not in ("cpu", "mem"):
        raise ServiceError("'by' must be 'cpu' or 'mem'.", status=400)
    me, containers = project_containers()
    rows = []
    for c in containers:
        if c.id == me.id or c.status != "running":
            continue
        stats = container_stats(c)
        rows.append({
            "name": c.name,
            "cpu_percent": stats["cpu_percent"],
            "mem_percent": stats["mem_percent"],
            "mem_used_mb": stats["mem_used_mb"],
        })
    key = "cpu_percent" if by == "cpu" else "mem_percent"
    rows = [r for r in rows if r[key] is not None]
    rows.sort(key=lambda r: r[key], reverse=True)
    return {"message": f"Top {min(limit, len(rows))} containers by {by}.", "items": rows[:limit]}
