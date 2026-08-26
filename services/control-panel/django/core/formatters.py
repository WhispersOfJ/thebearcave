"""Shared formatting utilities for the control panel."""


def human_size(n: int | float | None, fallback: str = "?") -> str:
    """Convert a byte count to a human-readable string (e.g. '1.5 GB').

    Returns `fallback` for None/0/empty values. Handles negative values
    (e.g. Docker's -1 for unbounded memory) by taking the absolute value.
    """
    if not n:
        return fallback
    size = abs(float(n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} PB"
