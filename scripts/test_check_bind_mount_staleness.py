#!/usr/bin/env python3
"""Regression test for scripts/check_bind_mount_staleness.py.

Verifies the inode-staleness guard cannot silently bit-rot:

  * host_inode / container_inode parse stat output correctly
  * a matching inode is not flagged
  * a mismatched inode IS flagged
  * a container stat failure (missing file / no stat binary) IS flagged
  * directory binds are skipped (only regular files are inode-checked)
  * not-running services are skipped (nothing to compare)

Runs against importable pure-Python logic (no live docker needed), so it
works on the CI runner. Run by .github/workflows/validate.yml and locally
via `python3 scripts/test_check_bind_mount_staleness.py`. Exits 0 when
every assertion holds, 1 otherwise.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = ROOT / "scripts" / "check_bind_mount_staleness.py"

spec = importlib.util.spec_from_file_location("check_bind_mount_staleness", CHECKER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    failures = 0

    def expect(name, got, want):
        nonlocal failures
        if got == want:
            print(f"OK: {name} (got {got})")
        else:
            print(f"FAIL: {name} expected {want}, got {got}")
            failures += 1

    # --- host_inode / container_inode parsing ---------------------------
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello")
        host_file = f.name
    import os
    real_inode = int(os.stat(host_file).st_ino)

    expect("host_inode parses a real file", mod.host_inode(host_file), real_inode)
    expect("host_inode None for missing path", mod.host_inode("/nonexistent/path/xyz"), None)

    # Stub run() to return canned stat output for container_inode.
    real_run = mod.run

    class FakeProc:
        def __init__(self, rc, out):
            self.returncode = rc
            self.stdout = out
            self.stderr = ""

    def fake_run_match(cmd, timeout=None):
        return FakeProc(0, str(real_inode))

    def fake_run_mismatch(cmd, timeout=None):
        return FakeProc(0, str(real_inode + 999))

    def fake_run_fail(cmd, timeout=None):
        return FakeProc(1, "")

    mod.run = fake_run_match
    expect("container_inode matches when stat agrees",
           mod.container_inode("c", "/x"), real_inode)

    mod.run = fake_run_mismatch
    expect("container_inode returns divergent inode",
           mod.container_inode("c", "/x"), real_inode + 999)

    mod.run = fake_run_fail
    expect("container_inode None when stat fails",
           mod.container_inode("c", "/x"), None)

    # --- container_content_hash (distroless fallback) -----------------
    # docker cp writes the host file to a temp path; with run() stubbed to
    # succeed, the temp file content == the real file's hash.

    def fake_cp_ok(cmd, timeout=None):
        # `docker cp name:path tmpfile` — simulate by copying the real file.
        if cmd[:2] == ["docker", "cp"]:
            dst = cmd[-1]
            import shutil
            shutil.copy2(host_file, dst)
            return FakeProc(0, "")
        return FakeProc(1, "")

    def fake_cp_fail(cmd, timeout=None):
        return FakeProc(1, "cp failed")

    mod.run = fake_cp_ok
    expect("container_content_hash returns host hash on successful cp",
           mod.container_content_hash("c", "/x"), mod._file_hash(host_file))

    mod.run = fake_cp_fail
    expect("container_content_hash None when docker cp fails",
           mod.container_content_hash("c", "/x"), None)

    mod.run = real_run

    # --- single_file_binds: directory binds are skipped ----------------
    # Build a fake services dict + monkeypatch compose + Path.is_file.
    tmpdir = tempfile.mkdtemp()
    regular = Path(tmpdir) / "config.yml"
    regular.write_text("k: v")
    subdir = Path(tmpdir) / "data"
    subdir.mkdir()

    services = {
        "svc_file": {
            "volumes": [
                {"type": "bind", "source": str(regular), "target": "/etc/config.yml"},
                {"type": "bind", "source": str(subdir), "target": "/data"},
                {"type": "volume", "source": "voldata", "target": "/v"},
                {"type": "bind"},  # no source/target — skipped
            ]
        },
        "svc_down": {  # not running — skipped
            "volumes": [{"type": "bind", "source": str(regular), "target": "/x"}]
        },
    }

    # Force compose ps to report only svc_file running.
    class FakeCompose:
        returncode = 0
        stdout = '{"Service":"svc_file","Name":"svc_file_1"}\n'

    real_compose = mod.compose
    mod.compose = lambda args: FakeCompose()

    binds = list(mod.single_file_binds(services, ROOT))
    mod.compose = real_compose

    # Only the regular-file bind for the running service should appear.
    targets = sorted(b[3] for b in binds)
    expect("single_file_binds: only regular file on running service",
           targets, ["/etc/config.yml"])
    # And the tuple shape is correct.
    if binds:
        svc, name, host, dst = binds[0]
        expect("single_file_binds tuple shape", (svc, name, dst),
               ("svc_file", "svc_file_1", "/etc/config.yml"))
    else:
        print("FAIL: single_file_binds yielded nothing")
        failures += 1

    # --- --offline CLI smoke --------------------------------------------
    import subprocess
    proc = subprocess.run([sys.executable, str(CHECKER_PATH), "--offline"],
                          capture_output=True, text=True)
    expect("--offline CLI -> exit 0", proc.returncode, 0)

    if failures:
        print(f"\n{failures} assertion(s) failed")
        return 1
    print("\nall check_bind_mount_staleness tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
