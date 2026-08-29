# MCP Servers in Freebuff Desktop

How Model Context Protocol (MCP) servers are configured in the Freebuff Desktop app,
which ones are worth adding for this stack, and the exact steps for each path.

---

## How Freebuff Desktop wires MCP servers

Freebuff Desktop (a Codebuff/Claude-engine app) manages MCP servers through
**Settings → Connectors**, backed by a single file:

- **`~/.agents/mcp.json`** — the source of truth, shared with the CLI. The
  app reads and writes this file; the Connectors UI is a thin editor over it.
- **Nothing runs until you approve it.** Pasting an `mcpServers` block only
  writes the file. The Electron main process (`mcp-consent-bridge`) raises a
  native dialog before any third-party program is spawned, with per-server
  controls for launch approval, tool approval, enable/disable, sign-in, and
  removal.
- **Secrets are encrypted at rest** in the app's secret store
  (`mcp-secrets.json` in the app userData dir), keyed by the OS keychain.
- **Kill switch:** `FREEBUFF_MCP_DISABLED=1` disables the consent bridge
  entirely.

> **Note:** `mcpServers` entries in `~/.claude.json` belong to Claude Code's
> own store and are **not** read by Freebuff. Freebuff only reads
> `~/.agents/mcp.json`.

### The empty state

With no `mcp.json` yet, the Connectors modal shows:

> *No servers configured yet. Add one to `~/.agents/mcp.json`, then reload.*

---

## Recommended: Context7

**Verdict: add it.** Context7 serves up-to-date, version-specific documentation
for the exact tools this stack runs — Docker Compose, Traefik v3, Next.js,
.NET, Python, Prometheus/Grafana, rclone, and more. It needs no API key for
basic use and fixes the most practical gap in agent sessions: model knowledge
lags current library docs.

### Via the Connectors UI (recommended)

1. Open Freebuff Desktop → **Settings** → **Connectors**.
2. In the paste box, enter:

   ```json
   {
     "mcpServers": {
       "context7": {
         "command": "npx",
         "args": ["-y", "@upstash/context7-mcp@latest"]
       }
     }
   }
   ```

   (The modal accepts either the full block above or the `context7` entry
   alone; the app writes the result into `~/.agents/mcp.json`.)
3. The server is written but **not run** — approve the launch dialog, then the
   tool-approval dialog, then **reload**.
4. Verify in a session: ask for current Docker Compose or Traefik v3 docs and
   confirm the `context7` tools answer with up-to-date content.

### Via the file (equivalent)

1. Create `~/.agents/mcp.json` (merge if it already exists):

   ```json
   {
     "mcpServers": {
       "context7": {
         "command": "npx",
         "args": ["-y", "@upstash/context7-mcp@latest"]
       }
     }
   }
   ```

2. In Freebuff: **Settings → Connectors → Reload**, then approve the launch
   prompt.

Both paths land on the same file; the consent dialog is the safety gate before
`npx` ever runs.

---

## Research: MCP servers evaluated for this stack

| Server | Verdict | Why |
|--------|---------|-----|
| **Context7** (`@upstash/context7-mcp`) | ✅ **Add** | Up-to-date, version-specific docs for the stack's tools. No API key needed for basic use. Fixes stale-docs gap in agent sessions. |
| **Docker MCP** (`docker-mcp` via `uvx`) | ⚠️ Skip | Container/compose/log management, but every session already has terminal access to `docker compose`/`docker ps` directly — redundant. Worse, a spawned MCP server holding the Docker socket widens the exact attack surface `potential.md` item #1 (writable socket, CRITICAL) is trying to close. |
| **Homelab MCP** (bjeans unified server) | ❌ Skip | Docker/Podman + Pi-hole/Unifi/Ollama; only the Docker slice overlaps, and that is the redundant-and-risky part. |
| **Filesystem MCP** | ❌ Skip | Native file read/write/search tools exist in every session. |
| **GitHub MCP** | ❌ Skip | Covered by the authenticated `gh` CLI (see `~/ECC` policy audit). |
| **Playwright / chrome-devtools MCP** | ❌ Skip | Already in `~/.claude.json`; Freebuff has native preview/screenshot/browser tools. |
| **Postgres / Supabase MCP** | ❌ Skip | This stack is SQLite-only — nothing to connect to. |
| **Stackarr** (media-stack control plane + MCP) | ⚠️ Watch | Purpose-built for Radarr/Sonarr/Plex orchestration — typed, approval-gated Docker actions. See [docs/stackarr.md](stackarr.md) for the full evaluation and adoption path. |

---

## Adding any other server

The same JSON shape works for every server. Paste its `mcpServers` block into
the Connectors modal (or merge into `~/.agents/mcp.json`), approve the launch,
and reload. Common shapes:

```json
{
  "mcpServers": {
    "name": {
      "command": "npx",
      "args": ["-y", "package-name@latest"]
    }
  }
}
```

```json
{
  "mcpServers": {
    "name": {
      "command": "uvx",
      "args": ["package-name"]
    }
  }
}
```

Remote (HTTP/SSE) servers instead use `"url": "https://host/path"` with optional
OAuth via the sign-in control.
