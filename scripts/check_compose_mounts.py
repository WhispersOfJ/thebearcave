#!/usr/bin/env python3
"""Fail when a docker-compose volume entry holds multiple mount pairs on one line.

The merged-mount defect: two YAML volume list items accidentally collapse onto a
single line, e.g.

    - ./media/movies:/data/movies      - ./media/shows:/data/shows

YAML happily parses that as ONE scalar, so `docker compose config` stays green;
Docker then mounts the garbage target `/data/movies      - ./media/shows` and
every consumer of the intended mount silently loses it (see the plex
anime-consolidation incident — plex ran for hours with no /data/shows mount).

This check scans the raw compose file, so the defect cannot silently ship again.
A line is flagged when a `- ` list item contains a second ` - ` fragment and
every fragment looks like a `source:target` mount pair (path or volume name,
colon, remainder). Port and environment entries share the same merged-line
defect class and are flagged too — the fix is always to split onto separate
lines.

Run by scripts/preflight.sh and .github/workflows/validate.yml.

Usage:
  python3 scripts/check_compose_mounts.py [compose-file]
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPOSE = ROOT / "docker-compose.yml"

# A YAML list item: optional indent, dash, whitespace, then the item body.
ITEM_RE = re.compile(r"^(\s*)-\s+(.*)$")
# Anything that looks like a source:target mount pair (or port mapping), a
# named volume, or a KEY=value environment entry: a non-separator prefix, the
# separator, then content.
PAIR_RE = re.compile(r"^[^:\s][^:\s]*:.+$|^[^=\s][^=\s]*=.+$")
# A second list-item fragment glued onto the same line: whitespace, dash, whitespace.
GLUE_RE = re.compile(r"\s+-\s+")


def strip_comment(line: str) -> str:
    """Cut a trailing ` # comment` (the repo uses `# LAN DNS ...` style)."""
    return re.split(r"\s+#", line, maxsplit=1)[0].rstrip()


def find_merged_mounts(compose_path: Path) -> list[tuple[int, str]]:
    """Return (line_no, offending_line) for every merged mount/port/env entry."""
    problems: list[tuple[int, str]] = []
    for line_no, raw in enumerate(compose_path.read_text().splitlines(), start=1):
        match = ITEM_RE.match(raw)
        if not match:
            continue
        body = strip_comment(match.group(2)).strip()
        if not body:
            continue
        fragments = GLUE_RE.split(body)
        if len(fragments) < 2:
            continue
        # Only flag when every fragment looks like a mapping entry — a comment
        # or prose with ` - ` in it must not trip the check.
        if all(PAIR_RE.match(frag) for frag in fragments):
            problems.append((line_no, raw.strip()))
    return problems


def main() -> int:
    compose = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COMPOSE
    if not compose.exists():
        print(f"CHECK FAILED: {compose} not found")
        return 1

    problems = find_merged_mounts(compose)

    if not problems:
        print(f"OK: no merged mount/port/env entries in {compose.name}.")
        return 0

    print(
        f"CHECK FAILED: {len(problems)} line(s) in {compose.name} hold multiple "
        "list items merged onto one line. Split each `- ` entry onto its own "
        "line, e.g.:\n"
        "    - ./media/movies:/data/movies\n"
        "    - ./media/shows:/data/shows\n"
    )
    for line_no, line in problems:
        print(f"  {compose.name}:{line_no}: {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
