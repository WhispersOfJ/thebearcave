#!/usr/bin/env python3
"""Run a scoped, verified Sonarr missing-episode search.

The search engine lives in ``search_missing_scoped_core.py``. This file is
only the executable interface: argument validation, API-key loading, and
human-readable rendering.

Read-only by default. Pass --apply to POST search commands. Pass --verify to
re-parse new grabs and abort on NO_MATCH, zero episodes, or a different
requested series. Applied commands are paced and the default checkpoint
stops after each batch for review.

Exit codes:
  0  completed, or stopped at a checkpoint
  1  API/network/configuration failure
  2  --verify found a suspect grab; the sweep was aborted

Usage:
  python3 scripts/search_missing_scoped.py --series 25891
  python3 scripts/search_missing_scoped.py --all --batch 10
  python3 scripts/search_missing_scoped.py --series 25891 --apply --verify
  python3 scripts/search_missing_scoped.py --all --apply --yes
"""

import argparse
import os
import sys
import urllib.error

try:
    from search_missing_scoped_core import (
        DEFAULT_BATCH,
        DEFAULT_CHECKPOINT_PATH,
        DEFAULT_GAP,
        DEFAULT_QUIET_WINDOW,
        DEFAULT_TIMEOUT,
        DEFAULT_URL,
        SearchConfig,
        SearchEngine,
        SonarrClient,
    )
except ImportError:
    # Allow direct execution from any working directory, including callers
    # that invoke this file by absolute path.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from search_missing_scoped_core import (
        DEFAULT_BATCH,
        DEFAULT_CHECKPOINT_PATH,
        DEFAULT_GAP,
        DEFAULT_QUIET_WINDOW,
        DEFAULT_TIMEOUT,
        DEFAULT_URL,
        SearchConfig,
        SearchEngine,
        SonarrClient,
    )


def positive_int(value):
    """Argparse type for values that must be greater than zero."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def nonnegative_int(value):
    """Argparse type for values that may be zero but not negative."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def render(result):
    """Render the core result without changing engine state."""
    for report in result.reports:
        print(
            f"batch {report.number}/{report.total}: "
            f"{report.episodes} episode(s), "
            f"{len(report.commands)} command(s)"
        )
        for group in report.groups:
            print(
                f"  series {group['seriesId']} S{group['seasonNumber']:02d} "
                f"({len(group['episodes'])} missing, last search "
                f"{group['last_search'] or 'never'})"
            )
        if report.dry_run:
            for command in report.commands:
                print(f"  [dry] POST /command {command}")
        verification = report.verification
        if verification:
            if not verification.history_available:
                print("  verify: history API unavailable; queue diff only")
            if verification.offenders:
                print("VERIFY FAILED -- aborting sweep:")
                for offender in verification.offenders:
                    print(
                        f"  {offender['title']} | "
                        f"series {offender['seriesId']} | "
                        f"parsed {offender['parsed']}"
                    )
            elif report.dry_run:
                print("  verify (dry-run, nothing searched): 0 suspect(s) -> OK")
            else:
                print(
                    f"  verify: {verification.history_count} new grab(s), "
                    f"{verification.queue_count} new queue item(s), "
                    "all parse to their own series"
                )
        if result.summary.startswith("checkpoint after"):
            print(
                "checkpoint: review this batch, then re-run with the same "
                "arguments; groups are ordered by lastSearchTime."
            )
    if result.summary == "no missing episodes to search":
        print(result.summary)
    elif not result.reports:
        print(result.summary)
    elif result.summary == "complete":
        print(result.summary)
    return result.exit_code


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument(
        "--series", type=positive_int, action="append", metavar="ID",
        help="Sonarr series ID(s) to search (repeatable)"
    )
    scope.add_argument(
        "--all", action="store_true",
        help="all monitored series with missing episodes"
    )
    parser.add_argument(
        "--url", default=os.environ.get("SONARR_URL", DEFAULT_URL),
        help="API base URL (default: %(default)s)"
    )
    parser.add_argument(
        "--api-key", default="",
        help="API key (default: $SONARR_API_KEY)"
    )
    parser.add_argument(
        "--batch", type=positive_int, default=DEFAULT_BATCH,
        help="max episodes searched per batch (default: %(default)s)"
    )
    parser.add_argument(
        "--gap", type=nonnegative_int, default=DEFAULT_GAP,
        help="pause seconds between batches (default: %(default)s; 0 disables)"
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="disable checkpoints; run every batch in one pass"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="parse-check new grabs and queue items after each batch"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="actually POST search commands; default is a dry run"
    )
    parser.add_argument(
        "--timeout", type=positive_int, default=DEFAULT_TIMEOUT,
        help="HTTP timeout seconds (default: %(default)s)"
    )
    parser.add_argument(
        "--quiet-window", type=positive_int, default=DEFAULT_QUIET_WINDOW,
        help="seconds without a new observation before verify passes (default: %(default)s)"
    )
    parser.add_argument(
        "--checkpoint-path", default=DEFAULT_CHECKPOINT_PATH,
        help="checkpoint JSON path (default: %(default)s)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="resume the existing applied checkpoint; never starts a new plan"
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    api_key = args.api_key or os.environ.get("SONARR_API_KEY", "")
    if not api_key:
        print(
            "SONARR_API_KEY not set (pass --api-key or export SONARR_API_KEY)",
            file=sys.stderr,
        )
        return 1
    config = SearchConfig(
        series_ids=tuple(args.series) if args.series else None,
        all_series=args.all,
        batch_size=args.batch,
        gap=args.gap,
        checkpoint=not args.yes,
        verify=args.verify,
        apply=args.apply,
        timeout=args.timeout,
        quiet_window=args.quiet_window,
        checkpoint_path=args.checkpoint_path,
        base_url=args.url,
    )
    try:
        result = SearchEngine(
            SonarrClient(args.url, api_key, args.timeout), config
        ).run(resume=args.resume)
    except (urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
        print(f"API/network failure: {exc}", file=sys.stderr)
        return 1
    return render(result)


if __name__ == "__main__":
    sys.exit(main())
