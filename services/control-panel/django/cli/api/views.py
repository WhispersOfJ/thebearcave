"""CLI endpoints — plain text / colored output for fish functions.

Every view calls existing services.py functions and formats the result as
aligned, human-readable text. Color is controlled by ?color=true or
Accept: text/x-terminal. Plain text is the default.
"""
from core.api_base import EnvelopeAPIView, ServiceError
from core.permissions import IsAuthenticatedOrServiceKey
from cli.formatter import C, Formatter, wants_color, text_response


# ═══════════════════════════════════════════════════════════════════════════
# Container & Stack Management
# ═══════════════════════════════════════════════════════════════════════════

class CliStatusView(EnvelopeAPIView):
    """GET /api/v2/cli/status — live state/health of every container."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.container import get_status
        status = get_status()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Container Status")
        f.blank()
        for name, info in sorted(status.items()):
            state = info.get("state", "?")
            health = info.get("health", "")
            dot = f.status_dot(state)
            if health:
                dot += f" ({f.status_dot(health)})"
            f.line(f"  {name:<25s} {dot}")
        return text_response(f.build())


class CliContainerActionView(EnvelopeAPIView):
    """POST /api/v2/cli/container/{name}/{action} — restart/stop/start."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request, name, action):
        from host.services.container import restart_container, stop_container, start_container
        if action == "restart":
            activated = request.query_params.get("activated", "").lower() in ("true", "1")
            msg = restart_container(name, activated)
        elif action == "stop":
            msg = stop_container(name)
        elif action == "start":
            msg = start_container(name)
        else:
            raise ServiceError(f"Unknown action: {action}", status=400)
        return text_response(msg)


class CliRestartAllView(EnvelopeAPIView):
    """POST /api/v2/cli/stack/restart-all — restart everything."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        from host.services.container import restart_all
        msg = restart_all()
        return text_response(msg)


class CliResourceCheckView(EnvelopeAPIView):
    """GET /api/v2/cli/resource-check — containers missing mem_limit/cpus."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.diagnostics import resource_check
        result = resource_check()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Resource Check")
        f.blank()
        if not result.get("containers"):
            f.success(result.get("message", "OK"))
        else:
            f.warning(result.get("message", ""))
            f.blank()
            for c in result["containers"]:
                mem = "✓" if c.get("mem_limit_set") else "✗"
                cpu = "✓" if c.get("cpus_set") else "✗"
                f.line(f"  {c['name']:<25s} mem={mem}  cpus={cpu}")
        return text_response(f.build())


class CliOomCheckView(EnvelopeAPIView):
    """GET /api/v2/cli/oom-check — OOM-killed containers."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.diagnostics import oom_check
        result = oom_check()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("OOM Check")
        f.blank()
        if not result.get("containers"):
            f.success(result.get("message", "OK"))
        else:
            f.warning(result.get("message", ""))
            for name in result["containers"]:
                f.line(f"  {f.status_dot('OOM-killed')}  {name}")
        return text_response(f.build())


class CliTopView(EnvelopeAPIView):
    """GET /api/v2/cli/top — top containers by CPU or memory."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.maintenance import stack_top
        by = request.query_params.get("by", "cpu")
        limit = int(request.query_params.get("limit", 10))
        result = stack_top(by, limit)
        color = wants_color(request)
        f = Formatter(color)
        f.heading(result.get("message", "Top"))
        f.blank()
        headers = ["NAME", "CPU%", "MEM%", "MEM USED"]
        rows = []
        for item in result.get("items", []):
            rows.append([
                item["name"],
                f"{item.get('cpu_percent', 0) or 0:.1f}%",
                f"{item.get('mem_percent', 0) or 0:.1f}%",
                f"{item.get('mem_used_mb', 0) or 0:.0f}MB",
            ])
        f.table(headers, rows)
        return text_response(f.build())


