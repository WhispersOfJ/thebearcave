"""Thin client for the host-privileged-action helper daemon
(scripts/host-helper/helper.py). Sends one JSON request over a
Unix domain socket, reads one JSON response, closes - never talks to the
host any other way (no nsenter, no D-Bus). This socket is the ONLY
privileged surface this container has for write operations - the Docker
socket is mounted read-only for reads only (stats, logs, listing).

All Docker write operations (restart, stop, start, prune, pull, run,
remove) go through this client to the helper daemon, which runs as host
root via systemd. The helper validates every parameter against a strict
regex before passing it to docker CLI subprocess calls.

Every route using this client must degrade to a clear error rather than
assume the socket exists.
"""
import json
import os
import socket

from core.api_base import ServiceError

HOST_HELPER_SOCKET = os.environ.get("HOST_HELPER_SOCKET", "/host-helper.sock")
DEFAULT_TIMEOUT = 600


def call_host_helper(action: str, timeout: float = DEFAULT_TIMEOUT, **params) -> dict:
    """Raises a ServiceError on any transport failure - socket not present
    (helper not installed on this host), connection refused, timeout, or a
    malformed response. On success, returns the daemon's own {"ok",
    "message", "returncode"} dict unchanged - the caller checks `ok`
    itself, since a verb can fail (e.g. pacman exiting non-zero) without
    this function raising.

    Extra keyword arguments are merged into the JSON payload alongside
    the action field, so call_host_helper("docker_restart", container="plex")
    sends {"action": "docker_restart", "container": "plex"}."""
    if not os.path.exists(HOST_HELPER_SOCKET):
        raise ServiceError("Host helper isn't installed on this host - see scripts/host-helper/README.md.", status=503)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(HOST_HELPER_SOCKET)
        payload = {"action": action, **params}
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    except OSError as e:
        raise ServiceError(f"Host helper request failed: {e}", status=502)
    finally:
        sock.close()
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        raise ServiceError("Host helper returned a malformed response.", status=502)
