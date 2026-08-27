from unittest.mock import MagicMock, patch

import docker
import pytest

from catalog import services
from core.api_base import ServiceError


def _not_found(*_args, **_kwargs):
    raise docker.errors.NotFound("not found")


class TestListCatalog:
    def test_all_not_installed(self):
        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = _not_found
            result = services.list_catalog()

        assert result["message"] == f"{len(result['items'])} catalog entries, 0 installed."
        assert all(item["status"] == "not_installed" for item in result["items"])
        uptime_kuma = next(i for i in result["items"] if i["id"] == "uptime-kuma")
        assert uptime_kuma["image"] == "louislam/uptime-kuma:2"
        assert uptime_kuma["ports"] == [3050]

    def test_one_installed_and_running(self):
        running = MagicMock(status="running")

        def get_side_effect(name):
            if name == "catalog-uptime-kuma":
                return running
            raise _not_found()

        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = get_side_effect
            result = services.list_catalog()

        assert "1 installed." in result["message"]
        uptime_kuma = next(i for i in result["items"] if i["id"] == "uptime-kuma")
        assert uptime_kuma["status"] == "running"

    def test_installed_but_not_running_reports_raw_status(self):
        exited = MagicMock(status="exited")

        def get_side_effect(name):
            if name == "catalog-uptime-kuma":
                return exited
            raise _not_found()

        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = get_side_effect
            result = services.list_catalog()

        uptime_kuma = next(i for i in result["items"] if i["id"] == "uptime-kuma")
        assert uptime_kuma["status"] == "exited"


class TestGetStatus:
    def test_unknown_id_raises_404(self):
        with pytest.raises(ServiceError) as exc_info:
            services.get_status("not-a-real-entry")
        assert exc_info.value.status_code == 404

    def test_not_installed(self):
        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = _not_found
            result = services.get_status("uptime-kuma")

        assert result == {"message": "Not installed.", "status": "not_installed"}

    def test_installed_reports_status_and_health(self):
        container = MagicMock(status="running")
        container.attrs = {
            "State": {"Health": {"Status": "healthy"}, "StartedAt": "2026-08-22T00:00:00Z"}
        }

        def get_side_effect(name):
            if name == "catalog-uptime-kuma":
                return container
            raise _not_found()

        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = get_side_effect
            result = services.get_status("uptime-kuma")

        container.reload.assert_called_once()
        assert result["status"] == "running"
        assert result["health"] == "healthy"
        assert result["started_at"] == "2026-08-22T00:00:00Z"


class TestInstall:
    def test_unknown_id_raises_404(self):
        with pytest.raises(ServiceError) as exc_info:
            services.install("not-a-real-entry")
        assert exc_info.value.status_code == 404

    def test_already_installed_raises_409(self):
        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.return_value = MagicMock(status="running")
            with pytest.raises(ServiceError) as exc_info:
                services.install("uptime-kuma")

        assert exc_info.value.status_code == 409
        assert "already installed" in str(exc_info.value.detail)

    def test_port_conflict_raises_409_without_pulling(self):
        other = MagicMock(name="other")
        other.name = "some-other-container"
        other.attrs = {"HostConfig": {"PortBindings": {"3001/tcp": [{"HostPort": "3050"}]}}}

        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = _not_found
            mock_docker.containers.list.return_value = [other]
            with pytest.raises(ServiceError) as exc_info:
                services.install("uptime-kuma")

        assert exc_info.value.status_code == 409

    def test_success_pulls_image_and_runs_container(self):
        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_pull") as mock_pull, \
             patch("catalog.services.helper_run") as mock_run:
            mock_docker.containers.get.side_effect = _not_found
            mock_docker.containers.list.return_value = []
            mock_pull.return_value = "Pulled."
            mock_run.return_value = "Container started."
            result = services.install("uptime-kuma")

        mock_pull.assert_called_once_with("louislam/uptime-kuma", "2")
        mock_run.assert_called_once()
        run_kwargs = mock_run.call_args.kwargs
        assert run_kwargs["name"] == "catalog-uptime-kuma"
        assert run_kwargs["network"] == "bearcave"
        assert run_kwargs["labels"] == {"media-stack.catalog": "uptime-kuma"}
        assert result["ports"] == [3050]
        assert "installed and starting" in result["message"]

    def test_docker_sock_entry_mounts_socket_read_only(self):
        """dozzle has docker_sock=True and is not portainer, so the socket
        bind mode must be 'ro' (only 'portainer' gets 'rw')."""
        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_pull") as mock_pull, \
             patch("catalog.services.helper_run") as mock_run:
            mock_docker.containers.get.side_effect = _not_found
            mock_docker.containers.list.return_value = []
            mock_pull.return_value = "Pulled."
            mock_run.return_value = "Container started."
            services.install("dozzle")

        run_kwargs = mock_run.call_args.kwargs
        volumes = run_kwargs["volumes"]
        sock_vol = next(v for v in volumes if v["source"] == "/var/run/docker.sock")
        assert sock_vol["mode"] == "ro"

    def test_entry_caveat_is_appended_to_install_message(self):
        """beszel has a non-None caveat - install's message must include it,
        matching router.py's `if entry.get('caveat'): message += ...`."""
        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_pull") as mock_pull, \
             patch("catalog.services.helper_run") as mock_run:
            mock_docker.containers.get.side_effect = _not_found
            mock_docker.containers.list.return_value = []
            mock_pull.return_value = "Pulled."
            mock_run.return_value = "Container started."
            result = services.install("beszel")

        assert "Note:" in result["message"]
        assert "agent" in result["message"]

    def test_pull_failure_raises_service_error(self):
        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_pull") as mock_pull:
            mock_docker.containers.get.side_effect = _not_found
            mock_docker.containers.list.return_value = []
            mock_pull.side_effect = ServiceError("Failed to pull image")

            with pytest.raises(ServiceError) as exc_info:
                services.install("uptime-kuma")

        assert "Failed to pull" in str(exc_info.value.detail)

    def test_run_failure_raises_service_error(self):
        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_pull") as mock_pull, \
             patch("catalog.services.helper_run") as mock_run:
            mock_docker.containers.get.side_effect = _not_found
            mock_docker.containers.list.return_value = []
            mock_pull.return_value = "Pulled."
            mock_run.side_effect = ServiceError("Container failed to start")

            with pytest.raises(ServiceError) as exc_info:
                services.install("uptime-kuma")

        assert "failed to start" in str(exc_info.value.detail)