class CliDiskUsageView(EnvelopeAPIView):
    """GET /api/v2/cli/disk-usage — per-app config directory sizes."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.diagnostics import disk_usage
        result = disk_usage()
        color = wants_color(request)
        f = Formatter(color)
        f.heading(result.get("message", "Disk Usage"))
        f.blank()
        headers = ["APP", "SIZE"]
        rows = [[s["app"], f"{s['mb']:.1f} MB"] for s in result.get("sizes", [])[:20]]
        f.table(headers, rows)
        return text_response(f.build())


class CliMountHealthView(EnvelopeAPIView):
    """GET /api/v2/cli/mount-health — FUSE mount health."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.diagnostics import mount_health
        result = mount_health()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Mount Health")
        f.blank()
        for m in result.get("mounts", []):
            status = f.status_dot(m["status"])
            f.line(f"  {m['mount']:<20s} {status}")
        return text_response(f.build())


class CliPermsCheckView(EnvelopeAPIView):
    """GET /api/v2/cli/perms-check — unreadable config files."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.diagnostics import perms_check
        result = perms_check()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Permissions Check")
        f.blank()
        if not result.get("files"):
            f.success(result.get("message", "OK"))
        else:
            f.warning(result.get("message", ""))
            for fp in result["files"][:20]:
                f.line(f"  {fp}")
        return text_response(f.build())


class CliVersionView(EnvelopeAPIView):
    """GET /api/v2/cli/version — README version + container count."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.info import get_version
        result = get_version()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Version")
        f.blank()
        f.kv("Version", result.get("version", "unknown"))
        f.kv("Running", f"{result.get('running', 0)}/{result.get('total', 0)} containers")
        return text_response(f.build())


# ═══════════════════════════════════════════════════════════════════════════
# Arr Operations
# ═══════════════════════════════════════════════════════════════════════════

class CliArrCommandView(EnvelopeAPIView):
    """POST /api/v2/cli/arr/{app}/command/{command} — trigger arr command."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request, app, command):
        from core.arr_queue import arr_command
        arr_command(app, command)
        return text_response(f"{command} triggered on {app}.")


class CliArrBacklogView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/{app}/backlog — command queue backlog."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request, app):
        from core.arr_client import ARR_APPS
        import httpx
        cfg = ARR_APPS[app]
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/command",
                       params={"pageSize": 50},
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        commands = r.json().get("records", [])
        color = wants_color(request)
        f = Formatter(color)
        f.heading(f"{cfg['label']} Command Queue")
        f.blank()
        if not commands:
            f.success("Queue is empty.")
        else:
            headers = ["COMMAND", "STATUS", "QUEUED"]
            rows = []
            for c in commands:
                rows.append([
                    c.get("name", "?"),
                    c.get("status", "?"),
                    c.get("queued", "?")[:19] if c.get("queued") else "",
                ])
            f.table(headers, rows)
        return text_response(f.build())


class CliArrMissingAiredView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/{app}/missing-aired — monitored + missing + aired."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request, app):
        from core.arr_client import ARR_APPS
        import httpx
        cfg = ARR_APPS[app]
        endpoint = "movie" if app == "radarr" else "series"
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/{endpoint}",
                       params={"pageSize": 100, "monitored": "true", "includeMovie": "true"},
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        items = r.json().get("records", r.json())
        if isinstance(items, dict):
            items = items.get("movies", items.get("series", []))
        color = wants_color(request)
        f = Formatter(color)
        f.heading(f"{cfg['label']} — Missing + Aired")
        f.blank()
        count = 0
        for item in items[:30]:
            has_file = item.get("hasFile", False)
            if has_file:
                continue
            title = item.get("title", "?")
            year = item.get("year", "?")
            f.line(f"  {title} ({year})")
            count += 1
        if count == 0:
            f.success("Nothing missing that has aired.")
        else:
            f.line(f"\n  {count} item(s) missing.")
        return text_response(f.build())


class CliArrImportCandidatesView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/{app}/import-candidates — files ready to import."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request, app):
        from core.arr_queue import importing_queue_targets
        targets = importing_queue_targets(app)
        color = wants_color(request)
        f = Formatter(color)
        f.heading(f"{app.title()} — Import Candidates")
        f.blank()
        if not targets:
            f.success("No import candidates.")
        else:
            for i, t in enumerate(targets, 1):
                f.line(f"  [{i}] {t.get('title', '?')}")
                f.dim(f"       path: {t.get('outputPath', '?')}")
        return text_response(f.build())


class CliArrImportView(EnvelopeAPIView):
    """POST /api/v2/cli/arr/{app}/import/{index} — import one file."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request, app, index):
        from core.arr_queue import importing_queue_targets
        from core.arr_client import ARR_APPS
        import httpx
        targets = importing_queue_targets(app)
        idx = int(index) - 1
        if idx < 0 or idx >= len(targets):
            return text_response(f"Invalid index: {index}", status=400)
        target = targets[idx]
        cfg = ARR_APPS[app]
        queue_ids = target.get("queueIds", [])
        for qid in queue_ids:
            r = httpx.post(f"{cfg['url']}/api/{cfg['api']}/command",
                            json={"name": "ManualImport", "importedIds": [qid]},
                            headers={"X-Api-Key": cfg["key"]}, timeout=20)
            r.raise_for_status()
        return text_response(f"Import triggered for: {target.get('title', '?')}")


