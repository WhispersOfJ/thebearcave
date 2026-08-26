#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Trust the local CA on LAN devices via Ansible
# ============================================================================
# Wrapper around ansible/playbooks/trust-ca.yml: verifies prerequisites
# (ansible, the CA file, an inventory) and runs the playbook.
#
# Usage:
#   ./scripts/ansible-trust-ca.sh                          # uses ansible/hosts.yml
#   ./scripts/ansible-trust-ca.sh -i my-inventory.yml      # custom inventory
#   ./scripts/ansible-trust-ca.sh --ask-pass --ask-become-pass
#   ANSIBLE_INVENTORY=hosts.yml BEAR_CA_FILE=/x/rootCA.pem ./scripts/ansible-trust-ca.sh
#
# Extra flags (and -e overrides like -e install_firefox_nss=true) are passed
# straight through to ansible-playbook.
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAYBOOK="${REPO_ROOT}/ansible/playbooks/trust-ca.yml"
INVENTORY="${ANSIBLE_INVENTORY:-${REPO_ROOT}/ansible/hosts.yml}"
CA_FILE="${BEAR_CA_FILE:-${HOME}/.local/share/mkcert/rootCA.pem}"

if ! command -v ansible-playbook >/dev/null 2>&1; then
    echo -e "${RED}✗ ansible-playbook not found${NC}" >&2
    echo "  Install it on this server:  pipx install ansible" >&2
    echo "  (or: python3 -m pip install --user ansible)" >&2
    exit 1
fi

if [[ ! -f "${CA_FILE}" ]]; then
    echo -e "${RED}✗ rootCA.pem not found at ${CA_FILE}${NC}" >&2
    echo "  Generate the CA first: mkcert -install  (see docs/tls.md)" >&2
    exit 1
fi

if [[ ! -f "${INVENTORY}" ]]; then
    echo -e "${RED}✗ No inventory at ${INVENTORY}${NC}" >&2
    echo "  Copy the example and list your devices:" >&2
    echo "    cp ansible/hosts.example.yml ansible/hosts.yml" >&2
    exit 1
fi

# Use the default inventory unless the user supplied their own -i / --inventory.
has_inventory=0
for arg in "$@"; do
    if [[ "${arg}" == "-i" || "${arg}" == --inventory* ]]; then
        has_inventory=1
    fi
done

args=("$@")
if [[ "${has_inventory}" -eq 0 ]]; then
    args=(-i "${INVENTORY}" "${args[@]}")
fi

echo -e "${GREEN}▶ Running trust-ca playbook (CA: ${CA_FILE})${NC}"
ansible-playbook "${args[@]}" -e "ca_src=${CA_FILE}" "${PLAYBOOK}"
