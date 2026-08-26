"""Host/fleet routes - status, container management, settings, diagnostics.
Ported from control-panel/services/host/router.py.

Auth split, matching the FastAPI-era source exactly:
- patch_settings (PATCH /api/v2/host/settings) and prune_disk
  (POST /api/v2/host/disk-health/prune) are IsAuthenticatedSessionOnly
  (admin, session-cookie-only) - the only two current_user-tier routes in
  the source's 24.
- Every other route is the default EnvelopeAPIView tier
  (IsAuthenticatedOrServiceKey) - the FastAPI-era current_user_or_service
  dependency, including the mutating container routes (restart/stop/start,
  restart-all), which stack-container.fish/stack-restart-all.fish call
  unattended via __stack_api's service key.

The container-logs stream view is NOT an EnvelopeAPIView (SSE isn't a JSON
envelope response) - it reuses posters.api.sse.sse_response, the same
helper the posters app's three stream views use, and picks up the default
auth pair from REST_FRAMEWORK settings like the posters stream views do.
"""
import os
import socket
import ssl

from rest_framework.views import APIView

from core.api_base import ConfirmMixin, EnvelopeAPIView, ServiceError
from core.permissions import IsAuthenticatedOrServiceKey, IsAuthenticatedSessionOnly
from host import services
from host.api.serializers import (
    LogsStreamQuerySerializer,
    PruneRequestSerializer,
    RestartQuerySerializer,
    SettingsPatchSerializer,
    TopQuerySerializer,
)


