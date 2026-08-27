"""Host diagnostics — resource checks, disk health, mount health, OOM, permissions.

Extracted from host/services.py. These are all read-only diagnostic
operations that report on host and container health.
"""
import os
import shutil
import time

import docker

from core.api_base import ServiceError
from core.docker_client import container_stats, docker_client, project_containers
from core.formatters import human_size
from core.host_paths import HOST_CONFIG_DIR, HOST_MNT_DIR, HOST_PROC_DIR


KNOWN_MOUNTS = ["remote/nzbdav"]


def resource_check() -> dict:
    """Every container missing mem_limit or cpus."""
    me, containers = project_containers()
    missing = []
    for c in containers:
        if c.id == me.id:
            continue
        host_config = c.attrs.get("HostConfig", {})
        mem_limit = host_config.get("Memory") or 0
        nano_cpus = host_config.get("NanoCpus") or 0
        if mem_limit == 0 or nano_cpus == 0:
            missing.append({
                "name": c.name,
                "mem_limit_set": mem_limit != 0,
                "cpus_set": nano_cpus != 0,
                **container_stats(c),
            })
    if not missing:
        return {"message": "Every container has both mem_limit and cpus set.", "containers": []}
    return {
        "message": f"{len(missing)} container(s) missing mem_limit and/or cpus.",
        "containers": missing,
    }


def disk_health() -> dict:
    """Host mount free space plus Docker reclaimable-space breakdown."""
    total, used, free = shutil.disk_usage(HOST_MNT_DIR)
    mount = {
        "path": HOST_MNT_DIR, "total": human_size(total, fallback="0 B"), "used": human_size(used, fallback="0 B"),
        "free": human_size(free, fallback="0 B"), "percent": round(used / total * 100, 1) if total else 0.0,
    }
    try:
        df = docker_client.df()
    except docker.errors.APIError as e:
        raise ServiceError(f"Docker df failed: {e}") from e
    reclaimable = {
        "images": sum(i.get("Size", 0) - i.get("SharedSize", 0) for i in df.get("Images") or [] if i.get("Containers") == 0),
        "containers": sum(c.get("SizeRw", 0) for c in df.get("Containers") or [] if c.get("State") != "running"),
        "volumes": sum(v.get("UsageData", {}).get("Size", 0) or 0 for v in df.get("Volumes") or [] if (v.get("UsageData") or {}).get("RefCount", 1) == 0),
        "build_cache": sum(b.get("Size", 0) for b in df.get("BuildCache") or [] if not b.get("InUse")),
    }
    reclaimable_human = {k: human_size(v, fallback="0 B") for k, v in reclaimable.items()}
    total_reclaimable = sum(reclaimable.values())
    return {
        "message": f"{mount['path']}: {mount['percent']}% used, {mount['free']} free. "
                   f"{human_size(total_reclaimable, fallback='0 B')} reclaimable from unused Docker images/volumes/build cache.",
        "mount": mount, "reclaimable": reclaimable_human,
        "total_reclaimable": human_size(total_reclaimable, fallback="0 B"),
    }


def _read_host_proc_meminfo() -> dict | None:
    path = os.path.join(HOST_PROC_DIR, "meminfo")
    if not os.path.isfile(path):
        return None
    values = {}
    with open(path) as f:
        for line in f:
            key, _, rest = line.partition(":")
            try:
                values[key] = int(rest.strip().split()[0]) * 1024  # kB -> bytes
            except (ValueError, IndexError):
                continue
    return values


def _read_host_proc_cpu_line() -> list[int] | None:
    path = os.path.join(HOST_PROC_DIR, "stat")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        first = f.readline()
    if not first.startswith("cpu "):
        return None
    return [int(x) for x in first.split()[1:]]


def host_resources() -> dict:
    """Real host-wide CPU/RAM, read from /host-proc."""
    mem = _read_host_proc_meminfo()
    cpu_before = _read_host_proc_cpu_line()
    if mem is None or cpu_before is None:
        raise ServiceError(
            f"{HOST_PROC_DIR} not available - host resource stats need the Plex Health proc mount.",
            status=503,
        )
    time.sleep(0.2)
    cpu_after = _read_host_proc_cpu_line()

    idle_before, idle_after = cpu_before[3], cpu_after[3]
    total_before, total_after = sum(cpu_before), sum(cpu_after)
    total_delta = total_after - total_before
    idle_delta = idle_after - idle_before
    cpu_percent = round((1 - idle_delta / total_delta) * 100, 1) if total_delta else 0.0

    mem_total = mem.get("MemTotal", 0)
    mem_available = mem.get("MemAvailable", mem.get("MemFree", 0))
    mem_used = mem_total - mem_available
    mem_percent = round(mem_used / mem_total * 100, 1) if mem_total else 0.0

    return {
        "message": f"CPU {cpu_percent}%, RAM {mem_percent}% ({human_size(mem_used)} / {human_size(mem_total)}).",
        "cpu_percent": cpu_percent, "mem_percent": mem_percent,
        "mem_used": human_size(mem_used), "mem_total": human_size(mem_total),
    }


