"""``/scan`` CLI command — daily scan plan preview and local-data-only run."""

from __future__ import annotations

import json
from datetime import date, datetime
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

from src.data.scan_plan import ScanPlan, build_scan_plan, format_plan_table, format_plan_json
from src.data.scan_validators import validate_watchlist
from src.data.watchlist_data_health import check_watchlist_data
from src.data.scan_signal_buckets import run_signal_scan
from src.data.scan_reporting import run_reporting
from src.data.data_refresh import run_data_refresh, RefreshReport


def _run_data_gate(
    watchlist: str,
    data_dir: str,
    output_dir: Path,
    format: str,
    scan_date: date,
    console: Console,
    plan: ScanPlan,
) -> None:
    """Run the data-health gate and handle PASS/WARN/FAIL outcomes.

    Writes data_health.json to output_dir and exits on FAIL.
    On PASS/WARN: calls run_signal_scan() to execute the signal analysis.
    """
    # Always write manifest.json first so even blocked scans have a record (ART-01)
    from src.data.scan_reporting import Manifest

    manifest = Manifest(
        scan_date=scan_date.isoformat(),
        watchlist_name=plan.watchlist_name,
        artifacts={
            "data_health": "data_health.json",
            "scan_results": "scan_results.json",
            "report": "report.md",
        },
        scan_info={"watchlist": str(plan.watchlist_path)},
        total_symbols=plan.total_symbols,
    )
    manifest.to_json(output_dir / "manifest.json")

    try:
        scan_dt = datetime.combine(scan_date, datetime.min.time())
    except Exception:
        scan_dt = datetime.now()

    report = check_watchlist_data(watchlist, data_dir, scan_dt)

    # Always write data_health.json
    health_json_path = output_dir / "data_health.json"
    health_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(health_json_path, "w") as fh:
        json.dump(report.to_dict(), fh, indent=2, default=str)

    gate_dict = report.to_dict()["gate"]

    if format == "json":
        # For JSON mode, we already printed plan. Now print gate status.
        # Re-print full output with gate included.
        pass  # Gate is already in data_health.json
    else:
        from src.data.watchlist_data_health import format_report_table

        console.print()
        console.print(format_report_table(report))

    status = gate_dict["status"]
    can_backtest = gate_dict["can_backtest"]
    blocking_failures = gate_dict["blocking_failures"]
    warnings = gate_dict["warnings"]

    if not can_backtest:
        # FAIL: abort the scan
        msg = (
            f"[bold red]Data health check FAILED[/bold red] — "
            f"{blocking_failures} blocking issue(s). "
            f"Blocking scan. See [dim]{health_json_path}[/dim]"
        )
        console.print()
        console.print(Panel(
            Text.from_markup(msg),
            title="Daily Scan Run — BLOCKED",
            border_style="red",
        ))
        raise SystemExit(1)

    if warnings > 0:
        msg = (
            f"[yellow]Data health check WARNING[/yellow] — "
            f"{warnings} caveat(s). "
            f"Scan continues with caveats. See [dim]{health_json_path}[/dim]"
        )
        console.print()
        console.print(Panel(
            Text.from_markup(msg),
            title="Daily Scan Run — WARNING",
            border_style="yellow",
        ))

    # PASS: continue
    console.print(Panel(
        Text.from_markup(
            f"[bold green]Data health check PASSED[/bold green] — "
            f"{gate_dict['total_checks']} check(s).",
        ),
        title="Daily Scan Run",
        border_style="green",
    ))

    # Phase 5: Signal Scan (SIG-01, SIG-02)
    try:
        run_signal_scan(
            plan,
            output_dir,
            scan_date=scan_date,
            format=format,
            console=console,
        )
    except Exception as exc:
        console.print(f"\n[red]Signal scan error:[/red] {exc}")
        raise SystemExit(1)

    # Phase 6: Reporting — manifest.json + report.md (ART-01, RPT-01, RPT-02)
    try:
        run_reporting(
            plan,
            output_dir,
            scan_date=scan_date.isoformat(),
            format=format,
            console=console,
        )
    except Exception as exc:
        console.print(f"\n[red]Reporting error:[/red] {exc}")
        raise SystemExit(1)


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
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate watchlist and show plan without running the data-health gate or analysis.",
)
@click.option(
    "--refresh",
    is_flag=True,
    default=False,
    help="Fetch stale/missing parquet data before running the data-health gate. "
         "Only valid with --run. Uses yfinance for US futures, appropriate loaders for other markets. "
         "Refresh failures are non-blocking.",
)
def scan(
    watchlist: str,
    data_dir: str,
    output: Optional[str],
    now: Optional[str],
    format: str,
    run: bool,
    dry_run: bool,
    refresh: bool,
) -> None:
    """Daily scan: preview scan plan or execute locally-data-only scan.

    **Plan mode (default):** Validate the watchlist and display a normalized scan plan
    showing each symbol, market, required timeframes, cache paths, and intended output
    paths — without triggering any remote data fetch.

    **Run mode (--run):** Execute the scan using only local parquet data. Runs the
    data-health gate before any strategy analysis. FAIL blocks the scan; WARN continues
    with caveats. In v2.2, the run mode is local-data-first; remote fetch is not triggered.

    **Refresh mode (--run --refresh):** Before the data-health gate, fetch stale or missing
    parquet data from remote sources. Only fetches data that is older than the staleness
    threshold (see --now). Refresh failures are non-blocking; the gate runs with whatever
    data is available. yfinance is used for US futures and US equities; other markets use
    the HybridDataFetcher pipeline. Provider 429 (rate-limit) errors trigger exponential
    backoff and retry.

    Examples:

        python -m agent.cli scan -w watchlist/us_futures_watchlist.csv

        python -m agent.cli scan -w my_watchlist.csv --format json

        python -m agent.cli scan -w watchlist.csv --output ./my-output --run

        python -m agent.cli scan -w watchlist.csv --run --dry-run  # validate only

        python -m agent.cli scan -w watchlist.csv --run --refresh  # fetch stale data first
    """

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
        output_data = plan.to_dict()
        # Add gate status preview in JSON plan mode
        output_data["gate_status_preview"] = {
            "note": "Gate runs on --run. Use --watchlist-data-check to preview.",
            "blocking_timeframes": ["1d", "1h"],
            "staleness_thresholds": {"1d": "2d", "1h": "6h", "4h": "12h"},
        }
        console.print(json.dumps(output_data, indent=2, default=str))
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
        # --- Phase 4: Data Health Gate (run mode only) -----------------
        if dry_run:
            console.print(Panel(
                Text.from_markup(
                    "[bold]Dry-run mode[/bold] — gate and analysis skipped.\n"
                    "[dim]Validation passed. Use --run without --dry-run to execute.[/dim]"
                ),
                title="Daily Scan Run (Dry-Run)",
                border_style="blue",
            ))
        else:
            # RF-01: Run data refresh before the health gate if --refresh is set
            refresh_report: RefreshReport | None = None
            if refresh:
                from src.data.data_refresh import run_data_refresh
                try:
                    refresh_report = run_data_refresh(
                        watchlist_path=watchlist,
                        data_dir=data_dir,
                        scan_date_str=scan_date.isoformat(),
                        console_output=True,
                    )
                    refresh_json_path = output_dir / "data_refresh.json"
                    with open(refresh_json_path, "w") as fh:
                        json.dump(refresh_report.to_dict(), fh, indent=2, default=str)
                    console.print(
                        f"[dim]Refresh report saved to {refresh_json_path}[/dim]"
                    )
                except Exception as exc:
                    console.print(
                        f"\n[yellow]Refresh warning:[/yellow] {exc} — continuing without refresh"
                    )

            _run_data_gate(
                watchlist=watchlist,
                data_dir=data_dir,
                output_dir=output_dir,
                format=format,
                scan_date=scan_date,
                console=console,
                plan=plan,
            )


# Module-level entry point so this can also be invoked as:
#   python -m agent.cli.commands.scan --watchlist ...
if __name__ == "__main__":
    scan()
