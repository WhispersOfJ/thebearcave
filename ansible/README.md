# Ansible — automate CA trust on LAN devices

Installs the Bear Cave mkcert root CA into every device's **system trust store**
so all `*.nip.io` hostnames validate with no browser warning — no manual steps
per device. Idempotent: re-running after everything is trusted is a no-op.

## How it works

| Target OS | Trust store | Action |
|-----------|-------------|--------|
| Debian/Ubuntu | `/usr/local/share/ca-certificates/` | `update-ca-certificates` |
| RHEL/Fedora | `/etc/pki/ca-trust/source/anchors/` | `update-ca-trust` |
| Archlinux | `/etc/ca-certificates/trust-source/anchors/` | `update-ca-trust` |
| macOS | System keychain | `security add-trusted-cert` |
| Windows | Local Machine Root store | `certutil -addstore -f ROOT` |
| Firefox (optional) | per-profile NSS stores | `certutil -A` |

Firefox on Linux/macOS does **not** read the system store, so it needs the
optional NSS import (`install_firefox_nss=true`) or a one-time manual import.

## Prerequisites

**Control node (this server):**
- `ansible` — `pipx install ansible` (or `python3 -m pip install --user ansible`)
- The CA file at `~/.local/share/mkcert/rootCA.pem` (from `mkcert -install`)

**Linux / macOS targets:**
- Passwordless SSH from the server: `ssh-copy-id user@host`
- Python 3 (Ansible needs it on POSIX targets)
- `openssl` on Linux targets (used to verify the trust-store link)

**Windows targets:**
- WinRM configured per the
  [Ansible Windows guide](https://docs.ansible.com/ansible/latest/os_guide/windows_setup.html)
  (e.g. `ansible_winrm_transport: credssp` for domain/credssp auth)
- The `ansible.windows` collection: `ansible-galaxy collection install ansible.windows`

## Setup

```bash
cp ansible/hosts.example.yml ansible/hosts.yml
# …edit ansible/hosts.yml: host IPs, SSH users, Windows WinRM settings…
```

`ansible/hosts.yml` is gitignored (it names your LAN devices/users).

## Run

```bash
./scripts/ansible-trust-ca.sh                          # default inventory
./scripts/ansible-trust-ca.sh -i my-inventory.yml      # custom inventory
./scripts/ansible-trust-ca.sh --ask-pass --ask-become-pass   # SSH password auth
./scripts/ansible-trust-ca.sh -e install_firefox_nss=true     # + Firefox NSS
```

Or skip the wrapper:

```bash
ansible-playbook -i ansible/hosts.yml ansible/playbooks/trust-ca.yml
```

Overrides (via `-e`): `ca_src=/path/to/rootCA.pem` (CA on the control node),
`install_firefox_nss=true`.

## Verification

The playbook asserts each target actually trusts the CA:

- Linux — checks the hashed symlink (`<hash>.0`) exists in the bundle
- macOS — `security find-certificate -c mkcert` in the System keychain
- Windows — `certutil -store ROOT mkcert`

After a green run, browse to `https://bearcave.192.168.4.20.nip.io` from each
device — the padlock should be valid.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `rootCA.pem not found` | Run `mkcert -install` on the server first |
| `unreachable` for a host | SSH key not copied / WinRM not reachable — check `ansible -m ping` |
| macOS task fails | The `security` command needs admin — is `become` working (sudo)? |
| Firefox still warns | Enable `-e install_firefox_nss=true` (or import manually once) |
| Windows task fails | Install the collection (`ansible.windows`) and check WinRM auth settings |
| CA regenerated | Re-run the playbook — `copy` detects the new content and refreshes all stores |
