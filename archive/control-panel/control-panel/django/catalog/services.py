"""Curated software catalog: install/remove/list for the vetted programs
in registry.py. Ported from control-panel/services/catalog/router.py.

All Docker write operations (pull, run, stop, remove, volume remove)
go through the host helper daemon for security. The Docker socket is
read-only for listing and inspection only.

Auth split: list_catalog/get_status accept a session OR a service key.
install/remove require a real session (IsAuthenticatedSessionOnly).
"""
import docker

from core.api_base import ServiceError
from core.docker_client import docker_client, helper_pull, helper_remove, helper_remove_volume, helper_run, helper_stop
from catalog.registry import CATALOG, CATALOG_BY_ID, CATALOG_LABEL, NETWORK


def _container_name(catalog_id: str) -> str:
    return f"catalog-{catalog_id}"


def _find_container(catalog_id: str):
    try:
        return docker_client.containers.get(_container_name(catalog_id))
    except docker.errors.NotFound:
        return None


def _host_ports_in_use(exclude_name: str | None = None) -> set[int]:
    used = set()
    for c in docker_client.containers.list(all=True):
        if exclude_name and c.name == exclude_name:
            continue
        bindings = (c.attrs.get("HostConfig") or {}).get("PortBindings") or {}
        for host_binds in bindings.values():
            if not host_binds:
                continue
            for b in host_binds:
                port = b.get("HostPort")
                if port:
                    used.add(int(port))
    return used


def list_catalog() -> dict:
    items = []
    for entry in CATALOG:
        c = _find_container(entry["id"])
        status = "not_installed"
        if c is not None:
            status = "running" if c.status == "running" else c.status
        items.append({
            "id": entry["id"], "name": entry["name"], "category": entry["category"],
            "pitch": entry["pitch"], "image": f"{entry['image']}:{entry['tag']}",
            "footprint": entry["footprint"], "doc_url": entry["doc_url"], "caveat": entry.get("caveat"),
            "ports": sorted(entry["ports"].values()), "status": status,
            "environment": entry["environment"], "volumes": entry["volumes"],
        })
    installed_count = sum(1 for i in items if i["status"] != "not_installed")
    return {
        "message": f"{len(items)} catalog entries, {installed_count} installed.",
        "items": items,
    }


def get_status(catalog_id: str) -> dict:
    entry = CATALOG_BY_ID.get(catalog_id)
    if entry is None:
        raise ServiceError(f"Unknown catalog entry '{catalog_id}'.", status=404)
    c = _find_container(catalog_id)
    if c is None:
        return {"message": "Not installed.", "status": "not_installed"}
    c.reload()
    health = (c.attrs.get("State", {}).get("Health") or {}).get("Status")
    return {
        "message": f"{entry['name']}: {c.status}.",
        "status": c.status,
        "health": health,
        "started_at": c.attrs.get("State", {}).get("StartedAt"),
    }


def install(catalog_id: str) -> dict:
    entry = CATALOG_BY_ID.get(catalog_id)
    if entry is None:
        raise ServiceError(f"Unknown catalog entry '{catalog_id}'.", status=404)

    name = _container_name(catalog_id)
    if _find_container(catalog_id) is not None:
        raise ServiceError(f"{entry['name']} is already installed.", status=409)

    wanted_ports = set(entry["ports"].values())
    conflict = wanted_ports & _host_ports_in_use()
    if conflict:
        raise ServiceError(
            f"Port(s) {sorted(conflict)} already in use by another container - "
            f"{entry['name']} needs {sorted(wanted_ports)}.",
            status=409,
        )

    # Pull image via host helper
    try:
        helper_pull(entry["image"], entry["tag"])
    except Exception as e:
        raise ServiceError(f"Failed to pull {entry['image']}:{entry['tag']}: {e}") from e

    # Build volumes dict for the helper
    volumes = []
    for vol_name, vol_conf in entry["volumes"].items():
        if isinstance(vol_conf, dict):
            volumes.append({"source": vol_name, "target": vol_conf.get("bind", vol_name), "mode": vol_conf.get("mode", "rw")})
        else:
            volumes.append({"source": vol_name, "target": vol_conf, "mode": "rw"})

    if entry.get("docker_sock"):
        mode = "rw" if catalog_id == "portainer" else "ro"
        volumes.append({"source": "/var/run/docker.sock", "target": "/var/run/docker.sock", "mode": mode})

    # Run container via host helper
    try:
        helper_run(
            image=f"{entry['image']}:{entry['tag']}",
            name=name,
            network=NETWORK,
            ports=entry["ports"],
            volumes=volumes,
            environment=entry["environment"],
            cap_add=entry["cap_add"],
            command=entry.get("command"),
            restart_policy="unless-stopped",
            labels={CATALOG_LABEL: catalog_id},
        )
    except Exception as e:
        raise ServiceError(f"{entry['name']} failed to start: {e}") from e

    message = f"{entry['name']} installed and starting."
    if entry.get("caveat"):
        message += f" Note: {entry['caveat']}"
    return {"message": message, "ports": sorted(wanted_ports)}


def remove(catalog_id: str, remove_volumes: bool = False) -> dict:
    entry = CATALOG_BY_ID.get(catalog_id)
    if entry is None:
        raise ServiceError(f"Unknown catalog entry '{catalog_id}'.", status=404)

    c = _find_container(catalog_id)
    if c is None:
        raise ServiceError(f"{entry['name']} isn't installed.", status=404)

    name = _container_name(catalog_id)

    # Stop and remove via host helper
    try:
        helper_stop(name, timeout=15)
        helper_remove(name)
    except Exception as e:
        raise ServiceError(f"Failed to remove {entry['name']}: {e}") from e

    volume_note = ""
    if remove_volumes and entry["volumes"]:
        removed, errors = [], []
        for vol_name in entry["volumes"]:
            try:
                helper_remove_volume(vol_name)
                removed.append(vol_name)
            except Exception as e:
                errors.append(f"{vol_name}: {e}")
        volume_note = f" Removed {len(removed)} volume(s)."
        if errors:
            volume_note += f" {len(errors)} volume(s) failed to remove: {errors}"
    elif entry["volumes"]:
        volume_note = " Data volume(s) kept - pass remove_volumes=true to delete them too."

    return {"message": f"{entry['name']} removed.{volume_note}"}
