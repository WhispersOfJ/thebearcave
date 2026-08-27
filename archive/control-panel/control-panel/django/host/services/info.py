"""Host information — version, README docs.

Extracted from host/services.py. Read-only informational endpoints.
"""
import os
import re

from core.api_base import ServiceError
from core.docker_client import project_containers
from core.host_paths import HOST_README


def get_version() -> dict:
    """Current version from README's own declared line, plus a live
    container count."""
    declared = "unknown"
    if os.path.isfile(HOST_README):
        with open(HOST_README) as f:
            for line in f:
                m = re.match(r"Current version: \*\*(v[\d.]+)\*\*", line)
                if m:
                    declared = m.group(1)
                    break
    me, containers = project_containers()
    running = sum(1 for c in containers if c.status == "running")
    total = len(containers)
    return {
        "message": f"README declares {declared}. {running}/{total} containers currently running.",
        "version": declared, "running": running, "total": total,
    }


def docs_readme() -> str:
    """Raw text of this stack's own README.md."""
    if not os.path.isfile(HOST_README):
        raise ServiceError("README.md not mounted at /host-README.md.")
    with open(HOST_README) as f:
        return f.read()
