#!/usr/bin/env python3
"""Check local watchlist data health before backtesting."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.src.data.watchlist_data_health import check_watchlist_data, format_report_table

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check local data completeness for a watchlist before backtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--watchlist",
        "-w",
        type=str,
        default="watchlist/us_futures_watchlist.csv",
        help="watchlist CSV path (default: watchlist/us_futures_watchlist.csv)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="local data directory (default: data)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["table", "json", "both"],
        default="both",
        help="output format (default: both)",
    )
    parser.add_argument(
        "--json-output",
        "-o",
        type=str,
        default=None,
        help="optional path to write JSON report",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="override current timestamp with ISO datetime for deterministic checks",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="enable debug logging",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    watchlist_path = Path(args.watchlist)
    if not watchlist_path.exists():
        print(f"File not found: {args.watchlist}", file=sys.stderr)
        watchlist_dir = Path("watchlist")
        if watchlist_dir.exists():
            print("Available watchlist files:", file=sys.stderr)
            for path in sorted(watchlist_dir.glob("*.csv")):
                print(f"  - {path}", file=sys.stderr)
        return 2

    try:
        now = datetime.fromisoformat(args.now) if args.now else None
    except ValueError:
        print(f"Invalid --now timestamp: {args.now}", file=sys.stderr)
        return 2

    report = check_watchlist_data(watchlist_path=watchlist_path, data_dir=args.data_dir, now=now)
    report_json = report.to_dict()

    if args.format in {"table", "both"}:
        print(format_report_table(report))

    if args.format in {"json", "both"}:
        if args.format == "both":
            print()
        print(json.dumps(report_json, ensure_ascii=False, indent=2))

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("JSON report written to %s", output_path)

    return 0 if report.can_backtest else 1


if __name__ == "__main__":
    sys.exit(main())
