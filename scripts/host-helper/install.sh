#!/usr/bin/env bash
# Install controlpanel-helper as a systemd socket-activated service.
# Run this on the HOST, not inside a container.
set -euo pipefail

HELPER_DIR="/opt/controlpanel-helper"
SOCKET_GROUP="controlpanel-helper"

echo "=== Installing controlpanel-helper ==="

# 1. Create group if absent
if ! getent group "$SOCKET_GROUP" >/dev/null 2>&1; then
    sudo groupadd --system "$SOCKET_GROUP"
    echo "Created group: $SOCKET_GROUP"
else
    echo "Group $SOCKET_GROUP already exists"
fi

# 2. Copy helper daemon
sudo mkdir -p "$HELPER_DIR"
sudo cp "$(dirname "$0")/helper.py" "$HELPER_DIR/helper.py"
sudo chmod 755 "$HELPER_DIR/helper.py"
echo "Installed helper.py to $HELPER_DIR"

# 3. Install systemd units
sudo cp "$(dirname "$0")/controlpanel-helper.service" /etc/systemd/system/
sudo cp "$(dirname "$0")/controlpanel-helper.socket" /etc/systemd/system/
sudo systemctl daemon-reload
echo "Installed systemd units"

# 4. Enable and start socket (the service is socket-activated)
sudo systemctl enable --now controlpanel-helper.socket
echo "Enabled and started controlpanel-helper.socket"

# 5. Verify
if [ -S /run/controlpanel-helper.sock ]; then
    echo "Socket is listening at /run/controlpanel-helper.sock"
    ls -la /run/controlpanel-helper.sock
else
    echo "WARNING: Socket not found at /run/controlpanel-helper.sock"
    echo "Check: sudo systemctl status controlpanel-helper.socket"
    exit 1
fi

echo ""
echo "=== Installation complete ==="
echo "The control-panel container can now connect to /run/controlpanel-helper.sock"
echo "No Docker socket access needed for write operations."
