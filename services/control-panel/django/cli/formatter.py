"""CLI text formatter — plain text and ANSI color output for fish functions.

The formatter produces aligned, human-readable text from structured data.
Color is controlled by the ?color=true query param or Accept: text/x-terminal
header. Plain text is the default for pipe safety.
"""
import re


# ANSI color codes
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def wants_color(request) -> bool:
    """Determine if the client wants colored output."""
    # Explicit query param takes precedence
    color_param = request.query_params.get("color")
    if color_param is not None:
        return color_param.lower() in ("true", "1", "yes")
    # Check Accept header
    accept = request.META.get("HTTP_ACCEPT", "")
    if "text/x-terminal" in accept:
        return True
    # Check TTY (not reliable behind reverse proxy, but harmless)
    return False


def text_response(text: str, status: int = 200):
    """Return a plain text HttpResponse."""
    from django.http import HttpResponse
    return HttpResponse(text, content_type="text/plain; charset=utf-8", status=status)


class Formatter:
    """Builds formatted text output from structured data."""

    def __init__(self, color: bool = False):
        self.color = color
        self._lines: list[str] = []

    def line(self, text: str = "") -> "Formatter":
        self._lines.append(text)
        return self

    def blank(self) -> "Formatter":
        self._lines.append("")
        return self

    def heading(self, text: str) -> "Formatter":
        if self.color:
            self._lines.append(f"{C.BOLD}{C.CYAN}{text}{C.RESET}")
        else:
            self._lines.append(text)
        return self

    def success(self, text: str) -> "Formatter":
        if self.color:
            self._lines.append(f"{C.GREEN}{text}{C.RESET}")
        else:
            self._lines.append(text)
        return self

    def error(self, text: str) -> "Formatter":
        if self.color:
            self._lines.append(f"{C.RED}{text}{C.RESET}")
        else:
            self._lines.append(text)
        return self

    def warning(self, text: str) -> "Formatter":
        if self.color:
            self._lines.append(f"{C.YELLOW}{text}{C.RESET}")
        else:
            self._lines.append(text)
        return self

    def dim(self, text: str) -> "Formatter":
        if self.color:
            self._lines.append(f"{C.DIM}{text}{C.RESET}")
        else:
            self._lines.append(text)
        return self

    def status_dot(self, status: str) -> str:
        """Return a colored status indicator."""
        if not self.color:
            return status
        colors = {
            "running": C.GREEN,
            "healthy": C.GREEN,
            "up": C.GREEN,
            "ok": C.GREEN,
            "exited": C.RED,
            "down": C.RED,
            "unhealthy": C.RED,
            "error": C.RED,
            "failed": C.RED,
            "warning": C.YELLOW,
            "stalled": C.YELLOW,
            "starting": C.YELLOW,
            "paused": C.YELLOW,
        }
        color = colors.get(status.lower(), C.WHITE)
        return f"{color}{status}{C.RESET}"

    def table(self, headers: list[str], rows: list[list[str]], align: list[str] | None = None) -> "Formatter":
        """Render an aligned table."""
        if not rows:
            self._lines.append("  (none)")
            return self

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))

        # Header
        header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        if self.color:
            header_line = f"{C.BOLD}{header_line}{C.RESET}"
        self._lines.append(header_line)

        # Separator
        sep = "  ".join("─" * w for w in widths)
        self._lines.append(sep)

        # Rows
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                w = widths[i] if i < len(widths) else len(str(cell))
                cells.append(str(cell).ljust(w))
            self._lines.append("  ".join(cells))

        return self

    def kv(self, key: str, value: str) -> "Formatter":
        """Render a key-value pair."""
        if self.color:
            self._lines.append(f"  {C.BOLD}{key}:{C.RESET} {value}")
        else:
            self._lines.append(f"  {key}: {value}")
        return self

    def build(self) -> str:
        return "\n".join(self._lines)
