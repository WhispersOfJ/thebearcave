#!/usr/bin/env bash
# Daily MCP baseline divergence check.
#
# Runs scripts/check_mcp.py --baseline against .github/mcp-baseline.json. A
# clean run (exit 0) writes mcp_baseline_divergence 0 into the node-exporter
# textfile directory; any failure (divergence or probe error) writes 1, so
# Prometheus fires McpBaselineDivergence and alertmanager pages the
# configured Discord channel. The systemd user timer mcp-baseline-check.timer
# runs this daily; the compose node-exporter service bind-mounts the textfile
# dir read-only at /textfile.
#
# The script always exits 0: state is signalled through the metric, not
# through the unit's exit status, so the timer never flaps.
#
# Override the output paths with MCP_TEXTFILE_DIR / MCP_LOG_FILE if the
# default layout does not match the compose mount.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXTFILE_DIR="${MCP_TEXTFILE_DIR:-$HOME/.local/share/node-exporter-textfile}"
LOG_FILE="${MCP_LOG_FILE:-$HOME/.local/state/mcp-baseline.log}"
METRIC_FILE="$TEXTFILE_DIR/mcp_baseline.prom"

mkdir -p "$TEXTFILE_DIR" "$(dirname "$LOG_FILE")"

out="$(cd "$REPO_DIR" && python3 scripts/check_mcp.py --baseline 2>&1)"
rc=$?

write_metric() {
  cat > "$METRIC_FILE" <<EOF
# HELP mcp_baseline_divergence MCP server state diverged from the committed baseline (1) or matches (0).
# TYPE mcp_baseline_divergence gauge
mcp_baseline_divergence $1
EOF
}

if [ "$rc" -eq 0 ]; then
  write_metric 0
  echo "MCP baseline OK"
else
  write_metric 1
  {
    echo "== $(date -Is) =="
    echo "$out"
  } >> "$LOG_FILE"
  echo "MCP baseline problem detected (exit $rc) - see $LOG_FILE" >&2
fi

exit 0
