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
  python3 scripts/check_mcp.py --baseline     # diff live probe against .github/mcp-baseline.json;
                                              # exit 1 on any divergence (or --baseline PATH)
  python3 scripts/check_mcp.py --write-baseline PATH  # capture live probe as a fresh baseline file
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


DEFAULT_BASELINE = Path(__file__).resolve().parent.parent / ".github" / "mcp-baseline.json"

# Patterns for facts embedded in probe detail lines, so baseline comparison
# does not depend on the exact human-readable wording.
#
# The baseline stores only STABLE facts. The orchestrator's live line also
# carries status + a session-scoped tool count (connected/idle, tools=N) that
# change whenever a chat session starts or stops — those are transient and
# would open spurious PRs on every re-capture, so they are normalized out.
_RE_TOOLS = re.compile(r"tools \((\d+)\):")
_RE_LIVE = re.compile(
    r"live: enabled=(\w+) approvedLaunch=(\w+) approvedTools=(\w+)"
)


def facts_from_detail(detail):
    """Extract {tools, enabled, approvedLaunch, approvedTools} from detail lines."""
    facts = {}
    for line in detail:
        m = _RE_TOOLS.search(line)
        if m:
            facts["tools"] = int(m.group(1))
        m = _RE_LIVE.search(line)
        if m:
            facts["enabled"] = m.group(1) == "True"
            facts["approvedLaunch"] = m.group(2) == "True"
            facts["approvedTools"] = m.group(3) == "True"
    return facts


def write_baseline(live_report, baseline_path):
    """Write a fresh baseline file from a live probe report.

    Mirrors the shape of .github/mcp-baseline.json: description,
    capturedAt (today), and per-server ok/tools/detail. Returns the
    written path.
    """
    import datetime

    baseline = {
        "description": (
            "Expected MCP server state for scripts/check_mcp.py. "
            "The probe (python3 scripts/check_mcp.py) exits non-zero if any "
            "configured server fails the spawn/initialize/tools-list handshake "
            "or diverges from the live Freebuff orchestrator approval state "
            "recorded here. Re-capture after adding/approving servers with: "
            "python3 scripts/check_mcp.py --write-baseline .github/mcp-baseline.json"
        ),
        "capturedAt": datetime.date.today().isoformat(),
        "servers": {},
    }
    # Preserve probe order (store order, then config-file order) so a
    # re-capture with unchanged state produces an identical file — sorted
    # keys would reorder servers and create a spurious PR on every run.
    for key, val in live_report.get("servers", {}).items():
        facts = facts_from_detail(val.get("detail", []))
        baseline["servers"][key] = {
            "ok": val.get("ok"),
            "tools": facts.get("tools"),
            "detail": val.get("detail", []),
        }
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
    return baseline_path


