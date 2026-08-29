#!/usr/bin/env python3
"""Verify configured MCP servers actually work.

Probes every MCP server registered in the Freebuff Desktop / CLI config
(`~/.agents/mcp.json`) and, optionally, the Claude Code store
(`~/.claude.json`). For each server it:

  1. spawns the configured command (spawn check),
  2. drives a real MCP `initialize` handshake over stdio,
  3. requests `tools/list` and reports the tool names,
  4. if Freebuff Desktop is running, checks the live orchestrator
     approval state (`enabled` / `status` / `approvedLaunch` /
     `approvedTools`) so you can see whether a server is registered
     but still gated behind the Connectors consent flow.

The live-state check finds the running Freebuff orchestrator by scanning
`/proc` for the consent token + API port (same-user access), so it works
without touching the app UI.

Usage:
  python3 scripts/check_mcp.py                # all stores; human-readable; exit 1 on failures
  python3 scripts/check_mcp.py --freebuff     # only ~/.agents/mcp.json (Freebuff)
  python3 scripts/check_mcp.py --claude       # only ~/.claude.json (Claude Code)
  python3 scripts/check_mcp.py --json         # machine-readable report; always exit 0
  python3 scripts/check_mcp.py --no-live      # skip the live orchestrator state check
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
AGENTS_MCP = HOME / ".agents" / "mcp.json"
CLAUDE_JSON = HOME / ".claude.json"

# MCP protocol version used for the initialize handshake.
PROTOCOL_VERSION = "2025-06-18"


def load_servers():
    """Return {store: {server_name: config}} from the config files that exist."""
    stores = {}
    for name, path in (("freebuff", AGENTS_MCP), ("claude", CLAUDE_JSON)):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"[{name}] WARN: could not parse {path}: {e}")
            continue
        servers = data.get("mcpServers", {})
        if isinstance(servers, dict) and servers:
            stores[name] = servers
    return stores


class McpClient:
    """Minimal MCP stdio client: spawn, initialize, tools/list."""

    def __init__(self, command, args, env_extra=None, timeout_s=45):
        self.timeout_s = timeout_s
        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)
        self.proc = subprocess.Popen(
            [command] + list(args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )
        self.next_id = 0

    def _send(self, method, params=None):
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue
            if resp.get("id") == self.next_id:
                return resp
        return None

    def handshake(self):
        """Return (server_info, tool_names) or (None, error_string)."""
        init = self._send(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "check_mcp", "version": "0.1"},
            },
        )
        if not init or "result" not in init:
            return None, (init or {}).get("error", "no initialize response")
        server_info = init["result"].get("serverInfo", {})
        # initialized notification, then tools/list
        try:
            self.proc.stdin.write(
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
            )
            self.proc.stdin.flush()
        except Exception:
            pass
        tools = self._send("tools/list", {})
        if not tools or "result" not in tools:
            return server_info, (tools or {}).get("error", "no tools/list response")
        names = [t.get("name", "?") for t in tools["result"].get("tools", [])]
        return server_info, names

    def close(self):
        try:
            self.proc.kill()
            self.proc.wait(timeout=5)
        except Exception:
            pass


def _listening_ports(pid):
    """Resolve a pid's listening loopback ports via /proc fd inodes -> /proc/net/tcp.

    The orchestrator's API port is ephemeral and not exposed in its env, so
    we map its socket file descriptors to port numbers. Returns a set of ints.
    """
    fd_dir = Path("/proc") / str(pid) / "fd"
    inodes = set()
    try:
        for fd in fd_dir.iterdir():
            try:
                link = os.readlink(fd)
            except OSError:
                continue
            m = re.match(r"socket:\[(\d+)\]", link)
            if m:
                inodes.add(m.group(1))
    except OSError:
        return set()

    ports = set()
    for tcp_path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(tcp_path).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            inode = parts[9]
            if inode not in inodes:
                continue
            state = parts[3]
            local = parts[1]
            # 0A = LISTEN; 0100007F = 127.0.0.1 (tcp6 loopback = 00000000000000000000000001000000)
            if state != "0A":
                continue
            if not (local.startswith("0100007F:") or local.startswith("00000000000000000000000001000000:")):
                continue
            try:
                ports.add(int(local.rsplit(":", 1)[1], 16))
            except ValueError:
                continue
    return ports


def find_freebuff_orchestrator():
    """Locate the running Freebuff orchestrator: (port, token) or (None, None).

    The token comes from the consent bridge env (same-user read of /proc);
    the API port is the orchestrator's own ephemeral listener (PORT env is
    unset/0), resolved from its socket inodes.
    """
    for pid_dir in Path("/proc").iterdir():
        if not pid_dir.name.isdigit():
            continue
        env_path = pid_dir / "environ"
        cmdline_path = pid_dir / "cmdline"
        try:
            cmdline = cmdline_path.read_bytes().decode(errors="replace")
        except OSError:
            continue
        if "orchestrator.js" not in cmdline:
            continue
        try:
            env = env_path.read_bytes().decode(errors="replace").split("\0")
        except OSError:
            continue
        env_map = dict(kv.split("=", 1) for kv in env if "=" in kv)
        token = env_map.get("FREEBUFF_MCP_CONSENT_TOKEN")
        if not token:
            continue
        ports = _listening_ports(int(pid_dir.name))
        # Prefer a loopback listener that answers the API; fall back to the first.
        for port in sorted(ports):
            if port == int(env_map.get("FREEBUFF_MCP_CONSENT_PORT") or 0):
                continue  # that is the consent bridge, not the API
            return port, token
        if ports:
            return min(ports), token
    return None, None


def live_state(port, token, config_key):
    """Query the orchestrator API for a server's approval state, or None."""
    import urllib.request

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/mcp/servers",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    for s in data.get("servers", []):
        if s.get("configKey") == config_key:
            return s
    return None