def oom_check() -> dict:
    """Containers Docker itself has ever recorded an OOM kill for."""
    me, containers = project_containers()
    killed = [c.name for c in containers if c.id != me.id and c.attrs.get("State", {}).get("OOMKilled")]
    if not killed:
        return {"message": "No container currently shows an OOM-kill flag.", "containers": []}
    return {
        "message": f"{len(killed)} container(s) have been OOM-killed at least once (flag persists until next "
                   f"recreate, not necessarily still happening): {', '.join(killed)}",
        "containers": killed,
    }


def disk_usage() -> dict:
    """Per-app config/ directory size."""
    if not os.path.isdir(HOST_CONFIG_DIR):
        raise ServiceError(f"{HOST_CONFIG_DIR} not mounted.")
    sizes = []
    for entry in sorted(os.listdir(HOST_CONFIG_DIR)):
        path = os.path.join(HOST_CONFIG_DIR, entry)
        if not os.path.isdir(path):
            continue
        total = 0
        for dirpath, _, filenames in os.walk(path, followlinks=False):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.lstat(fp).st_blocks * 512
                except OSError:
                    pass
        sizes.append({"app": entry, "mb": round(total / 1024 / 1024, 1)})
    sizes.sort(key=lambda x: x["mb"], reverse=True)
    return {"message": f"{len(sizes)} app config directories.", "sizes": sizes}


def mount_health() -> dict:
    """Every known FUSE mountpoint under /mnt, checked for a clean listing."""
    results = []
    for name in KNOWN_MOUNTS:
        path = os.path.join(HOST_MNT_DIR, name)
        entry = {"mount": name, "path": path}
        if not os.path.exists(path):
            entry["status"] = "missing"
        else:
            try:
                os.listdir(path)
                entry["status"] = "healthy"
            except OSError as e:
                entry["status"] = f"stale: {e}"
        results.append(entry)
    unhealthy = [r for r in results if r["status"] != "healthy"]
    if not unhealthy:
        return {"message": "All known mounts resolve cleanly.", "mounts": results}
    return {
        "message": f"{len(unhealthy)} mount(s) not healthy: {', '.join(r['mount'] for r in unhealthy)}",
        "mounts": results,
    }


def perms_check() -> dict:
    """Config files that are root-owned and unreadable by group/other."""
    if not os.path.isdir(HOST_CONFIG_DIR):
        raise ServiceError(f"{HOST_CONFIG_DIR} not mounted.")
    unreadable = []
    for dirpath, _, filenames in os.walk(HOST_CONFIG_DIR, followlinks=False):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                mode = os.lstat(fp).st_mode
            except OSError:
                continue
            if not (mode & 0o044):
                unreadable.append(fp.replace(HOST_CONFIG_DIR, "config", 1))
    if not unreadable:
        return {"message": "No config files found unreadable by group/other.", "files": []}
    return {
        "message": f"{len(unreadable)} file(s) unreadable by group/other (won't be backed up):",
        "files": unreadable[:200],
    }


def image_check() -> dict:
    """For every running container's image, check if a newer digest exists."""
    me, containers = project_containers()
    results = []
    for c in containers:
        if c.id == me.id:
            continue
        try:
            image_tags = c.image.tags
            if not image_tags:
                continue
            tag_ref = image_tags[0]
            current_digests = set(c.image.attrs.get("RepoDigests", []))
            registry_data = docker_client.images.get_registry_data(tag_ref)
            remote_digest = registry_data.attrs.get("Descriptor", {}).get("digest")
            has_update = bool(remote_digest) and not any(remote_digest in d for d in current_digests)
            results.append({"name": c.name, "image": tag_ref, "update_available": has_update})
        except Exception as e:
            try:
                tag_ref = c.image.tags[0] if c.image.tags else ""
            except Exception:
                tag_ref = ""
            results.append({"name": c.name, "image": tag_ref, "update_available": None, "error": str(e)})
    updates = [r["name"] for r in results if r.get("update_available")]
    msg = f"{len(updates)} image(s) with a newer digest available: {', '.join(updates)}" if updates else \
          "No newer digests found for any currently-pinned tag (or all checks failed - see errors)."
    return {"message": msg, "images": results}
