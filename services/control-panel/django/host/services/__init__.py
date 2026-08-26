"""Host/fleet status + settings + diagnostics — backward-compatible re-export hub.

This module re-exports every symbol that callers previously imported from
here, but the implementations now live in focused sub-modules:

  host.services.container  — get_status, list_containers, restart/stop/start,
                             stream_container_logs, restart_all
  host.services.diagnostics — resource_check, disk_health, host_resources,
                              oom_check, disk_usage, mount_health, perms_check,
                              image_check
  host.services.maintenance — get_settings, patch_settings, prune_disk,
                              log_levels, reset_log_levels, notify_test, stack_top
  host.services.info       — get_version, docs_readme

New code should import directly from the focused sub-modules. This file
exists only so existing callers don't break.
"""

# --- container lifecycle ---
from host.services.container import (  # noqa: F401
    get_status,
    list_containers,
    restart_all,
    restart_container,
    start_container,
    stop_container,
    stream_container_logs,
)

# --- diagnostics ---
from host.services.diagnostics import (  # noqa: F401
    disk_health,
    disk_usage,
    host_resources,
    image_check,
    mount_health,
    oom_check,
    perms_check,
    resource_check,
)

# --- maintenance ---
from host.services.maintenance import (  # noqa: F401
    get_settings,
    log_levels,
    notify_test,
    patch_settings,
    prune_disk,
    reset_log_levels,
    stack_top,
)

# --- info ---
from host.services.info import (  # noqa: F401
    docs_readme,
    get_version,
)