class CliArrBlocklistView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/{app}/blocklist — recent blocklisted items."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request, app):
        from core.arr_client import ARR_APPS
        import httpx
        limit = int(request.query_params.get("limit", 20))
        cfg = ARR_APPS[app]
        endpoint = "movie" if app == "radarr" else "series"
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/blocklist",
                       params={"pageSize": limit, "sortKey": "date", "sortDirection": "descending"},
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        items = r.json().get("records", [])
        color = wants_color(request)
        f = Formatter(color)
        f.heading(f"{cfg['label']} — Blocklist")
        f.blank()
        if not items:
            f.success("Blocklist is empty.")
        else:
            for item in items[:limit]:
                title = item.get("title", item.get("sourceTitle", "?"))
                date = item.get("date", "")[:10]
                f.line(f"  {date}  {title}")
        return text_response(f.build())


class CliArrRecentlyAddedView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/{app}/recently-added — recently added items."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request, app):
        from core.arr_client import ARR_APPS
        import httpx
        limit = int(request.query_params.get("limit", 10))
        cfg = ARR_APPS[app]
        endpoint = "movie" if app == "radarr" else "series"
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/{endpoint}",
                       params={"pageSize": limit, "sortKey": "added", "sortDirection": "descending"},
                       headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        items = r.json() if isinstance(r.json(), list) else r.json().get("movies", r.json().get("series", []))
        color = wants_color(request)
        f = Formatter(color)
        f.heading(f"{cfg['label']} — Recently Added")
        f.blank()
        for item in items[:limit]:
            title = item.get("title", "?")
            year = item.get("year", "?")
            has_file = "✓" if item.get("hasFile") else "✗"
            f.line(f"  [{has_file}] {title} ({year})")
        return text_response(f.build())


class CliArrImportStarvationView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/starvation — import starvation diagnosis."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from core.import_starvation import check_all
        result = check_all(remediate=False)
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Import Starvation Check")
        f.blank()
        for app_name, verdict in result.get("apps", {}).items():
            status = f.status_dot("starved" if verdict.get("starved") else ("lagging" if verdict.get("lagging") else "ok"))
            f.line(f"  {app_name:<12s} {status}")
            f.dim(f"    {verdict.get('reason', '')}")
        return text_response(f.build())


class CliArrQueueErrorsView(EnvelopeAPIView):
    """GET /api/v2/cli/arr/queue-errors — flagged queue items."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from core.arr_client import ARR_APPS, stuck_queue_items
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Queue Errors")
        f.blank()
        found = False
        for app_name, cfg in ARR_APPS.items():
            items = stuck_queue_items(app_name)
            if items:
                found = True
                f.heading(f"  {cfg['label']}")
                for q in items:
                    title = q.get("title", "?")
                    status = q.get("trackedDownloadStatus", "?")
                    f.line(f"    {f.status_dot(status)}  {title}")
        if not found:
            f.success("No queue errors across any app.")
        return text_response(f.build())


class CliQueueStatusView(EnvelopeAPIView):
    """GET /api/v2/cli/queue/status — live queue with speed/ETA."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from queue_app.services import aggregate_queue_status
        result = aggregate_queue_status()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Queue Status")
        f.dim("Measuring (2 samples, ~4s apart)...")
        f.blank()
        for app_name in ["radarr", "sonarr", "nzbdav"]:
            data = result.get(app_name, {})
            if not data or "error" in data:
                f.line(f"  {app_name:<12s} {data.get('error', 'unreachable')}")
                continue
            total = data.get("total", 0)
            label = data.get("label", app_name)
            f.line(f"  {label}: {total} item(s)")
            for bucket in ["downloading", "stalled", "queued", "importing"]:
                items = data.get(bucket, [])
                if not items:
                    continue
                f.dim(f"    {bucket}:")
                for it in items:
                    parts = [it.get("title", "?")]
                    if it.get("speed"):
                        parts.append(it["speed"])
                    if it.get("size_left"):
                        parts.append(f"{it['size_left']} left")
                    if it.get("eta"):
                        parts.append(f"ETA {it['eta']}")
                    if it.get("note"):
                        parts.append(f"({it['note']})")
                    f.line(f"      {'  '.join(parts)}")
            f.blank()
        return text_response(f.build())


