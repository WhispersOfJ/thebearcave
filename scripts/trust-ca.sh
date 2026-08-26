#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Trust the Local CA on Devices
# ============================================================================
# Publishes the mkcert root CA to the landing page (nginx, served over HTTPS
# by traefik), rebuilds the combined CA bundle used inside containers, and
# prints per-device installation steps.
#
# Run ONCE on the server after generating the CA (see docs/tls.md), and again
# whenever the CA is regenerated or the host CA bundle is updated:
#   ./scripts/trust-ca.sh
#
# Then, on each device, install rootCA.pem using the steps printed below.
# After the CA is trusted, every *.nip.io hostname serves a valid cert and the
# browser warning disappears.
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_CA="${HOME}/.local/share/mkcert/rootCA.pem"
CA_DIR="${REPO_ROOT}/config/ca"
PUBLISH_DEST="${CA_DIR}/rootCA.pem"
BUNDLE_DEST="${CA_DIR}/ca-bundle.pem"
HOST_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
CA_URL="https://bearcave.${HOST_IP:-192.168.4.20}.nip.io/rootCA.pem"

if [[ ! -f "${ROOT_CA}" ]]; then
    echo -e "${RED}✗ rootCA.pem not found at ${ROOT_CA}${NC}"
    echo "Generate the CA first: mkcert -install  (see docs/tls.md)"
    exit 1
fi

# Publish the CA; the landing-page nginx container mounts this single file and
# serves it at /rootCA.pem (public cert — no key).
mkdir -p "${CA_DIR}"
cp -f "${ROOT_CA}" "${PUBLISH_DEST}"
echo -e "${GREEN}✓ rootCA.pem published (landing page serves it at ${CA_URL})${NC}"

# Rebuild the combined bundle (public CAs + mkcert root) that every container
# mounts as its SSL_CERT_FILE. SSL_CERT_FILE/CURL_CA_BUNDLE/REQUESTS_CA_BUNDLE
# REPLACE the bundle — pointing them at rootCA.pem alone would break all
# external HTTPS calls (indexers, usenet, TMDB/TVDB) — so the bundle must keep
# the full public trust store plus the mkcert root.
if [[ ! -f "${HOST_BUNDLE}" ]]; then
    echo -e "${RED}✗ host CA bundle not found at ${HOST_BUNDLE}${NC}"
    echo "  Rebuild ca-bundle.pem manually: cat <host bundle> ${ROOT_CA} > ${BUNDLE_DEST}" >&2
else
    cat "${HOST_BUNDLE}" "${ROOT_CA}" > "${BUNDLE_DEST}"
    echo -e "${GREEN}✓ ca-bundle.pem rebuilt ($(grep -c 'BEGIN CERTIFICATE' "${BUNDLE_DEST}") certs: host store + mkcert)${NC}"
fi
echo

cat <<'EOF'
==============================================================================
 INSTALL THE CA ON EACH DEVICE (pick your platform)
==============================================================================

--- Linux (Debian/Ubuntu) ------------------------------------------------
  curl -kO https://bearcave.192.168.4.20.nip.io/rootCA.pem
  sudo cp rootCA.pem /usr/local/share/ca-certificates/mkcert-rootCA.crt
  sudo update-ca-certificates
  # Firefox: Settings → Privacy & Security → Certificates → View…
  #          → Authorities → Import → select rootCA.pem

--- Linux (Fedora/RHEL) --------------------------------------------------
  curl -kO https://bearcave.192.168.4.20.nip.io/rootCA.pem
  sudo cp rootCA.pem /etc/pki/ca-trust/source/anchors/
  sudo update-ca-trust

--- macOS -----------------------------------------------------------------
  curl -kO https://bearcave.192.168.4.20.nip.io/rootCA.pem
  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain rootCA.pem

--- Windows ---------------------------------------------------------------
  curl.exe -k -O https://bearcave.192.168.4.20.nip.io/rootCA.pem
  certutil -addstore -f "ROOT" rootCA.pem
  # (or double-click rootCA.pem → Install Certificate → Local Machine → Trusted Root)

--- iOS / iPadOS ----------------------------------------------------------
  1. Safari → https://bearcave.192.168.4.20.nip.io/rootCA.pem  (download, allow)
  2. Settings → General → VPN & Device Management → install the profile
  3. Settings → General → About → Certificate Trust Settings
     → enable full trust for the mkcert CA

--- Android ---------------------------------------------------------------
  1. Chrome → https://bearcave.192.168.4.20.nip.io/rootCA.pem (download)
  2. Settings → Security → Encryption & credentials → Install a certificate
     → CA certificate → select the download
==============================================================================

Verification: after trusting, open https://bearcave.192.168.4.20.nip.io
— the padlock should be valid (no warning).

Note: the CA URL is LAN-only and unauthenticated (same trust model as the rest
of the stack's UIs). The root CA certificate is public by design — only the
rootCA-key.pem private key (which never leaves this server) is secret.
EOF
