#!/usr/bin/env python3
"""Regression test for scripts/alias_candidates.py.

Verifies the alias-candidate miner cannot silently bit-rot:

  * classification pins exactly: TITLE_MATCH / WRONG_SHOW / NO_MATCH
  * distinct (series, release-title) dedup — one parse call per pair
  * unanchored rows (no series id / empty source title) are skipped
  * the parse-call cap truncates with the flag set, not silently
  * Sonarr date parsing: Z-suffixed, offset, and naive-UTC forms
  * CLI rc contract: 0 clean / 1 candidates / 2 unreachable (offline)

Runs against the importable pure helpers with an injected parse table — no
Sonarr and no network — so it works on the CI runner. Run by validate.yml and
nightly-healthcheck.yml, and locally via
`python3 scripts/test_alias_candidates.py`. Exits 0 when every assertion
holds, 1 otherwise.
"""

import contextlib
import importlib.util
import io
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "alias_candidates.py"

spec = importlib.util.spec_from_file_location("alias_candidates", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = 0


def expect(name, got, want):
    global failures
    if got == want:
        print(f"OK: {name}")
    else:
        print(f"FAIL: {name} expected {want!r}, got {got!r}")
        failures += 1


def history_row(sid, s_title, source, date="2026-09-01T19:00:00Z"):
    return {"series": {"id": sid, "title": s_title},
            "sourceTitle": source, "date": date}


def table_parse(table):
    """parse_fn from {(title): (id|None, title)}; unknown -> no match."""
    def parse_fn(title):
        pid, p_title = table.get(title, (None, ""))
        return {"id": pid, "title": p_title}
    return parse_fn


# --- classification ---------------------------------------------------------

rows = [
    history_row(1, "Good Show", "Good.Show.S01E01"),       # same series
    history_row(2, "Other Show", "Good.Show.S01E01"),      # parse -> series 1
    history_row(3, "Alias Gap", "Variant.Title.S01E01"),   # parse -> nothing
]
table = {
    "Good.Show.S01E01": (1, "Good Show"),
    "Variant.Title.S01E01": (None, ""),
}
report = mod.classify_grabs(rows, table_parse(table), gap=0)
expect("counts", report["counts"],
       {"TITLE_MATCH": 1, "WRONG_SHOW": 1, "NO_MATCH": 1})
expect("candidate is NO_MATCH",
       [r["release_title"] for r in report["results"]
        if r["class"] == "NO_MATCH"],
       ["Variant.Title.S01E01"])
expect("wrong-show keeps parsed target",
       [r["parsed_title"] for r in report["results"]
        if r["class"] == "WRONG_SHOW"],
       ["Good Show"])

# --- dedup: one parse per distinct (series, title) pair ---------------------

rows = [history_row(1, "Good Show", "Same.Title.S01E01", date=f"2026-09-0{d}T19:00:00Z")
        for d in (1, 2, 3)]
calls = {"n": 0}


def counting_parse(title):
    calls["n"] += 1
    return {"id": 1, "title": "Good Show"}


report = mod.classify_grabs(rows, counting_parse, gap=0)
expect("dedup to one call", calls["n"], 1)
expect("grabs_total distinct", report["grabs_total"], 1)

# --- unanchored rows skipped -------------------------------------------------

rows = [
    history_row(1, "Good Show", "A.S01E01"),
    {"series": None, "sourceTitle": "Orphan.S01E01", "date": "2026-09-01T19:00:00Z"},
    history_row(1, "Good Show", ""),
    {"series": {"id": 1, "title": "Good Show"}, "sourceTitle": None,
     "date": "2026-09-01T19:00:00Z"},
]
report = mod.classify_grabs(rows, counting_parse, gap=0)
expect("unanchored skipped", report["grabs_total"], 1)

# --- parse-call cap truncates loudly ----------------------------------------

rows = [history_row(i, f"Show {i}", f"Title.{i}.S01E01") for i in range(1, 6)]
report = mod.classify_grabs(rows, counting_parse, gap=0, max_parse_calls=2)
expect("cap stops at limit", report["grabs_checked"], 2)
expect("cap flags truncation", report["truncated"], True)
expect("cap keeps total visible", report["grabs_total"], 5)
expect("no truncation when under cap",
       mod.classify_grabs(rows[:2], counting_parse, gap=0)["truncated"], False)

# --- date parsing: Z, offset, naive-UTC, junk --------------------------------

expect("Z suffix", mod._parse_sonarr_date("2026-09-01T19:00:00Z"),
       datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc))
expect("explicit offset", mod._parse_sonarr_date("2026-09-01T19:00:00+02:00"),
       datetime(2026, 9, 1, 17, 0, tzinfo=timezone.utc))
expect("naive assumed UTC", mod._parse_sonarr_date("2026-09-01T19:00:00"),
       datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc))
expect("junk -> None", mod._parse_sonarr_date("not-a-date"), None)

# --- window filter helper (fetch_grabbed's early-return contract) ------------

newer = history_row(1, "S", "New.S01E01", date="2026-09-03T10:00:00Z")
older = history_row(1, "S", "Old.S01E01", date="2026-09-01T10:00:00Z")
since = datetime(2026, 9, 2, tzinfo=timezone.utc)
kept = [r for r in [newer, older]
        if (w := mod._parse_sonarr_date(r["date"])) is not None and w >= since]
expect("window keeps only newer", [r["sourceTitle"] for r in kept],
       ["New.S01E01"])
expect("window math uses timedelta",
       (datetime.now(timezone.utc) - timedelta(days=7)) >
       datetime.now(timezone.utc) - timedelta(days=8), True)

# --- CLI rc contract (offline: unreachable Sonarr must be rc 2) --------------

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = mod.main(["--url", "http://127.0.0.1:1/api/v3", "--api-key", "x",
                   "--days", "1"])
expect("unreachable rc 2", rc, 2)
expect("skip message", "CHECK SKIPPED" in buf.getvalue(), True)

# missing key -> rc 2 before any network attempt
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = mod.main(["--api-key", ""])
expect("missing key rc 2", rc, 2)

# HTTPError subclass must be caught by the same skip path (rc 2, not a raise)
class FakeHTTPError(urllib.error.HTTPError):
    def __init__(self):
        super().__init__("url", 401, "unauthorized", None, None)


def boom(*_a, **_k):
    raise FakeHTTPError()


orig_fetch = mod.fetch_grabbed
mod.fetch_grabbed = boom
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = mod.main(["--url", "http://localhost:1/api/v3", "--api-key", "x"])
mod.fetch_grabbed = orig_fetch
expect("http error rc 2", rc, 2)

# --- offline helpers: print_report is stable on empty results ----------------

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    mod.print_report({"counts": {"TITLE_MATCH": 0, "WRONG_SHOW": 0,
                                 "NO_MATCH": 0},
                      "grabs_checked": 0, "grabs_total": 0,
                      "truncated": False, "results": []}, 7)
expect("empty report prints cleanly", "NO_MATCH: 0" in buf.getvalue(), True)

sys.exit(1 if failures else 0)