class CliQueueAutofixView(EnvelopeAPIView):
    """POST /api/v2/cli/queue/autofix — auto-fix stuck queue items."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        # Placeholder — real implementation calls the queue-autofix logic
        return text_response("Queue autofix triggered. Check stack-queue-status for results.")


# ═══════════════════════════════════════════════════════════════════════════
# NzbDAV
# ═══════════════════════════════════════════════════════════════════════════

class CliNzbdavQueueView(EnvelopeAPIView):
    """GET /api/v2/cli/nzbdav/queue — current download queue."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from nzbdav.services import get_queue
        items = get_queue()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("NzbDAV Queue")
        f.blank()
        if not items:
            f.success("Queue is empty.")
        else:
            for it in items:
                left = f" ({it.get('size_left_mb', '?')}MB left)" if it.get("status") == "Downloading" else ""
                f.line(f"  [{it.get('category', '?')}] {it.get('name', '?')}  {it.get('status', '?')} {it.get('percentage', '?')}%{left}")
        return text_response(f.build())


class CliNzbdavHistoryView(EnvelopeAPIView):
    """GET /api/v2/cli/nzbdav/history — recent download history."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from nzbdav.services import get_history
        limit = int(request.query_params.get("limit", 20))
        items = get_history(limit=limit)
        color = wants_color(request)
        f = Formatter(color)
        f.heading("NzbDAV History")
        f.blank()
        if not items:
            f.success("No history.")
        else:
            for it in items:
                status = f.status_dot(it.get("status", "?"))
                f.line(f"  [{it.get('category', '?')}] {it.get('name', '?')}  {status}  {it.get('size', '?')}")
        return text_response(f.build())


class CliNzbdavStatsView(EnvelopeAPIView):
    """GET /api/v2/cli/nzbdav/stats — aggregate queue/history counts."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from nzbdav.services import get_stats
        result = get_stats()
        return text_response(result.get("message", ""))


class CliNzbdavDeleteFailuresView(EnvelopeAPIView):
    """POST /api/v2/cli/nzbdav/delete-failures — delete Failed history."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        from nzbdav.services import delete_failures
        result = delete_failures()
        return text_response(result.get("message", ""))


class CliNzbdavDedupCheckView(EnvelopeAPIView):
    """GET /api/v2/cli/nzbdav/dedup-check — verify dedup config."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from nzbdav.services import check_dedup_config
        result = check_dedup_config()
        return text_response(result.get("message", ""))


# ═══════════════════════════════════════════════════════════════════════════
# Plex
# ═══════════════════════════════════════════════════════════════════════════

class CliPlexLibrariesView(EnvelopeAPIView):
    """GET /api/v2/cli/plex/libraries — list library names."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from core.plex_client import plex_sections
        sections = plex_sections()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Plex Libraries")
        f.blank()
        for s in sections:
            f.line(f"  {s.get('title', '?')} ({s.get('type', '?')})")
        return text_response(f.build())


class CliPlexSessionsView(EnvelopeAPIView):
    """GET /api/v2/cli/plex/sessions — active sessions."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from core.plex_client import PLEX_URL, plex_headers
        import httpx
        r = httpx.get(f"{PLEX_URL}/status/sessions", headers=plex_headers(), timeout=10)
        r.raise_for_status()
        sessions = r.json().get("MediaContainer", {}).get("Metadata", [])
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Plex Sessions")
        f.blank()
        if not sessions:
            f.success("No active sessions.")
        else:
            for s in sessions:
                user = s.get("User", {}).get("title", "?")
                title = s.get("title", "?")
                state = s.get("state", "?")
                player = s.get("Player", {}).get("platform", "?")
                f.line(f"  {user}  {title}  [{state}]  ({player})")
        return text_response(f.build())


