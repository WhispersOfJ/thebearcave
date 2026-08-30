#!/usr/bin/env bash
# Daily mount-drift / stale-FUSE-handle check against the live stack.
#
# Runs scripts/check_mount_drift.py. A clean run (exit 0) writes
# mount_drift_divergence 0 into the node-exporter textfile directory; any
# divergence or probe error writes 1, so the state lands in Prometheus (the
# compose node-exporter service bind-mounts the textfile dir read-only at
# /textfile) for dashboards and alerting. The systemd user timer
# mount-drift-check.timer runs this daily; the drift check itself cannot run
# on a GitHub runner because it inspects live containers.
#
# The script always exits 0: state is signalled through the metric, not
# through the unit's exit status, so the timer never flaps.
#
# Override the output paths with MOUNT_DRIFT_TEXTFILE_DIR /
# MOUNT_DRIFT_LOG_FILE if the default layout does not match the compose mount.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXTFILE_DIR="${MOUNT_DRIFT_TEXTFILE_DIR:-$HOME/.local/share/node-exporter-textfile}"
LOG_FILE="${MOUNT_DRIFT_LOG_FILE:-$HOME/.local/state/mount-drift.log}"
METRIC_FILE="$TEXTFILE_DIR/mount_drift.prom"

mkdir -p "$TEXTFILE_DIR" "$(dirname "$LOG_FILE")"

out="$(cd "$REPO_DIR" && python3 scripts/check_mount_drift.py 2>&1)"
rc=$?

write_metric() {
  cat > "$METRIC_FILE" <<EOF
# HELP mount_drift_divergence Live container mounts diverged from compose or a FUSE handle is stale (1) or matches (0).
# TYPE mount_drift_divergence gauge
mount_drift_divergence $1
EOF
}

if [ "$rc" -eq 0 ]; then
  write_metric 0
  echo "Mount drift OK"
else
  write_metric 1
  {
    echo "== $(date -Is) =="
    echo "$out"
  } >> "$LOG_FILE"
  echo "Mount drift problem detected (exit $rc) - see $LOG_FILE" >&2
fi

exit 0
