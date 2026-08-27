"""Container lifecycle operations — list, restart, stop, start, logs, restart-all.

Extracted from host/services.py. Handles Docker container management
operations for the compose project.

Write operations (restart/stop/start) route through the host helper
daemon for security — the Docker socket is read-only.
Read operations (list/stats/logs) use the Docker SDK directly.
"""
import concurrent.futures
import threading

from core.api_base import ServiceError
from core.docker_client import (
    MOUNT_DEPENDENTS,
    MOUNT_PREREQS,
    MOUNT_PROVIDERS,
    container_label,
    container_stats,
    docker_client,
    find_project_container,
    helper_restart,
    helper_start,
    helper_stop,
    project_containers,
    wait_for_healthy,
)


def get_status() -> dict:
    """Every container in the compose project with state + health."""
    _, containers = project_containers()
    out = {}
    for c in containers:
        health = c.attrs.get("State", {}).get("Health", {}).get("Status")
        out[c.name] = {"state": c.status, "health": health}
    return out


def _container_row(me, c) -> dict:
    label, note = (container_label(c.name), None)
    # CONTAINER_LABELS lookup for note
    from core.docker_client import CONTAINER_LABELS
    label, note = CONTAINER_LABELS.get(c.name, (c.name, None))
    health = c.attrs.get("State", {}).get("Health", {}).get("Status")
    # c.image.* is a lazy API call (inspect_image) that raises ImageNotFound
    # when a container's image was removed from the store while the container
    # still runs from it (e.g. an image prune raced a recreate).
    try:
        image_tags = c.image.tags
        image = image_tags[0] if image_tags else (c.image.short_id or "")
    except Exception:
        image = ""
    service = c.labels.get("com.docker.compose.service", c.name)
    return {
        "name": c.name,
        "label": label,
        "note": note,
        "service": service,
        "image": image,
        "state": c.status,
        "health": health,
        "is_self": c.id == me.id,
        **container_stats(c),
    }


def list_containers() -> list[dict]:
    """Full container grid: name/label/image/state/health/CPU/mem per
    container, fetched in parallel (stats calls are the slow part)."""
    me, containers = project_containers()
    ordered = sorted(containers, key=lambda c: c.name)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(ordered), 16) or 1) as pool:
        return list(pool.map(lambda c: _container_row(me, c), ordered))


def restart_container(name: str, activated: bool = False) -> str:
    if name == "plex" and not activated:
        raise ServiceError(
            "Plex restart requires activated=true - a plain restart click is no longer "
            "enough (by design). Pass activated=true explicitly to restart Plex.",
            status=400,
        )
    # Validate the container exists in the project (read-only check)
    find_project_container(name, reject_self=True)
    try:
        helper_restart(name)
    except Exception as e:
        raise ServiceError(f"Restart failed: {e}") from e
    return f"{container_label(name)} restarted."


def stop_container(name: str) -> str:
    c = find_project_container(name, reject_self=True)
    if c.status != "running":
        return f"{container_label(name)} is already {c.status}."
    try:
        helper_stop(name)
    except Exception as e:
        raise ServiceError(f"Stop failed: {e}") from e
    return f"{container_label(name)} stopped."


def start_container(name: str) -> str:
    c = find_project_container(name, reject_self=False)
    if c.status == "running":
        return f"{container_label(name)} is already running."
    try:
        helper_start(name)
    except Exception as e:
        raise ServiceError(f"Start failed: {e}") from e
    return f"{container_label(name)} started."


def stream_container_logs(name: str, tail: int = 100):
    """Generator yielding SSE \"data: <line>\" events from the live container
    log stream."""
    c = find_project_container(name, reject_self=False)

    def generate():
        for line in c.logs(stream=True, follow=True, tail=tail, timestamps=True):
            text = line.decode(errors="replace").rstrip("\n")
            for part in text.splitlines() or [""]:
                yield f"data: {part}\n\n"

    return generate()


def restart_all() -> str:
    """Restart every container except this panel, in FUSE-safe mount order."""
    me, containers = project_containers()
    targets = [c for c in containers if c.id != me.id]
    if not targets:
        raise ServiceError("No other containers found in this compose project.")
    names = sorted(c.name for c in targets)

    prereqs = [c for c in targets if c.name in MOUNT_PREREQS]
    providers = [c for c in targets if c.name in MOUNT_PROVIDERS]
    dependents = [c for c in targets if c.name in MOUNT_DEPENDENTS]
    staged = MOUNT_PREREQS | MOUNT_PROVIDERS | MOUNT_DEPENDENTS
    rest = [c for c in targets if c.name not in staged]

    def worker():
        for c in prereqs:
            try:
                helper_restart(c.name)
            except Exception as e:
                print(f"restart-all: failed to restart {c.name}: {e}")
        for c in prereqs:
            wait_for_healthy(c)
        for c in providers:
            try:
                helper_restart(c.name)
            except Exception as e:
                print(f"restart-all: failed to restart {c.name}: {e}")
        for c in providers:
            wait_for_healthy(c)
        for c in rest:
            try:
                helper_restart(c.name)
            except Exception as e:
                print(f"restart-all: failed to restart {c.name}: {e}")
        for c in dependents:
            try:
                helper_restart(c.name)
            except Exception as e:
                print(f"restart-all: failed to restart {c.name}: {e}")
        # nzbdav bind-mounts /mnt directly too - re-restart to rebind
        for c in prereqs:
            try:
                helper_restart(c.name)
            except Exception as e:
                print(f"restart-all: failed to restart {c.name}: {e}")

    threading.Thread(target=worker, daemon=True).start()
    return f"Restarting {len(names)} containers (everything except this panel): {', '.join(names)}"
