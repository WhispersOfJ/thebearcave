"""Tests for host.services.health — the registry-derived health check list."""
import json
import os
from unittest.mock import patch

import pytest

from host.services.health import build_health_check_list


def _write_registry(tmp_path, services):
    """Write a minimal service-registry.json to tmp_path."""
    registry = {"categories": {}, "services": services}
    path = tmp_path / "service-registry.json"
    path.write_text(json.dumps(registry))
    return path


class TestBuildHealthCheckList:
    def test_returns_http_and_docker_checks(self, tmp_path):
        registry_path = _write_registry(tmp_path, {
            "radarr": {
                "name": "Radarr",
                "health": {"type": "http", "url": "http://radarr:7878/ping"},
                "port": 7878,
            },
            "unpackerr": {
                "name": "Unpackerr",
                "health": {"type": "none"},
                "port": None,
            },
        })
        with patch("host.services.health._REGISTRY_PATH", str(registry_path)):
            http_checks, docker_checks = build_health_check_list()

        assert len(http_checks) == 1
        assert http_checks[0]["name"] == "Radarr"
        assert len(docker_checks) == 1
        assert docker_checks[0]["name"] == "Unpackerr"
        assert docker_checks[0]["container"] == "unpackerr"

    def test_api_overrides_used_for_known_services(self, tmp_path):
        registry_path = _write_registry(tmp_path, {
            "radarr": {
                "name": "Radarr",
                "health": {"type": "http", "url": "http://radarr:7878/ping"},
                "port": 7878,
            },
        })
        with patch("host.services.health._REGISTRY_PATH", str(registry_path)):
            http_checks, _ = build_health_check_list()

        # radarr is in _api_overrides, so the override URL is used
        assert "system/status" in http_checks[0]["url"]
        assert "X-Api-Key" in http_checks[0]["headers"]

    def test_missing_registry_returns_empty(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent.json")
        with patch("host.services.health._REGISTRY_PATH", fake_path):
            http_checks, docker_checks = build_health_check_list()
        assert http_checks == []
        assert docker_checks == []

    def test_all_22_services_covered(self):
        """Verify the real registry produces checks for all 22 services."""
        http_checks, docker_checks = build_health_check_list()
        total = len(http_checks) + len(docker_checks)
        assert total == 22

    def test_service_names_match_registry(self, tmp_path):
        registry_path = _write_registry(tmp_path, {
            "my-service": {
                "name": "My Service",
                "health": {"type": "http", "url": "http://my-service:8080/health"},
                "port": 8080,
            },
        })
        with patch("host.services.health._REGISTRY_PATH", str(registry_path)):
            http_checks, _ = build_health_check_list()
        assert http_checks[0]["name"] == "My Service"
