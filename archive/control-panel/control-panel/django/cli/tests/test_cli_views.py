"""Tests for CLI endpoints — verify each returns plain text."""
import pytest
from unittest.mock import patch

_HDR = {"HTTP_HOST": "localhost", "REMOTE_ADDR": "127.0.0.1"}


@pytest.mark.django_db
def test_cli_status_returns_plain_text(authed_client):
    with patch("host.services.container.get_status", return_value={"radarr": {"state": "running", "health": "healthy"}}):
        response = authed_client.get("/api/v2/cli/status")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "radarr" in body
    assert "running" in body


@pytest.mark.django_db
def test_cli_status_color_flag(authed_client):
    with patch("host.services.container.get_status", return_value={"radarr": {"state": "running", "health": "healthy"}}):
        response = authed_client.get("/api/v2/cli/status?color=true")
    assert response.status_code == 200
    body = response.content.decode()
    # ANSI escape code for green
    assert "\033[32m" in body


@pytest.mark.django_db
def test_cli_version_returns_plain_text(authed_client):
    with patch("host.services.info.get_version", return_value={"version": "v1.0.0", "running": 10, "total": 12}):
        response = authed_client.get("/api/v2/cli/version")
    assert response.status_code == 200
    body = response.content.decode()
    assert "v1.0.0" in body
    assert "10/12" in body


@pytest.mark.django_db
def test_cli_oom_check_no_oom(authed_client):
    with patch("host.services.diagnostics.oom_check", return_value={"message": "No OOM kills.", "containers": []}):
        response = authed_client.get("/api/v2/cli/oom-check")
    assert response.status_code == 200
    body = response.content.decode()
    assert "No OOM" in body


@pytest.mark.django_db
def test_cli_nzbdav_queue_empty(authed_client):
    with patch("nzbdav.services.get_queue", return_value=[]):
        response = authed_client.get("/api/v2/cli/nzbdav/queue")
    assert response.status_code == 200
    body = response.content.decode()
    assert "empty" in body.lower()


@pytest.mark.django_db
def test_cli_log_levels_returns_text(authed_client):
    with patch("host.services.maintenance.log_levels", return_value={"message": "All info.", "levels": {"radarr": "info"}}):
        response = authed_client.get("/api/v2/cli/log-levels")
    assert response.status_code == 200
    body = response.content.decode()
    assert "radarr" in body
    assert "info" in body


@pytest.mark.django_db
def test_cli_watchstate_status(authed_client):
    with patch("watchstate.services.get_status", return_value={
        "version": "1.0", "tracked": 42,
        "task": {"prev_run": "2026-08-22", "next_run": "2026-08-23", "queued": False},
        "backend": {"export_enabled": False},
        "message": "Idle.",
    }):
        response = authed_client.get("/api/v2/cli/watchstate/status")
    assert response.status_code == 200
    body = response.content.decode()
    assert "42" in body
    assert "no (correct)" in body


@pytest.mark.django_db
def test_cli_cleanuparr_instances(authed_client):
    with patch("cleanuparr.services.check_instances", return_value={
        "message": "OK", "connected": ["radarr", "sonarr"], "gaps": []
    }):
        response = authed_client.get("/api/v2/cli/cleanuparr/instances")
    assert response.status_code == 200
    body = response.content.decode()
    assert "radarr" in body
    assert "sonarr" in body


@pytest.mark.django_db
def test_cli_container_action_restart(authed_client):
    with patch("host.services.container.restart_container", return_value="Radarr restarted."):
        response = authed_client.post("/api/v2/cli/container/radarr/restart", **_HDR)
    assert response.status_code == 200
    body = response.content.decode()
    assert "restarted" in body


@pytest.mark.django_db
def test_cli_notify_test(authed_client):
    with patch("host.services.maintenance.notify_test", return_value="Test notification sent."):
        response = authed_client.post("/api/v2/cli/notify/test", **_HDR)
    assert response.status_code == 200
    body = response.content.decode()
    assert "sent" in body


@pytest.mark.django_db
def test_cli_unauthenticated_rejects():
    from rest_framework.test import APIClient
    client = APIClient()
    response = client.get("/api/v2/cli/status", **_HDR)
    assert response.status_code in (401, 403)
