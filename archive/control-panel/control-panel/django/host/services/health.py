"""Health check list derived from service-registry.json.

Instead of hardcoding service URLs in HealthCheckView, this module reads
the canonical registry and builds the check list. Adding a new service
to the landing page automatically adds it to the health check — no need
to update two places.
"""
import json
import os

# Path to the landing page's service registry (the single source of truth)
_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "services", "landing-page", "service-registry.json"
)


def _load_registry() -> dict:
    with open(_REGISTRY_PATH) as f:
        return json.load(f)


def _http_check(name: str, url: str, timeout: int = 2, headers: dict | None = None) -> dict:
    entry = {"name": name, "url": url, "timeout": timeout}
    if headers:
        entry["headers"] = headers
    return entry


def _docker_check(name: str, container: str) -> dict:
    return {"name": name, "container": container}


def build_health_check_list() -> tuple[list[dict], list[dict]]:
    """Build (http_checks, docker_checks) from the service registry.

    HTTP checks use the registry's health.url where available.
    Docker checks are for services with health.type=="none" (no HTTP
    health endpoint — check container state instead).

    Some services need special handling (API keys, non-standard ports)
    that the registry doesn't encode, so we overlay those here.
    """
    try:
        registry = _load_registry()
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback to empty if registry is unavailable
        return [], []

    services = registry.get("services", {})
    http_checks = []
    docker_checks = []

    # Services that need API keys or special URL construction
    # (not derivable from the registry alone)
    _api_overrides = _build_api_overrides()

    for key, svc in services.items():
        name = svc["name"]
        health = svc.get("health", {})
        health_type = health.get("type", "none")

        if health_type == "http" and key in _api_overrides:
            # Use the override (adds API keys, fixes URLs for internal services)
            override = _api_overrides[key]
            http_checks.append(_http_check(name, override["url"],
                                           timeout=override.get("timeout", 3),
                                           headers=override.get("headers")))
        elif health_type == "http":
            # Use the registry URL directly
            url = health.get("url", "")
            # Registry URLs use container hostnames — they work on the bearcave network
            http_checks.append(_http_check(name, url, timeout=2))
        else:
            # No HTTP health endpoint — check Docker container state
            docker_checks.append(_docker_check(name, key))

    return http_checks, docker_checks


def _build_api_overrides() -> dict:
    """Health check overrides for services that need API keys or have
    non-standard health endpoints not captured in the registry."""
    from core.arr_client import ARR_APPS, PROWLARR_CFG
    from core.nzbdav_client import NZBDAV_API_KEY, NZBDAV_URL
    from core.plex_client import PLEX_URL

    nzbdav_key = f"&apikey={NZBDAV_API_KEY}" if NZBDAV_API_KEY else ""

    return {
        "plex": {
            "url": f"{PLEX_URL}/identity" if PLEX_URL else "http://127.0.0.1:9/",
            "timeout": 3,
        },
        "radarr": {
            "url": f"{ARR_APPS['radarr']['url']}/api/v3/system/status",
            "headers": {"X-Api-Key": ARR_APPS["radarr"]["key"]},
            "timeout": 3,
        },
        "sonarr": {
            "url": f"{ARR_APPS['sonarr']['url']}/api/v3/system/status",
            "headers": {"X-Api-Key": ARR_APPS["sonarr"]["key"]},
            "timeout": 3,
        },
        "prowlarr": {
            "url": f"{PROWLARR_CFG['url']}/api/v1/system/status",
            "headers": {"X-Api-Key": PROWLARR_CFG["key"]},
            "timeout": 3,
        },
        "nzbdav": {
            "url": f"{NZBDAV_URL}?mode=get_cats&output=json{nzbdav_key}",
            "timeout": 3,
        },
        "seerr": {
            "url": "http://seerr:5055/api/v1/status",
            "timeout": 3,
        },
        "arr-dashboard": {
            "url": "http://arr-dashboard:3000/health",
            "timeout": 3,
        },
        "traefik": {
            # Traefik has no dedicated /health endpoint but is reachable on :80
            "url": "http://traefik:80/",
            "timeout": 2,
        },
    }
