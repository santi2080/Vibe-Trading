"""Signal scan bucket classification for daily scan pipeline (SIG-01, SIG-02).

After the data-health gate passes or warns, iterates every watchlist symbol, loads its
primary (1d) parquet data, runs CompositeTrendStrategy.analyze(df), classifies the
resulting TradingSignal into exactly one of five buckets, and writes scan_results.json.

Five buckets:
    actionable  — BULL/BEAR + VALID + READY + confidence >= 0.45
    watch       — BULL/BEAR + VALID + READY + 0.25 <= confidence < 0.45
                 — NEUTRAL direction
    risk_excluded — BULL/BEAR + VALID + READY + confidence < 0.25
                   — BLOCKED/EXHAUSTED readiness
                   — FILTERED status
    skipped     — NO_SIGNAL status
                 — parquet missing or empty (handled per-symbol)
    failed      — INVALID status
                 — uncaught exception during analysis
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

# Strategy imports — use lazy import from trend package
from ..strategies.composite.base import TradingSignal
from .scan_plan import ScanPlan, SymbolPlan
from .watchlist_data_health import read_local_parquet

# Thresholds (per research Assumption A1)
BULL_BEAR_THRESHOLD = 0.45  # confidence floor for actionable
WATCH_CONFIDENCE_FLOOR = 0.25  # confidence floor for watch (below = risk_excluded)

# Valid bucket names
VALID_BUCKETS = frozenset({"actionable", "watch", "risk_excluded", "skipped", "failed"})


def _bucket_for_status(signal: TradingSignal) -> tuple[str, str]:
    """Classify INVALID/NO_SIGNAL/FILTERED status into buckets."""
    if signal.status == "INVALID":
        msg = signal.warnings[0] if signal.warnings else "unknown"
        return "failed", f"status=INVALID: {msg}"
    if signal.status == "NO_SIGNAL":
        return "skipped", "status=NO_SIGNAL: no trend signal detected"
    if signal.status == "FILTERED":
        msg = signal.warnings[0] if signal.warnings else "filtered out"
        return "risk_excluded", f"FILTERED: {msg}"
    # VALID status — fall through to direction-based logic
    return "", ""


def _bucket_for_readiness(signal: TradingSignal) -> tuple[str, str]:
    """Classify readiness BLOCKED/EXHAUSTED into risk_excluded bucket."""
    if signal.readiness in ("BLOCKED", "EXHAUSTED"):
        return "risk_excluded", f"readiness={signal.readiness}"
    return "", ""


def _bucket_for_direction(
    signal: TradingSignal,
) -> tuple[str, str]:
    """Classify BULL/BEAR/NEUTRAL direction + confidence into buckets."""
    if signal.direction == "NEUTRAL":
        return "watch", "no directional trend (NEUTRAL)"

    confidence = signal.confidence
    if confidence >= BULL_BEAR_THRESHOLD:
        return (
            "actionable",
            f"{signal.direction} trend, confidence={confidence:.2f}, score={signal.signal_score:.1f}",
        )
    if confidence >= WATCH_CONFIDENCE_FLOOR:
        return (
            "watch",
            f"{signal.direction} trend, low confidence={confidence:.2f}",
        )
    return (
        "risk_excluded",
        f"low confidence={confidence:.2f}",
    )


def classify_trading_signal(signal: TradingSignal) -> tuple[str, str]:
    """Classify a TradingSignal into a bucket name and human-readable reason.

    Every TradingSignal is classified into exactly one of five buckets:
        actionable, watch, risk_excluded, skipped, failed.

    Returns:
        A 2-tuple of (bucket_name, reason_string).
    """
    # 1. Status-based buckets (covers INVALID, NO_SIGNAL, FILTERED)
    bucket, reason = _bucket_for_status(signal)
    if bucket:
        return bucket, reason

    # 2. Readiness-based buckets (BLOCKED, EXHAUSTED override VALID)
    bucket, reason = _bucket_for_readiness(signal)
    if bucket:
        return bucket, reason

    # 3. Direction + confidence buckets (covers BULL/BEAR/NEUTRAL + VALID + READY)
    return _bucket_for_direction(signal)


# --- Result dataclass -------------------------------------------------------


@dataclass
class SymbolSignalResult:
    """Result for one symbol in the signal scan."""

    symbol: str
    name: str
    market: str
    bucket: str
    bucket_reason: str
    trading_signal: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "bucket": self.bucket,
            "bucket_reason": self.bucket_reason,
            "trading_signal": self.trading_signal,
            "error": self.error,
        }


# --- Report dataclass -------------------------------------------------------


@dataclass
class ScanSignalReport:
    """Aggregated signal scan report across all watchlist symbols."""

    scan_info: dict[str, Any]
    buckets_summary: dict[str, int]
    buckets: dict[str, list[dict[str, Any]]]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_info": self.scan_info,
            "buckets_summary": self.buckets_summary,
            "buckets": self.buckets,
            "metadata": self.metadata,
        }

    def to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)


# --- Rich table formatter ---------------------------------------------------


def format_signal_table(report: ScanSignalReport, console: Console) -> None:
    """Render a color-coded signal table grouped by bucket.

    Args:
        report: The ScanSignalReport to render.
        console: A rich Console instance for output.
    """
    title = f"Signal Scan Results — {report.scan_info.get('scan_date', 'unknown')}"
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Market", style="magenta")
    table.add_column("Bucket", style="bold")
    table.add_column("Reason", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("Conf", justify="right")

    BUCKET_COLORS: dict[str, str] = {
        "actionable": "green",
        "watch": "yellow",
        "risk_excluded": "red",
        "skipped": "dim",
        "failed": "bold red",
    }

    def _add_row(item: dict[str, Any]) -> None:
        bucket = item["bucket"]
        color = BUCKET_COLORS.get(bucket, "white")
        ts = item.get("trading_signal") or {}
        score = f"{ts.get('signal_score', 0):.1f}" if ts else "—"
        conf = f"{ts.get('confidence', 0):.2f}" if ts else "—"
        table.add_row(
            item["symbol"],
            item["name"],
            item["market"],
            f"[{color}]{bucket}[/{color}]",
            item["bucket_reason"],
            score,
            conf,
        )

    # Primary buckets ordered by priority
    for bucket_name in ("actionable", "watch", "risk_excluded", "skipped"):
        for item in report.buckets.get(bucket_name, []):
            _add_row(item)

    console.print(table)

    # Summary line
    s = report.buckets_summary
    summary_parts = []
    for bucket_name in ("actionable", "watch", "risk_excluded", "skipped", "failed"):
        count = s.get(bucket_name, 0)
        if count:
            color = BUCKET_COLORS.get(bucket_name, "white")
            summary_parts.append(f"[{color}]{count} {bucket_name}[/{color}]")

    if summary_parts:
        console.print("  ".join(summary_parts))
    else:
        console.print("[dim]No symbols processed.[/dim]")

    # Failed symbols — separate table
    failed_items = report.buckets.get("failed", [])
    if failed_items:
        console.print()
        console.print("[bold red]Failed symbols:[/bold red]")
        err_table = Table(show_header=True, header_style="bold")
        err_table.add_column("Symbol", style="cyan")
        err_table.add_column("Error", style="red")
        for item in failed_items:
            err_table.add_row(item["symbol"], item.get("error") or item.get("bucket_reason", "unknown"))
        console.print(err_table)


# --- Main orchestrator ------------------------------------------------------


def run_signal_scan(
    scan_plan: ScanPlan,
    output_dir: Path,
    *,
    scan_date: date_cls,
    format: str,
    console: Console | None = None,
) -> ScanSignalReport:
    """Run the composite signal scan over all watchlist symbols.

    For each symbol in scan_plan.symbols:
        1. Loads primary (1d) parquet via read_local_parquet.
        2. Runs CompositeTrendStrategy.analyze(df).
        3. Classifies the TradingSignal into a bucket.
        4. Appends a SymbolSignalResult.

    Per-symbol exceptions are caught and recorded to the "failed" bucket so one
    bad symbol cannot abort the scan of remaining symbols.

    Writes scan_results.json to output_dir on return.

    Args:
        scan_plan: The ScanPlan from scan_plan.build_scan_plan().
        output_dir: Directory to write scan_results.json.
        scan_date: ISO date string for the scan.
        format: "table" to render rich table, "json" for machine output.
        console: Optional rich Console instance for table rendering.

    Returns:
        A ScanSignalReport aggregating all results.
    """
    # Build composite strategy with lazy-loaded sources
    from ..strategies.trend import EnhancedSuperTrendStrategy, MTESv3TrendStrategy

    composite = _build_composite_strategy()

    results: list[SymbolSignalResult] = []

    for symbol_plan in scan_plan.symbols:
        result = _scan_single_symbol(symbol_plan, composite)
        results.append(result)

    # Build report
    buckets: dict[str, list[dict[str, Any]]] = {
        "actionable": [],
        "watch": [],
        "risk_excluded": [],
        "skipped": [],
        "failed": [],
    }
    for r in results:
        buckets[r.bucket].append(r.to_dict())

    counts: dict[str, int] = {}
    for bucket_name in VALID_BUCKETS:
        counts[bucket_name] = len(buckets.get(bucket_name, []))
    counts["total"] = len(results)

    report = ScanSignalReport(
        scan_info={
            "watchlist": str(scan_plan.watchlist_path),
            "watchlist_name": scan_plan.watchlist_name,
            "data_dir": str(scan_plan.data_dir),
            "output_dir": str(output_dir),
            "scan_date": scan_date.isoformat(),
            "strategy": "CompositeTrendStrategy",
            "total_symbols": len(results),
        },
        buckets_summary=counts,
        buckets=buckets,
        metadata={
            "strategy": "CompositeTrendStrategy",
            "sources": ["EnhancedSuperTrendStrategy", "MTESv3TrendStrategy"],
            "version": "1.0.0",
            "thresholds": {
                "bull_bear_threshold": BULL_BEAR_THRESHOLD,
                "watch_confidence_floor": WATCH_CONFIDENCE_FLOOR,
            },
        },
    )

    # Write artifact
    results_path = output_dir / "scan_results.json"
    report.to_json(results_path)

    # Render table if requested
    if format == "table" and console is not None:
        format_signal_table(report, console)

    return report


def _build_composite_strategy() -> "CompositeTrendStrategy":
    """Build CompositeTrendStrategy with default sources.

    Uses lazy imports from agent.src.strategies.trend to keep the module
    import-time lightweight.
    """
    from ..strategies.composite.trend_composite import CompositeTrendStrategy, CompositeTrendConfig
    from ..strategies.trend import EnhancedSuperTrendStrategy, MTESv3TrendStrategy

    return CompositeTrendStrategy(
        sources=[EnhancedSuperTrendStrategy(), MTESv3TrendStrategy()],
        strategy_config=CompositeTrendConfig(name="scan_composite"),
    )


def _scan_single_symbol(
    symbol_plan: SymbolPlan,
    composite: "CompositeTrendStrategy",  # type: ignore[name-defined]
) -> SymbolSignalResult:
    """Scan a single symbol: load parquet, analyze, classify.

    All exceptions are caught and reported in the "failed" bucket so that
    one bad symbol cannot abort the scan.

    Args:
        symbol_plan: The SymbolPlan for this symbol.
        composite: A configured CompositeTrendStrategy instance.

    Returns:
        A SymbolSignalResult.
    """
    # Use primary timeframe (timeframes[0], typically "1d")
    primary_cache = symbol_plan.cache_paths[0] if symbol_plan.cache_paths else None

    # 1. Load parquet
    if primary_cache is None:
        return SymbolSignalResult(
            symbol=symbol_plan.symbol,
            name=symbol_plan.name,
            market=symbol_plan.market,
            bucket="skipped",
            bucket_reason="no cache path available",
            trading_signal=None,
            error=None,
        )

    df, read_error = read_local_parquet(primary_cache)

    if read_error:
        return SymbolSignalResult(
            symbol=symbol_plan.symbol,
            name=symbol_plan.name,
            market=symbol_plan.market,
            bucket="skipped",
            bucket_reason=f"parquet read error: {read_error}",
            trading_signal=None,
            error=None,
        )

    if df is None or df.empty:
        return SymbolSignalResult(
            symbol=symbol_plan.symbol,
            name=symbol_plan.name,
            market=symbol_plan.market,
            bucket="skipped",
            bucket_reason="parquet data is empty",
            trading_signal=None,
            error=None,
        )

    # 2. Analyze
    try:
        signal = composite.analyze(df)
    except Exception as exc:  # noqa: BLE001 — per-symbol catch, let SystemExit propagate
        return SymbolSignalResult(
            symbol=symbol_plan.symbol,
            name=symbol_plan.name,
            market=symbol_plan.market,
            bucket="failed",
            bucket_reason=f"{type(exc).__name__}: {exc}",
            trading_signal=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    # 3. Classify
    bucket, bucket_reason = classify_trading_signal(signal)

    return SymbolSignalResult(
        symbol=symbol_plan.symbol,
        name=symbol_plan.name,
        market=symbol_plan.market,
        bucket=bucket,
        bucket_reason=bucket_reason,
        trading_signal=signal.to_dict(),
        error=None,
    )
