"""``/scan`` CLI command — daily scan plan preview and local-data-only run."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Lazy parquet engine check — raises ImportError with a helpful message if missing.
try:
    import pyarrow.parquet as _pq  # noqa: F401
except ImportError:
    raise ImportError(
        "[pyarrow] is required for Parquet I/O.\n"
        "Install it with: pip install 'vibe-trading-ai[parquet]'\n"
        "Or: pip install pyarrow"
    ) from None

from src.data.scan_plan import build_scan_plan, format_plan_table, format_plan_json
from src.data.scan_validators import validate_watchlist


console = Console()


@click.command()
@click.option(
    "--watchlist", "-w",
    type=str,
    required=True,
    help="Path to watchlist CSV file. Relative paths are resolved relative to the "
         "watchlist/ directory; absolute paths are also accepted.",
)
@click.option(
    "--data-dir", "-d",
    type=str,
    default="data",
    show_default=True,
    help="Root directory containing local parquet data (organized as data/{market}/{symbol}/).",
)
@click.option(
    "--output", "-o",
    type=str,
    default=None,  # None = use date-based default under output/
    help="Output directory. If not provided, defaults to output/YYYY-MM-DD/.",
)
@click.option(
    "--now",
    type=str,
    default=None,
    help="Scan date (ISO-8601, e.g. 2026-06-09). Defaults to today.",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format: 'table' for human-readable, 'json' for machine-readable.",
)
@click.option(
    "--run",
    is_flag=True,
    default=False,
    help="Execute the scan. Without this flag, only the plan is shown (--plan mode).",
)
def scan(
    watchlist: str,
    data_dir: str,
    output: Optional[str],
    now: Optional[str],
    format: str,
    run: bool,
) -> None:
    """Daily scan: preview scan plan or execute locally-data-only scan.

    **Plan mode (default):** Validate the watchlist and display a normalized scan plan
    showing each symbol, market, required timeframes, cache paths, and intended output
    paths — without triggering any remote data fetch.

    **Run mode (--run):** Execute the scan using only local parquet data. In v2.2, the
    run mode is local-data-first; remote provider fetch is not triggered.

    Examples:

        python -m agent.cli scan -w watchlist/us_futures_watchlist.csv

        python -m agent.cli scan -w my_watchlist.csv --format json

        python -m agent.cli scan -w watchlist.csv --output ./my-output --run
    """
    mode = "run" if run else "plan"

    # Parse scan date
    scan_date: date
    if now:
        try:
            scan_date = date.fromisoformat(now)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid --now date format: {now!r}. Use ISO-8601 (e.g. 2026-06-09).")
            raise SystemExit(1)
    else:
        scan_date = date.today()

    # Determine output directory
    if output:
        output_dir = Path(output).expanduser().resolve()
    else:
        output_dir = Path("output") / scan_date.isoformat()

    # --- Phase 1: Validation (both plan and run mode) -----------------
    validation = validate_watchlist(watchlist)
    if not validation.valid:
        console.print(Panel(
            "[bold red]Watchlist validation failed:[/bold red]",
            expand=False,
        ))
        for issue in validation.errors:
            row_note = f" (row {issue.row_index})" if issue.row_index else ""
            console.print(f"  [red]![/red] {issue.field}{row_note}: {issue.message}")
        if validation.warnings:
            console.print(f"  [yellow] Warnings ({len(validation.warnings)}):[/yellow]")
            for w in validation.warnings:
                row_note = f" (row {w.row_index})" if w.row_index else ""
                console.print(f"    [yellow]-[/yellow] {w.field}{row_note}: {w.message}")

        # Fail-fast in run mode; summary-only in plan mode
        if run:
            console.print("\n[red]Aborted: watchlist validation failed. Fix the errors above and retry.[/red]")
            raise SystemExit(1)
        console.print("\n[yellow]Proceeding in --plan mode — errors must be fixed before --run.[/yellow]")

    # Show validation warnings even in plan mode (non-blocking)
    if validation.warnings and validation.valid:
        console.print(f"\n[yellow]Note:[/yellow] {len(validation.warnings)} warning(s):")
        for w in validation.warnings:
            row_note = f" (row {w.row_index})" if w.row_index else ""
            console.print(f"  [yellow]-[/yellow] {w.field}{row_note}: {w.message}")

    # --- Phase 2: Build scan plan --------------------------------------
    try:
        plan = build_scan_plan(
            watchlist_path=watchlist,
            data_dir=data_dir,
            output_dir=str(output_dir) if output else None,
            scan_date=scan_date,
        )
    except Exception as exc:
        console.print(f"[red]Error building scan plan:[/red] {exc}")
        raise SystemExit(1)

    # --- Phase 3: Output -----------------------------------------------
    if format == "json":
        console.print(format_plan_json(plan))
    else:
        console.print(format_plan_table(plan))

    if not run:
        panel = Panel(
            Text.from_markup(
                f"[bold]Plan mode[/bold] — no analysis executed.\n"
                f"To execute: [cyan]--run[/cyan]\n"
                f"Output dir: [dim]{output_dir}[/dim]"
            ),
            title="Daily Scan Plan",
            border_style="blue",
        )
        console.print(panel)
    else:
        console.print(Panel(
            Text.from_markup(
                f"[bold green]Run mode[/bold green] — local-data-first scan.\n"
                f"[dim]v2.2: No remote data fetch is triggered by this command.\n"
                f"Full signal scan + reporting is implemented in Phases 13–15.[/dim]"
            ),
            title="Daily Scan Run",
            border_style="green",
        ))


# Module-level entry point so this can also be invoked as:
#   python -m agent.cli.commands.scan --watchlist ...
if __name__ == "__main__":
    scan()