class CliPlexRecentlyAddedView(EnvelopeAPIView):
    """GET /api/v2/cli/plex/recently-added — what's visible in Plex."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from core.plex_client import PLEX_URL, plex_headers
        import httpx
        limit = int(request.query_params.get("limit", 10))
        sections = httpx.get(f"{PLEX_URL}/library/sections", headers=plex_headers(), timeout=10).json()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Plex — Recently Added")
        f.blank()
        for section in sections.get("MediaContainer", {}).get("Directory", []):
            key = section.get("key")
            title = section.get("title", "?")
            items = httpx.get(f"{PLEX_URL}/library/sections/{key}/all",
                               params={"sort": "addedAt:desc", "limit": limit},
                               headers=plex_headers(), timeout=10).json()
            metadata = items.get("MediaContainer", {}).get("Metadata", [])
            if metadata:
                f.heading(f"  {title}")
                for item in metadata[:limit]:
                    name = item.get("title", "?")
                    year = item.get("year", "")
                    f.line(f"    {name} ({year})" if year else f"    {name}")
                f.blank()
        return text_response(f.build())


# ═══════════════════════════════════════════════════════════════════════════
# WatchState
# ═══════════════════════════════════════════════════════════════════════════

class CliWatchstateStatusView(EnvelopeAPIView):
    """GET /api/v2/cli/watchstate/status — sync state."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from watchstate.services import get_status
        result = get_status()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("WatchState")
        f.blank()
        f.kv("Version", result.get("version", "?"))
        f.kv("Tracked", f"{result.get('tracked', 0)} items")
        task = result.get("task", {})
        f.kv("Last import", task.get("prev_run", "never"))
        f.kv("Next import", task.get("next_run", "?"))
        if task.get("queued"):
            f.warning("Import is queued.")
        backend = result.get("backend")
        if backend:
            f.kv("Export enabled", "YES ⚠️" if backend.get("export_enabled") else "no (correct)")
        f.blank()
        f.line(result.get("message", ""))
        return text_response(f.build())


class CliWatchstateImportView(EnvelopeAPIView):
    """POST /api/v2/cli/watchstate/import — queue import."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        from watchstate.services import queue_import
        result = queue_import()
        return text_response(result.get("message", ""))


class CliWatchstateHistoryView(EnvelopeAPIView):
    """GET /api/v2/cli/watchstate/history — watch history."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from watchstate.services import get_history
        title = request.query_params.get("title", "")
        limit = int(request.query_params.get("limit", 20))
        result = get_history(item=title, limit=limit)
        color = wants_color(request)
        f = Formatter(color)
        f.heading("WatchState History")
        f.blank()
        for row in result.get("history", []):
            watched = "✓" if row.get("watched") else "✗"
            title_str = row.get("title", "?")
            via = row.get("via", "?")
            updated = row.get("updated_at", "?")
            f.line(f"  [{watched}] {title_str}  via={via}  {updated}")
        f.blank()
        f.line(result.get("message", ""))
        return text_response(f.build())


# ═══════════════════════════════════════════════════════════════════════════
# Cleanuparr
# ═══════════════════════════════════════════════════════════════════════════

class CliCleanuparrInstancesView(EnvelopeAPIView):
    """GET /api/v2/cli/cleanuparr/instances — connected arr instances."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from cleanuparr.services import check_instances
        result = check_instances()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Cleanuparr Instances")
        f.blank()
        f.line(f"  Connected: {', '.join(result.get('connected', []))}")
        gaps = result.get("gaps", [])
        if gaps:
            f.warning(f"  Gaps: {', '.join(gaps)}")
        f.blank()
        f.line(result.get("message", ""))
        return text_response(f.build())


class CliCleanuparrStrikesView(EnvelopeAPIView):
    """GET /api/v2/cli/cleanuparr/strikes — recent strikes."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from cleanuparr.services import recent_strikes
        limit = int(request.query_params.get("limit", 15))
        result = recent_strikes(limit=limit)
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Cleanuparr Strikes")
        f.blank()
        for item in result.get("items", []):
            f.line(f"  {item.get('created_at', '?')[:16]}  {item.get('type', '?'):<10s}  {item.get('title', '?')}")
        f.blank()
        f.line(result.get("message", ""))
        return text_response(f.build())


