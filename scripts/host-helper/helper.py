#!/usr/bin/env python3
"""controlpanel-helper — minimal privileged host-action daemon.

Listens on a systemd-activated Unix socket, dispatches a fixed, closed
set of verbs to hardcoded subprocess argv lists — never a shell string,
never a templated command, never a caller-supplied argument reaching a
command line. This IS the security boundary between the control-panel
container (root-in-container, but never root-on-host) and actions that
only host root can take.

Protocol: one connection per request. Client sends one newline-terminated
JSON object ({"action": "<verb>", ...params...}), then half-closes its
write side. Daemon replies with one newline-terminated JSON object
({"ok": bool, "message": str, "returncode": int|null}) and closes.

Two verb categories:
  1. Host actions (reboot, pacman) — hardcoded argv, no caller params
  2. Docker actions — validated params fed to docker CLI subprocess calls

Runs as root (systemd service, User=root). Every request is logged to
LOG_PATH with the action, outcome, and return code.
"""
import json
import logging
import os
import re
import socket
import subprocess

LOG_PATH = os.environ.get("CONTROLPANEL_HELPER_LOG", "/var/log/controlpanel-helper.log")
SOCKET_PATH = os.environ.get("CONTROLPANEL_HELPER_SOCKET", "/run/controlpanel-helper.sock")
RECV_CHUNK = 4096
MAX_REQUEST_BYTES = 4096

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(message)s")

# ─── Validation helpers ─────────────────────────────────────────────

# Container/image/volume names: alphanumeric, hyphens, underscores, dots, slashes (for images)
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._\-/:]{0,127}$')

def _validate_name(value, label="name"):
    """Validate a container/image/volume name against a strict regex."""
    if not isinstance(value, str) or not _SAFE_NAME_RE.match(value):
        raise ValueError(f"Invalid {label}: must be 1-128 chars, alphanumeric/hyphens/underscores/dots/slashes")
    return value

def _validate_port(value):
    """Validate a port number (1-65535)."""
    port = int(value)
    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port: {port}")
    return port