def sse_response(generator):
    """Create an SSE StreamingHttpResponse from a generator."""
    from django.http import StreamingHttpResponse
    response = StreamingHttpResponse(generator, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


class StatusView(EnvelopeAPIView):
    """GET /api/v2/host/status - every container's state + health."""

    def get(self, request):
        result = services.get_status()
        return self.ok(f"{len(result)} container(s).", containers=result)


class ContainersView(EnvelopeAPIView):
    """GET /api/v2/host/containers - full container grid with stats."""

    def get(self, request):
        items = services.list_containers()
        return self.ok(f"{len(items)} container(s).", items=items)


class ContainerRestartView(EnvelopeAPIView):
    """POST /api/v2/host/container/<name>/restart?activated=..."""

    def post(self, request, name):
        query = RestartQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        message = services.restart_container(name, query.validated_data["activated"])
        return self.ok(message)


class ContainerStopView(EnvelopeAPIView):
    """POST /api/v2/host/container/<name>/stop"""

    def post(self, request, name):
        message = services.stop_container(name)
        return self.ok(message)


class ContainerStartView(EnvelopeAPIView):
    """POST /api/v2/host/container/<name>/start"""

    def post(self, request, name):
        message = services.start_container(name)
        return self.ok(message)


class ContainerLogsStreamView(APIView):
    """GET /api/v2/host/container/<name>/logs/stream?tail=..."""

    def get(self, request, name):
        query = LogsStreamQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        generator = services.stream_container_logs(name, query.validated_data["tail"])
        return sse_response(generator)


class RestartAllView(EnvelopeAPIView):
    """POST /api/v2/host/stack/restart-all"""

    def post(self, request):
        message = services.restart_all()
        return self.ok(message)


class SettingsView(EnvelopeAPIView):
    """GET /api/v2/host/settings - every saved setting (default tier).

    PATCH /api/v2/host/settings - update settings; session-only (admin
    action, the FastAPI-era current_user dependency). The two methods
    share one URL, so the permission split is per-method rather than
    per-view: get_permissions() returns IsAuthenticatedSessionOnly for
    PATCH and the default pair for GET."""

    def get_permissions(self):
        if self.request and self.request.method == "PATCH":
            return [IsAuthenticatedSessionOnly()]
        return [IsAuthenticatedOrServiceKey()]

    def get(self, request):
        result = services.get_settings()
        return self.ok("Settings fetched.", **result)

    def patch(self, request):
        body = SettingsPatchSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        patch = {k: v for k, v in body.validated_data.items() if v is not None}
        result = services.patch_settings(patch)
        return self.ok("Settings updated.", **result)


class ResourceCheckView(EnvelopeAPIView):
    """GET /api/v2/host/resource-check"""

    def get(self, request):
        result = services.resource_check()
        message = result.pop("message")
        return self.ok(message, **result)


class DiskHealthView(EnvelopeAPIView):
    """GET /api/v2/host/disk-health"""

    def get(self, request):
        result = services.disk_health()
        message = result.pop("message")
        return self.ok(message, **result)


class PruneDiskView(ConfirmMixin, EnvelopeAPIView):
    """POST /api/v2/host/disk-health/prune - session-only (admin action),
    requires confirm=true in the body (checked before services is called,
    matching the FastAPI-era router's payload.confirm gate)."""

    permission_classes = [IsAuthenticatedSessionOnly]

    def post(self, request):
        self.check_confirm(request, PruneRequestSerializer)
        message = services.prune_disk()
        return self.ok(message)


class HostResourcesView(EnvelopeAPIView):
    """GET /api/v2/host/host-resources"""

    def get(self, request):
        result = services.host_resources()
        message = result.pop("message")
        return self.ok(message, **result)


class LogLevelsView(EnvelopeAPIView):
    """GET /api/v2/host/log-levels"""

    def get(self, request):
        result = services.log_levels()
        message = result.pop("message")
        return self.ok(message, **result)


class ResetLogLevelsView(EnvelopeAPIView):
    """POST /api/v2/host/log-levels/reset

    Resets all debug-logging apps back to info level. Uses the default
    IsAuthenticatedOrServiceKey permission (not session-only) — this is a
    maintenance action, not irreversible like host reboot."""

    def post(self, request):
        message = services.reset_log_levels()
        return self.ok(message)


class OomCheckView(EnvelopeAPIView):
    """GET /api/v2/host/oom-check"""

    def get(self, request):
        result = services.oom_check()
        message = result.pop("message")
        return self.ok(message, **result)


class DiskUsageView(EnvelopeAPIView):
    """GET /api/v2/host/disk-usage"""

    def get(self, request):
        result = services.disk_usage()
        message = result.pop("message")
        return self.ok(message, **result)


class MountHealthView(EnvelopeAPIView):
    """GET /api/v2/host/mount-health"""

    def get(self, request):
        result = services.mount_health()
        message = result.pop("message")
        return self.ok(message, **result)


class PermsCheckView(EnvelopeAPIView):
    """GET /api/v2/host/perms-check"""

    def get(self, request):
        result = services.perms_check()
        message = result.pop("message")
        return self.ok(message, **result)


class ImageCheckView(EnvelopeAPIView):
    """GET /api/v2/host/image-check"""

    def get(self, request):
        result = services.image_check()
        message = result.pop("message")
        return self.ok(message, **result)


class VersionView(EnvelopeAPIView):
    """GET /api/v2/host/version"""

    def get(self, request):
        result = services.get_version()
        message = result.pop("message")
        return self.ok(message, **result)


class DocsReadmeView(EnvelopeAPIView):
    """GET /api/v2/host/docs/readme"""

    def get(self, request):
        text = services.docs_readme()
        return self.ok("README.md", text=text)


class NotifyTestView(EnvelopeAPIView):
    """POST /api/v2/host/notify/test

    Sends a test notification to the configured Discord webhook. Uses the
    default IsAuthenticatedOrServiceKey permission (not session-only) —
    harmless, idempotent, useful for automation health checks."""

    def post(self, request):
        message = services.notify_test()
        return self.ok(message)


class TopView(EnvelopeAPIView):
    """GET /api/v2/host/top?by=cpu|mem&limit=..."""

    def get(self, request):
        query = TopQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        result = services.stack_top(query.validated_data["by"], query.validated_data["limit"])
        message = result.pop("message")
        return self.ok(message, **result)


class TlsCertView(EnvelopeAPIView):
    """GET /api/v2/host/tls - verify the served HTTPS cert against the local CA.

    Public endpoint (no auth) so the landing page can render a live
    cert-trust badge. Performs a real TLS handshake with the traefik HTTPS
    endpoint using config/ca/rootCA.pem (mounted at /host-config/ca/rootCA.pem)
    as a trust anchor. A successful handshake means the served cert is
    signed by the local CA, so devices that trust rootCA.pem get no browser
    warning; an SSLCertVerificationError means Traefik is serving its default
    self-signed cert (or the CA is out of sync). Note: create_default_context
    adds the CA to the system trust store rather than replacing it — external
    HTTPS calls (TMDB, indexers) are unaffected.
    """

    permission_classes = []  # AllowAny - read-only diagnostic

    def get(self, request):
        host_ip = os.environ.get("HOST_IP", "") or "192.168.4.20"
        ca_file = "/host-config/ca/rootCA.pem"
        hostname = f"bearcave.{host_ip}.nip.io"

        if not os.path.exists(ca_file):
            return self.ok(
                "Local CA not mounted in the control panel.",
                trusted=False,
                issuer=None,
                error="rootCA.pem missing at /host-config/ca/rootCA.pem (run scripts/trust-ca.sh)",
            )

        ctx = ssl.create_default_context(cafile=ca_file)
        try:
            with socket.create_connection((host_ip, 443), timeout=5) as raw:
                with ctx.wrap_socket(raw, server_hostname=hostname) as tls:
                    cert = tls.getpeercert()
                    issuer = dict(entry[0] for entry in cert.get("issuer", []))
        except ssl.SSLCertVerificationError as exc:
            return self.ok(
                "Served certificate does not validate against the local CA.",
                trusted=False,
                issuer=None,
                error=str(exc),
            )
        except OSError as exc:
            return self.ok(
                "Could not reach the HTTPS endpoint.",
                trusted=False,
                issuer=None,
                error=f"{type(exc).__name__}: {exc}",
            )

        return self.ok(
            "Served certificate validates against the local CA.",
            trusted=True,
            issuer=issuer.get("commonName") or issuer.get("organizationName"),
            error=None,
        )


class HealthCheckView(EnvelopeAPIView):
    """GET /api/v2/host/health - check all service health endpoints.

    Returns a dict mapping service name to {status: "up"|"down", code: int}.
    Health check list is derived from service-registry.json (the landing
    page's single source of truth) — adding a new service to the landing
    page automatically adds it here. Public endpoint (no auth) so the
    landing page can poll it.
    """

    permission_classes = []  # AllowAny - read-only status check

    def get(self, request):
        import concurrent.futures

        import httpx

        from host.services.health import build_health_check_list

        services_to_check, docker_services = build_health_check_list()

        def check_one(svc):
            try:
                with httpx.Client(timeout=svc["timeout"], follow_redirects=True) as client:
                    r = client.get(svc["url"], headers=svc.get("headers", {}))
                    return svc["name"], {"status": "up" if r.status_code < 400 else "down", "code": r.status_code}
            except Exception:
                return svc["name"], {"status": "down", "code": 0}

        result = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for name, info in pool.map(check_one, services_to_check):
                result[name] = info

        # Docker container checks for services without HTTP health endpoints
        try:
            from core.docker_client import project_containers
            _, containers = project_containers()
            container_map = {c.name: c for c in containers}
            for svc in docker_services:
                c = container_map.get(svc["container"])
                if c and c.status == "running":
                    result[svc["name"]] = {"status": "up", "code": 200}
                else:
                    result[svc["name"]] = {"status": "down", "code": 0}
        except Exception:
            for svc in docker_services:
                if svc["name"] not in result:
                    result[svc["name"]] = {"status": "down", "code": 0}

        response = self.ok(f"{sum(1 for v in result.values() if v['status'] == 'up')}/{len(result)} services up", services=result)
        response["Access-Control-Allow-Origin"] = "*"
        return response
