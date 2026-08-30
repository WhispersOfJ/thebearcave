#!/usr/bin/env bash
# Daily stack health metrics check (MCP baseline + mount drift).
#
# Runs scripts/check_mcp.py --baseline and scripts/check_mount_drift.py and
# writes both divergence gauges into a single node-exporter textfile metric
# (stack-health.prom). A clean run of both checks writes 0/0; any divergence
# or probe error writes 1 for that metric, so Prometheus fires
# McpBaselineDivergence / MountDriftDivergence and alertmanager pages the
# configured Discord channel. The systemd user timer stack-health-metrics.timer
# runs this daily; the compose node-exporter service bind-mounts the textfile
# dir read-only at /textfile. The mount-drift check itself cannot run on a
# GitHub runner because it inspects live containers.
#
# The script always exits 0: state is signalled through the metrics, not
# through the unit's exit status, so the timer never flaps.
#
# Override the output paths with STACK_HEALTH_TEXTFILE_DIR /
# STACK_HEALTH_LOG_FILE if the default layout does not match the compose mount.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXTFILE_DIR="${STACK_HEALTH_TEXTFILE_DIR:-$HOME/.local/share/node-exporter-textfile}"
LOG_FILE="${STACK_HEALTH_LOG_FILE:-$HOME/.local/state/stack-health.log}"
METRIC_FILE="$TEXTFILE_DIR/stack-health.prom"

mkdir -p "$TEXTFILE_DIR" "$(dirname "$LOG_FILE")"

mcp_out="$(cd "$REPO_DIR" && python3 scripts/check_mcp.py --baseline 2>&1)"
mcp_rc=$?

drift_out="$(cd "$REPO_DIR" && python3 scripts/check_mount_drift.py 2>&1)"
drift_rc=$?

{
  cat <<'EOF'
# HELP mcp_baseline_divergence MCP server state diverged from the committed baseline (1) or matches (0).
# TYPE mcp_baseline_divergence gauge
EOF
  if [ "$mcp_rc" -eq 0 ]; then
    echo "mcp_baseline_divergence 0"
  else
    echo "mcp_baseline_divergence 1"
  fi
  cat <<'EOF'
# HELP mount_drift_divergence Live container mounts diverged from compose or a FUSE handle is stale (1) or matches (0).
# TYPE mount_drift_divergence gauge
EOF
  if [ "$drift_rc" -eq 0 ]; then
    echo "mount_drift_divergence 0"
  else
    echo "mount_drift_divergence 1"
  fi
} > "$METRIC_FILE"

if [ "$mcp_rc" -ne 0 ]; then
  {
    echo "== $(date -Is) MCP baseline =="
    echo "$mcp_out"
  } >> "$LOG_FILE"
  echo "MCP baseline problem detected (exit $mcp_rc) - see $LOG_FILE" >&2
else
  echo "MCP baseline OK"
fi

if [ "$drift_rc" -ne 0 ]; then
  {
    echo "== $(date -Is) mount drift =="
    echo "$drift_out"
  } >> "$LOG_FILE"
  echo "Mount drift problem detected (exit $drift_rc) - see $LOG_FILE" >&2
else
  echo "Mount drift OK"
fi

exit 0