class TestRemove:
    def test_unknown_id_raises_404(self):
        with pytest.raises(ServiceError) as exc_info:
            services.remove("not-a-real-entry")
        assert exc_info.value.status_code == 404

    def test_not_installed_raises_404(self):
        with patch("catalog.services.docker_client") as mock_docker:
            mock_docker.containers.get.side_effect = _not_found
            with pytest.raises(ServiceError) as exc_info:
                services.remove("uptime-kuma")

        assert exc_info.value.status_code == 404
        assert "isn't installed" in str(exc_info.value.detail)

    def test_success_keeps_volumes_by_default(self):
        container = MagicMock()

        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_stop") as mock_stop, \
             patch("catalog.services.helper_remove") as mock_remove:
            mock_docker.containers.get.return_value = container
            mock_stop.return_value = "Stopped."
            mock_remove.return_value = "Removed."
            result = services.remove("uptime-kuma")

        mock_stop.assert_called_once_with("catalog-uptime-kuma", timeout=15)
        mock_remove.assert_called_once_with("catalog-uptime-kuma")
        assert "Data volume(s) kept" in result["message"]

    def test_success_removes_volumes_when_requested(self):
        container = MagicMock()

        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_stop") as mock_stop, \
             patch("catalog.services.helper_remove") as mock_remove, \
             patch("catalog.services.helper_remove_volume") as mock_rm_vol:
            mock_docker.containers.get.return_value = container
            mock_stop.return_value = "Stopped."
            mock_remove.return_value = "Removed."
            mock_rm_vol.return_value = "Removed."
            result = services.remove("uptime-kuma", remove_volumes=True)

        assert "Removed 1 volume(s)." in result["message"]

    def test_no_volumes_entry_has_no_volume_note(self):
        """dozzle has no volumes at all, so neither the 'kept' nor the
        'removed' note is appended - message is just '<name> removed.'"""
        container = MagicMock()

        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_stop") as mock_stop, \
             patch("catalog.services.helper_remove") as mock_remove:
            mock_docker.containers.get.return_value = container
            mock_stop.return_value = "Stopped."
            mock_remove.return_value = "Removed."
            result = services.remove("dozzle")

        assert result["message"] == "Dozzle removed."

    def test_stop_failure_raises_service_error(self):
        container = MagicMock()

        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_stop") as mock_stop:
            mock_docker.containers.get.return_value = container
            mock_stop.side_effect = ServiceError("Stop failed")
            with pytest.raises(ServiceError) as exc_info:
                services.remove("uptime-kuma")

        assert "Failed to remove" in str(exc_info.value.detail)

    def test_volume_not_found_is_skipped_silently(self):
        container = MagicMock()

        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_stop") as mock_stop, \
             patch("catalog.services.helper_remove") as mock_remove, \
             patch("catalog.services.helper_remove_volume") as mock_rm_vol:
            mock_docker.containers.get.return_value = container
            mock_stop.return_value = "Stopped."
            mock_remove.return_value = "Removed."
            mock_rm_vol.side_effect = ServiceError("Volume not found")
            result = services.remove("uptime-kuma", remove_volumes=True)

        assert "Removed 0 volume(s)." in result["message"]
        assert "failed to remove" in result["message"]

    def test_volume_removal_api_error_is_reported_in_message(self):
        container = MagicMock()

        with patch("catalog.services.docker_client") as mock_docker, \
             patch("catalog.services.helper_stop") as mock_stop, \
             patch("catalog.services.helper_remove") as mock_remove, \
             patch("catalog.services.helper_remove_volume") as mock_rm_vol:
            mock_docker.containers.get.return_value = container
            mock_stop.return_value = "Stopped."
            mock_remove.return_value = "Removed."
            mock_rm_vol.side_effect = ServiceError("Volume boom")
            result = services.remove("uptime-kuma", remove_volumes=True)

        assert "Removed 0 volume(s)." in result["message"]
        assert "1 volume(s) failed to remove" in result["message"]