def compare_to_baseline(live_report, baseline_path):
    """Diff the live probe report against a baseline file.

    Returns (divergences, notes) where divergences is a list of
    human-readable strings describing every difference between the live
    state and the baseline: missing/extra servers, handshake failures,
    tool-count drift, and approval-state changes.
    """
    if not baseline_path.exists():
        return [f"baseline file not found: {baseline_path}"], []
    try:
        baseline = json.loads(baseline_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return [f"baseline file unreadable ({e}): {baseline_path}"], []

    base_servers = baseline.get("servers", {})
    live_servers = live_report.get("servers", {})
    divergences = []
    notes = []

    for key in sorted(set(live_servers) | set(base_servers)):
        live = live_servers.get(key)
        base = base_servers.get(key)
        if base is None:
            notes.append(f"{key}: present in live probe but not in baseline (new server — re-capture baseline)")
            continue
        if live is None:
            divergences.append(f"{key}: missing from live probe but expected by baseline (removed/renamed?)")
            continue

        lf = facts_from_detail(live.get("detail", []))
        bf = facts_from_detail(base.get("detail", []))
        btools = base.get("tools")
        bok = base.get("ok")

        if not live.get("ok"):
            divergences.append(f"{key}: handshake FAILS now (baseline ok={bok})")
        elif bok is False:
            notes.append(f"{key}: baseline recorded a failure but live probe passes now")

        if "tools" in lf and btools is not None and lf["tools"] != btools:
            divergences.append(f"{key}: tool count changed {btools} -> {lf['tools']}")

        # Approval-state drift is only meaningful for servers the live
        # orchestrator knows about (the live line exists) AND the baseline
        # recorded a live line (so we have a before/after).
        if "enabled" in lf and "enabled" in bf:
            for field in ("enabled", "approvedLaunch", "approvedTools"):
                if lf[field] != bf[field]:
                    divergences.append(
                        f"{key}: {field} changed {bf[field]} -> {lf[field]}"
                    )
        elif "enabled" in lf and "enabled" not in bf:
            notes.append(f"{key}: has live orchestrator state but baseline predates it")

    return divergences, notes


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

    # Only the Freebuff orchestrator exposes live state, and it only ever
    # tracks servers from ~/.agents/mcp.json (configKey = bare server name).
    # A claude-store entry with the same name (e.g. playwright exists in
    # both stores) must NOT be credited with the freebuff entry's live
    # state — the live line it would get belongs to the other store, and
    # later approval changes there would falsely flag this entry as
    # diverged. So the live check is gated to the freebuff store.
    if check_live and store == "freebuff":
        port, token = find_freebuff_orchestrator()
        if port and token:
            state = live_state(port, token, name)
            if state:
                # Stable fields only — status/toolCount are session-scoped and
                # transient; storing them in the baseline would produce spurious
                # divergences whenever a chat session starts or stops.
                lines.append(
                    f"    live: enabled={state.get('enabled')} "
                    f"approvedLaunch={state.get('approvedLaunch')} "
                    f"approvedTools={state.get('approvedTools')}"
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
    ap.add_argument(
        "--baseline",
        nargs="?",
        const=str(DEFAULT_BASELINE),
        default=None,
        metavar="PATH",
        help="diff live probe against the MCP baseline (default: %(const)s); exit 1 on divergence",
    )
    ap.add_argument(
        "--write-baseline",
        metavar="PATH",
        default=None,
        help="capture the live probe as a fresh baseline file at PATH (no comparison)",
    )
    args = ap.parse_args()

    stores = load_servers()
    if args.freebuff:
        stores = {k: v for k, v in stores.items() if k == "freebuff"}
    if args.claude:
        stores = {k: v for k, v in stores.items() if k == "claude"}

    if not stores:
        # Still honor --write-baseline / --baseline with an empty report so a
        # total removal of servers is captured as a state change rather than
        # silently ignored by the early return.
        empty_report = {"ok": True, "servers": {}}
        if args.write_baseline:
            path = write_baseline(empty_report, Path(args.write_baseline))
            print(f"wrote baseline: {path}")
            return 0
        if args.baseline:
            divergences, notes = compare_to_baseline(empty_report, Path(args.baseline))
            for note in notes:
                print(f"  NOTE: {note}")
            for d in divergences:
                print(f"  DIVERGENCE: {d}")
            print(f"\n  baseline: {args.baseline}")
            print(f"  {len(divergences)} divergence(s), {len(notes)} note(s)")
            return 1 if divergences else 0
        msg = "No MCP servers configured (checked ~/.agents/mcp.json and ~/.claude.json)."
        if args.json:
            print(json.dumps({"ok": True, "servers": [], "message": msg}))
        else:
            print(msg)
        return 0

    quiet = args.json or args.baseline or args.write_baseline
    results = {}
    all_ok = True
    for store, servers in stores.items():
        if not quiet:
            print(f"\n=== {store} ({len(servers)} server(s)) ===")
        for name, cfg in servers.items():
            ok, lines = probe_server(store, name, cfg, check_live=not args.no_live)
            results[f"{store}/{name}"] = {"ok": ok, "lines": lines}
            all_ok = all_ok and ok
            if not quiet:
                for l in lines:
                    print(l)

    live_report = {
        "ok": all_ok,
        "servers": {k: {"ok": v["ok"], "detail": v["lines"]} for k, v in results.items()},
    }

    if args.write_baseline:
        path = write_baseline(live_report, Path(args.write_baseline))
        print(f"wrote baseline: {path}")
        # Exit non-zero if any server failed the handshake so a workflow that
        # re-captures and opens a PR does not cement a broken baseline as the
        # new expected state (set -euo pipefail aborts before the PR step).
        return 0 if all_ok else 1

    if args.baseline:
        divergences, notes = compare_to_baseline(live_report, Path(args.baseline))
        for note in notes:
            print(f"  NOTE: {note}")
        for d in divergences:
            print(f"  DIVERGENCE: {d}")
        print(f"\n  baseline: {args.baseline}")
        print(f"  {len(divergences)} divergence(s), {len(notes)} note(s)")
        return 1 if divergences else 0

    if args.json:
        print(json.dumps(live_report, indent=1))
        return 0

    print("\n===== SUMMARY =====")
    for k, v in results.items():
        print(f"  {'PASS' if v['ok'] else 'FAIL'}  {k}")
        all_ok = all_ok and v["ok"]
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
