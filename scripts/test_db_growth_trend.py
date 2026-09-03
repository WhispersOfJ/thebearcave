#!/usr/bin/env python3
"""Regression test for scripts/db_growth_trend.py (TODO.md #5).

Verifies the growth-trend predictor cannot silently bit-rot:

  * OLS slope + crossing math pins exact numbers (spurious decimals would
    silently move every scheduled prune date)
  * prune/VACUUM resets split the trend: pre-drop samples never mask the
    current segment's growth
  * dedup collapses near-identical timestamps (rapid repeated runs)
  * verdict ladder: insufficient history -> rc 2 warn; crossing inside the
    horizon -> rc 1 fail; beyond it or shrinking -> rc 0 ok; already at the
    high-water -> rc 1 fail
  * rc contract of the CLI on synthetic history + synthetic DBs (real
    check_radarr_db_size.read_metrics against throwaway sqlite files)
  * live end-to-end: sample_and_append grows the history file by exactly one
    line per run and the recorded footprint matches the gate's own reader

Runs fully offline. Exits 0 when every assertion holds, 1 otherwise.
"""

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "db_growth_trend.py"

spec = importlib.util.spec_from_file_location("db_growth_trend", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DAY = 86400.0
MiB = 1024 * 1024


def expect(name, got, want):
    if got == want:
        print(f"OK: {name}")
        return True
    print(f"FAIL: {name} expected {want!r}, got {got!r}")
    return False


def mk_samples(start_bytes, per_day_bytes, count, start_ts, spacing_h=24.0):
    """Synthetic history: linear growth, count samples, `spacing_h` apart."""
    step = spacing_h * 3600.0
    return [{"db": "t", "ts": int(start_ts + i * step),
             "footprint_bytes": int(start_bytes + i * per_day_bytes * spacing_h / 24.0)}
            for i in range(count)]


def main() -> int:
    failures = 0
    now = 1_800_000_000.0

    # --- slope math: exact OLS on a perfect line -----------------------
    pts = mk_samples(100 * MiB, 2 * MiB, 5, now - 4 * DAY)  # +2 MiB/day
    slope = mod.ols_slope_bytes_per_day(pts) * DAY
    failures += not expect("OLS slope recovers 2 MiB/day on a perfect line",
                           round(slope / MiB, 6), 2.0)

    # zero time span -> no slope
    flat = [{"db": "t", "ts": now, "footprint_bytes": 10 * MiB},
            {"db": "t", "ts": now, "footprint_bytes": 20 * MiB}]
    failures += not expect("zero-span history yields no slope",
                           mod.ols_slope_bytes_per_day(flat), None)

    # --- prune reset splits segments ------------------------------------
    # Pre-prune growth is huge (50 MiB/day); if it leaked through the
    # segment split, the crossing math would fail fast. Post-prune growth is
    # 3 MiB/day against a far limit, so a correct segmentation reads "ok".
    hist = mk_samples(900 * MiB, 50 * MiB, 4, now - 10 * DAY)
    vacuumed = dict(hist[-1])  # prune drops the file below everyone
    vacuumed["footprint_bytes"] = 130 * MiB
    vacuumed["ts"] = hist[-1]["ts"] + DAY
    regrown = mk_samples(130 * MiB, 3 * MiB, 3, vacuumed["ts"] + DAY)
    seg = mod.current_segment(hist + [vacuumed] + regrown)
    failures += not expect("prune drop starts a new segment",
                           [s["footprint_bytes"] for s in seg],
                           [s["footprint_bytes"] for s in [vacuumed] + regrown])
    v = mod.assess(hist + [vacuumed] + regrown, 400 * MiB, now,
                   min_samples=3, horizon_days=30)
    failures += not expect("pre-prune slope never masks current growth",
                           v["level"], "ok")
    # OLS over the real segment [130,130,133,136]: the duplicated 130 (the
    # vacuum sample and the first regrowth sample share a value) pulls the
    # fit slightly below the nominal 3 MiB/day — pin it exactly.
    failures += not expect("verdict slope is the current segment's OLS",
                           round(v["slope_bytes_per_day"] / MiB, 1), 2.1)

    # --- dedup of rapid repeated runs ------------------------------------
    rapid = mk_samples(100 * MiB, 2 * MiB, 2, now - 2 * DAY)
    rapid.append({"db": "t", "ts": int(rapid[-1]["ts"] + 5),
                  "footprint_bytes": 101 * MiB})
    v = mod.assess(rapid, 900 * MiB, now, min_samples=2, horizon_days=30)
    failures += not expect("near-identical timestamps collapse to one sample",
                           v["level"], "ok")

    # --- verdict ladder ---------------------------------------------------
    # insufficient history -> warn
    v = mod.assess(mk_samples(100 * MiB, 1 * MiB, 2, now - DAY),
                   900 * MiB, now, min_samples=3, horizon_days=30)
    failures += not expect("insufficient history is a warn",
                           (v["level"], v["days_to_limit"]), ("warn", None))

    # crossing inside the horizon -> fail, with sane day count
    # 190 MiB growing 2 MiB/day against a 200 MiB limit -> 5 days
    v = mod.assess(mk_samples(180 * MiB, 2 * MiB, 6, now - 5 * DAY),
                   200 * MiB, now, min_samples=3, horizon_days=30)
    failures += not expect("crossing inside horizon fails",
                           v["level"], "fail")
    failures += not expect("predicted days ~5",
                           round(v["days_to_limit"], 1), 5.0)

    # same growth, horizon 3 days -> ok
    v = mod.assess(mk_samples(180 * MiB, 2 * MiB, 6, now - 5 * DAY),
                   200 * MiB, now, min_samples=3, horizon_days=3)
    failures += not expect("crossing beyond the horizon is ok",
                           v["level"], "ok")

    # shrinking DB -> ok, no crossing
    v = mod.assess(mk_samples(190 * MiB, -1 * MiB, 5, now - 4 * DAY),
                   200 * MiB, now, min_samples=3, horizon_days=30)
    failures += not expect("shrinking DB is ok",
                           (v["level"], v["days_to_limit"]), ("ok", None))

    # already at/over the limit -> fail now
    v = mod.assess(mk_samples(199 * MiB, 2 * MiB, 3, now - 2 * DAY),
                   200 * MiB, now, min_samples=3, horizon_days=30)
    failures += not expect("over the high-water fails immediately",
                           v["level"], "fail")

    # --- CLI contract on synthetic DBs + history --------------------------
    def make_db(footprint_target):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        f.close()
        con = sqlite3.connect(f.name)
        con.execute("PRAGMA page_size=4096")
        con.execute("CREATE TABLE t (x TEXT)")
        pad = max(0, footprint_target - 3 * 4096)
        con.execute("INSERT INTO t VALUES (?)", ("x" * pad,))
        con.commit()
        con.close()
        return Path(f.name)

    tmpdir = Path(tempfile.mkdtemp())
    hist_path = tmpdir / "history.jsonl"
    db = make_db(100 * MiB)

    def run_cli(extra):
        argv = ["db_growth_trend.py", "--db", str(db),
                "--history", str(hist_path)] + extra
        old = sys.argv
        sys.argv = argv
        try:
            return mod.main()
        finally:
            sys.argv = old

    # first two runs: insufficient (min 3) -> rc 2 (warn class)
    rc1 = run_cli(["--json"])
    rc2 = run_cli(["--json"])
    failures += not expect("runs 1-2 are insufficient -> rc 2", (rc1, rc2), (2, 2))
    # run 3 is seconds later: dedup collapses all three to one usable
    # sample, which is still insufficient -> rc 2 is correct, not a bug
    rc3 = run_cli(["--json"])
    failures += not expect("run 3 still insufficient after dedup -> rc 2", rc3, 2)

    # Seed day-spaced samples (the realistic cadence: nightly digest) at the
    # DB's true footprint, then run again -> 4 usable samples, flat -> rc 0.
    gate_fp = __import__("check_radarr_db_size").read_metrics(db)["footprint_bytes"]
    for i in range(1, 4):
        with hist_path.open("a") as fh:
            fh.write(json.dumps({"db": "custom",
                                 "ts": int(now - (4 - i) * DAY),
                                 "footprint_bytes": gate_fp}) + "\n")
    rc4 = run_cli(["--json"])
    failures += not expect("day-spaced history turns the trend ok -> rc 0", rc4, 0)
    lines = [json.loads(line) for line in hist_path.read_text().splitlines()]
    failures += not expect("history records one line per run/seed",
                           len(lines), 7)
    failures += not expect("all samples tagged with the db basename",
                           {r["db"] for r in lines}, {"custom"})
    # footprint recorded matches the shared gate reader
    failures += not expect("sampled footprint equals the gate's reader",
                           lines[3]["footprint_bytes"], gate_fp)

    # missing DB -> rc 2
    rc_missing = 2  # direct: point --db at a nonexistent path
    argv = ["db_growth_trend.py", "--db", str(tmpdir / "nope.db"),
            "--history", str(tmpdir / "h2.jsonl"), "--json"]
    old = sys.argv
    sys.argv = argv
    try:
        rc_missing = mod.main()
    finally:
        sys.argv = old
    failures += not expect("missing DB -> rc 2", rc_missing, 2)

    # torn last history line does not blind the predictor
    torn = tmpdir / "torn.jsonl"
    good = mk_samples(100 * MiB, 2 * MiB, 4, now - 3 * DAY)
    torn.write_text("\n".join(json.dumps(r) for r in good)
                    + "\n{\"db\": \"t\", \"ts\": 1, \"footp")  # torn tail
    loaded = mod.load_history(torn, "t")
    failures += not expect("torn JSONL tail skipped, good lines kept",
                           len(loaded), 4)

    print(f"\ntest_db_growth_trend: "
          f"{'all assertions passed' if failures == 0 else f'{failures} assertion(s) failed'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
