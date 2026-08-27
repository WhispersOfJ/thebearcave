"""Arr import file testing — dd read test and candidate file discovery.

Extracted from core/arr_client.py. These functions test whether download
output files are readable via container exec, used by the import starvation
and auto-fix flows.
"""

IMPORTING_TEST_TIMEOUT_S = 40
IMPORTING_TEST_MB = 5


def dd_test_file(container, file_path: str) -> tuple[bool, str]:
    try:
        result = container.exec_run(
            cmd=["timeout", str(IMPORTING_TEST_TIMEOUT_S), "dd", f"if={file_path}", "of=/dev/null", "bs=1M",
                 f"count={IMPORTING_TEST_MB}"],
            demux=True,
        )
    except Exception as e:
        return False, f"exec failed: {e}"
    if result.exit_code == 0:
        return True, "readable"
    stderr = b""
    if result.output and result.output[1]:
        stderr = result.output[1]
    return False, stderr.decode(errors="replace").strip() or f"dd exited {result.exit_code}"


def find_candidate_files(container, output_path: str) -> tuple[str, list[str]]:
    """Returns (status, files): 'missing' if output_path doesn't exist on
    disk at all, 'empty' if the path exists but has no file worth testing,
    or 'ok' with the files found."""
    exists = container.exec_run(cmd=["test", "-e", output_path])
    if exists.exit_code != 0:
        return "missing", []
    find_result = container.exec_run(cmd=["find", output_path, "-maxdepth", "2", "-type", "l"])
    files = [f for f in find_result.output.decode(errors="replace").splitlines() if f.strip()]
    if not files:
        find_result = container.exec_run(cmd=["find", output_path, "-maxdepth", "2", "-type", "f"])
        files = [f for f in find_result.output.decode(errors="replace").splitlines() if f.strip()]
    return ("ok", files) if files else ("empty", [])