def probe_server(store, name, cfg, check_live=True):
    """Probe one server; return (ok, detail_lines)."""
    lines = []
    command = cfg.get("command")
    args = cfg.get("args", [])
    if not command:
        lines.append(f"  {name}: no 'command' in config — skipping")
        return False, lines

    ok = False
    client = None
    try:
        client = McpClient(command, args, cfg.get("env") or {})
        server_info, result = client.handshake()
        if isinstance(result, list):
            names = result
            info = server_info or {}
            lines.append(
                f"  {name}: PASS — handshake OK"
                + (f" ({info.get('name')} {info.get('version', '')})".rstrip() if info else "")
            )
            lines.append(f"    tools ({len(names)}): {', '.join(names[:12])}{'...' if len(names) > 12 else ''}")
            ok = True
        else:
            lines.append(f"  {name}: FAIL — {result}")
    except Exception as e:
        lines.append(f"  {name}: FAIL — spawn/handshake error: {e}")
    finally:
        if client:
            client.close()

    if check_live:
        port, token = find_freebuff_orchestrator()
        if port and token:
            state = live_state(port, token, name)
            if state:
                lines.append(
                    f"    live: enabled={state.get('enabled')} status={state.get('status')} "
                    f"approvedLaunch={state.get('approvedLaunch')} "
                    f"approvedTools={state.get('approvedTools')} "
                    f"tools={state.get('toolCount')}"
                )
                if state.get("error"):
                    lines.append(f"    live error: {state['error']}")
                if state.get("status") == "awaiting_launch_approval":
                    lines.append("    NOTE: registered but NOT approved — approve in Settings → Connectors")
            else:
                lines.append("    live: not registered in the running Freebuff orchestrator (normal for Claude Code servers)")
        else:
            lines.append("    live: Freebuff Desktop not running — skipped")
    return ok, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--freebuff", action="store_true", help="only ~/.agents/mcp.json (Freebuff)")
    ap.add_argument("--claude", action="store_true", help="only ~/.claude.json (Claude Code)")
    ap.add_argument("--json", action="store_true", help="machine-readable report; always exit 0")
    ap.add_argument("--no-live", action="store_true", help="skip the live orchestrator state check")
    args = ap.parse_args()

    stores = load_servers()
    if args.freebuff:
        stores = {k: v for k, v in stores.items() if k == "freebuff"}
    if args.claude:
        stores = {k: v for k, v in stores.items() if k == "claude"}

    if not stores:
        msg = "No MCP servers configured (checked ~/.agents/mcp.json and ~/.claude.json)."
        if args.json:
            print(json.dumps({"ok": True, "servers": [], "message": msg}))
        else:
            print(msg)
        return 0

    results = {}
    all_ok = True
    for store, servers in stores.items():
        if not args.json:
            print(f"\n=== {store} ({len(servers)} server(s)) ===")
        for name, cfg in servers.items():
            ok, lines = probe_server(store, name, cfg, check_live=not args.no_live)
            results[f"{store}/{name}"] = {"ok": ok, "lines": lines}
            all_ok = all_ok and ok
            if not args.json:
                for l in lines:
                    print(l)

    if args.json:
        report = {
            "ok": all_ok,
            "servers": {
                k: {"ok": v["ok"], "detail": v["lines"]} for k, v in results.items()
            },
        }
        print(json.dumps(report, indent=1))
        return 0

    print("\n===== SUMMARY =====")
    for k, v in results.items():
        print(f"  {'PASS' if v['ok'] else 'FAIL'}  {k}")
        all_ok = all_ok and v["ok"]
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