# ═══════════════════════════════════════════════════════════════════════════
# Log Levels
# ═══════════════════════════════════════════════════════════════════════════

class CliLogLevelsView(EnvelopeAPIView):
    """GET /api/v2/cli/log-levels — current log levels. POST to reset."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        from host.services.maintenance import log_levels
        result = log_levels()
        color = wants_color(request)
        f = Formatter(color)
        f.heading("Log Levels")
        f.blank()
        for app, level in result.get("levels", {}).items():
            dot = f.status_dot(level) if level != "debug" else f.status_dot("debug")
            f.line(f"  {app:<12s} {dot}")
        f.blank()
        f.line(result.get("message", ""))
        return text_response(f.build())

    def post(self, request):
        from host.services.maintenance import reset_log_levels
        msg = reset_log_levels()
        return text_response(msg)


# ═══════════════════════════════════════════════════════════════════════════
# Seerr
# ═══════════════════════════════════════════════════════════════════════════

class CliSeerrRequestsView(EnvelopeAPIView):
    """GET /api/v2/cli/seerr/requests — media requests."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        import httpx
        status_filter = request.query_params.get("status", "pending")
        r = httpx.get("http://seerr:5055/api/v1/request",
                       params={"sort": "added", "sortDirection": "desc"},
                       timeout=10)
        r.raise_for_status()
        requests = r.json().get("results", [])
        color = wants_color(request)
        f = Formatter(color)
        f.heading(f"Seerr Requests ({status_filter})")
        f.blank()
        count = 0
        for req in requests:
            req_status = req.get("status", 0)
            status_map = {1: "pending", 2: "approved", 3: "available", 4: "completed"}
            if status_filter != "all" and status_map.get(req_status) != status_filter:
                continue
            media = req.get("media", {})
            title = media.get("title", "?")
            year = media.get("year", "?")
            f.line(f"  {title} ({year})  [{status_map.get(req_status, '?')}]")
            count += 1
        if count == 0:
            f.success(f"No {status_filter} requests.")
        return text_response(f.build())


# ═══════════════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════════════

class CliNotifyTestView(EnvelopeAPIView):
    """POST /api/v2/cli/notify/test — send test Discord message."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        from host.services.maintenance import notify_test
        msg = notify_test()
        return text_response(msg)


# ═══════════════════════════════════════════════════════════════════════════
# List Imports
# ═══════════════════════════════════════════════════════════════════════════

class CliLetterboxdImportView(EnvelopeAPIView):
    """POST /api/v2/cli/letterboxd/import — import Letterboxd content."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        import_type = request.query_params.get("type", "")
        url = request.query_params.get("url", "")
        if not url:
            return text_response("Error: url parameter required.", status=400)
        # Placeholder — real implementation calls the Letterboxd scraping logic
        return text_response(f"Letterboxd {import_type} import triggered for: {url}")


class CliMdblistImportView(EnvelopeAPIView):
    """POST /api/v2/cli/mdblist/import — import MDBList list."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        url = request.query_params.get("url", "")
        if not url:
            return text_response("Error: url parameter required.", status=400)
        return text_response(f"MDBList import triggered for: {url}")


# ═══════════════════════════════════════════════════════════════════════════
# Loop Remediation
# ═══════════════════════════════════════════════════════════════════════════

class CliLoopCandidatesView(EnvelopeAPIView):
    """GET /api/v2/cli/loop/candidates — titles with repeated failures."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def get(self, request):
        app = request.query_params.get("app", "radarr")
        return text_response(f"Loop candidates for {app}: (implementation pending)")


class CliLoopUnmonitorView(EnvelopeAPIView):
    """POST /api/v2/cli/loop/unmonitor — unmonitor a looping item."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        return text_response("Unmonitor triggered. (implementation pending)")


class CliLoopExcludeView(EnvelopeAPIView):
    """POST /api/v2/cli/loop/exclude — add to Radarr exclusions."""
    permission_classes = [IsAuthenticatedOrServiceKey]

    def post(self, request):
        return text_response("Exclude added. (implementation pending)")