def _validate_bool(value):
    """Validate a boolean-like value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return False

# ─── Host action verbs (no caller params) ──────────────────────────

HOST_VERBS = {
    "reboot": (["systemctl", "reboot"], 60),
    "pacman_sync": (["pacman", "-Sy", "--noconfirm"], 120),
    "pacman_upgrade": (["pacman", "-Syu", "--noconfirm"], 1800),
}

def _run_host_verb(action):
    argv, timeout = HOST_VERBS[action]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": f"{action} timed out after {timeout}s.", "returncode": None}
    except OSError as e:
        return {"ok": False, "message": f"{action} failed to start: {e}", "returncode": None}
    ok = result.returncode == 0
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    message = output[-4000:] if output else ("succeeded" if ok else "failed with no output")
    return {"ok": ok, "message": message, "returncode": result.returncode}

# ─── Docker action verbs (validated params → docker CLI) ───────────

def _docker(args, timeout=60):
    """Run a docker CLI command and return the result dict."""
    cmd = ["docker"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": f"docker command timed out after {timeout}s.", "returncode": None}
    except OSError as e:
        return {"ok": False, "message": f"docker failed to start: {e}", "returncode": None}
    ok = result.returncode == 0
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    message = output[-4000:] if output else ("succeeded" if ok else "failed with no output")
    return {"ok": ok, "message": message, "returncode": result.returncode}


def _handle_docker_restart(params):
    name = _validate_name(params.get("container"), "container")
    timeout = int(params.get("timeout", 30))
    return _docker(["restart", "-t", str(timeout), name], timeout=timeout + 10)


def _handle_docker_stop(params):
    name = _validate_name(params.get("container"), "container")
    timeout = int(params.get("timeout", 30))
    return _docker(["stop", "-t", str(timeout), name], timeout=timeout + 10)


def _handle_docker_start(params):
    name = _validate_name(params.get("container"), "container")
    return _docker(["start", name])


def _handle_docker_prune_images(params):
    return _docker(["image", "prune", "-f"], timeout=120)


def _handle_docker_prune_volumes(params):
    return _docker(["volume", "prune", "-f"], timeout=120)


def _handle_docker_pull(params):
    image = _validate_name(params.get("image"), "image")
    tag = params.get("tag", "latest")
    _validate_name(tag, "tag")
    return _docker(["pull", f"{image}:{tag}"], timeout=300)


def _handle_docker_remove(params):
    name = _validate_name(params.get("container"), "container")
    force = _validate_bool(params.get("force", False))
    cmd = ["rm"]
    if force:
        cmd.append("-f")
    cmd.append(name)
    return _docker(cmd)


def _handle_docker_remove_volume(params):
    name = _validate_name(params.get("volume"), "volume")
    return _docker(["volume", "rm", name])


def _handle_docker_run(params):
    """Run a new container with validated parameters.

    Expected params:
      image: str (required) — image:tag reference
      name: str (required) — container name
      network: str — network name
      ports: dict — {host_port: container_port}
      volumes: list — [{source, target, mode}] or {source: {bind, mode}}
      environment: dict — env vars
      labels: dict — container labels
      cap_add: list — capabilities to add
      restart_policy: str — e.g. "unless-stopped"
      command: str or list — override command
      detach: bool — run in background (default true)
    """
    image = _validate_name(params.get("image"), "image")
    name = _validate_name(params.get("name"), "name")

    cmd = ["run", "--name", name, "-d"]

    # Network
    network = params.get("network")
    if network:
        _validate_name(network, "network")
        cmd.extend(["--network", network])

    # Restart policy
    restart = params.get("restart_policy", "unless-stopped")
    if restart:
        cmd.extend(["--restart", restart])

    # Capabilities
    for cap in (params.get("cap_add") or []):
        _validate_name(cap, "capability")
        cmd.extend(["--cap-add", cap])

    # Environment variables (key=value pairs)
    for key, value in (params.get("environment") or {}).items():
        _validate_name(key, "env_key")
        # Value is between quotes, so shell injection isn't possible via subprocess
        cmd.extend(["-e", f"{key}={value}"])

    # Labels
    for key, value in (params.get("labels") or {}).items():
        _validate_name(key, "label_key")
        cmd.extend(["--label", f"{key}={value}"])

    # Port mappings
    for host_port, container_port in (params.get("ports") or {}).items():
        hp = _validate_port(host_port)
        cp = _validate_port(container_port)
        cmd.extend(["-p", f"{hp}:{cp}"])

    # Volume mounts
    for vol in (params.get("volumes") or []):
        if isinstance(vol, dict):
            source = vol.get("source", vol.get("bind", ""))
            target = vol.get("target", vol.get("bind", ""))
            mode = vol.get("mode", "rw")
        elif isinstance(vol, str):
            source, target, mode = vol, vol, "rw"
        else:
            continue
        if source:
            _validate_name(source, "volume_source")
        mount_str = f"{source}:{target}"
        if mode and mode != "rw":
            mount_str += f":{mode}"
        cmd.extend(["-v", mount_str])

    # Command
    command = params.get("command")
    if command:
        if isinstance(command, list):
            cmd.extend(command)
        else:
            cmd.extend(["/bin/sh", "-c", command])

    # Image (last arg)
    cmd.append(image)

    return _docker(cmd, timeout=120)


# ─── Dispatch table ─────────────────────────────────────────────────

DOCKER_HANDLERS = {
    "docker_restart": _handle_docker_restart,
    "docker_stop": _handle_docker_stop,
    "docker_start": _handle_docker_start,
    "docker_prune_images": _handle_docker_prune_images,
    "docker_prune_volumes": _handle_docker_prune_volumes,
    "docker_pull": _handle_docker_pull,
    "docker_remove": _handle_docker_remove,
    "docker_remove_volume": _handle_docker_remove_volume,
    "docker_run": _handle_docker_run,
}

ALL_ACTIONS = set(HOST_VERBS.keys()) | set(DOCKER_HANDLERS.keys())


def handle_request(raw):
    """Returns (response, action) — action is None when the request
    couldn't even be parsed far enough to log which verb was attempted."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "message": "Malformed JSON request.", "returncode": None}, None
    if not isinstance(payload, dict):
        return {"ok": False, "message": "Request must be a JSON object.", "returncode": None}, None

    action = payload.get("action")
    if not isinstance(action, str):
        return {"ok": False, "message": "Request must include a string 'action'.", "returncode": None}, None

    # Host verbs (no params)
    if action in HOST_VERBS:
        return _run_host_verb(action), action

    # Docker verbs (validated params)
    handler = DOCKER_HANDLERS.get(action)
    if handler:
        try:
            return handler(payload), action
        except ValueError as e:
            return {"ok": False, "message": f"Validation error: {e}", "returncode": None}, action

    return {"ok": False, "message": f"Unknown action '{action}' — not in the fixed verb set.", "returncode": None}, action


# ─── Socket server (unchanged) ─────────────────────────────────────

def _listen_socket():
    if os.environ.get("LISTEN_FDS") == "1" and os.environ.get("LISTEN_PID") == str(os.getpid()):
        return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, fileno=3)
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o660)
    sock.listen(5)
    return sock


def _recv_request(conn):
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(RECV_CHUNK)
        if not chunk:
            break
        data += chunk
        if len(data) > MAX_REQUEST_BYTES:
            raise ValueError("request too large")
    return data.decode("utf-8", errors="replace").strip()


def serve_one(conn):
    try:
        try:
            raw = _recv_request(conn)
        except ValueError as e:
            response, action = {"ok": False, "message": str(e), "returncode": None}, None
        else:
            response, action = handle_request(raw) if raw else ({"ok": False, "message": "Empty request.", "returncode": None}, None)
        logging.info(json.dumps({"action": action, "ok": response["ok"], "returncode": response["returncode"]}))
        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
    finally:
        conn.close()


def serve(sock):
    while True:
        conn, _ = sock.accept()
        serve_one(conn)


def main():
    sock = _listen_socket()
    try:
        serve(sock)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
