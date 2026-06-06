"""Composite strategy reporting helpers.

Generates markdown reports for composite strategy backtests by reusing the
existing StrategyComparator and run_card.json artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from backtest.metrics import equity_gap_check, per_source_stats
from backtest.strategies.comparison import StrategyComparator


@dataclass
class CompositeReportConfig:
    """Configuration for composite strategy report generation."""

    symbol: str = ""
    period: str = ""
    data_quality_notes: str = ""
    ranked_by: str = "sharpe_ratio"


def load_single_strategy_metrics(run_dir: Path) -> Optional[dict[str, Any]]:
    """Load scalar metrics from a run directory's run_card.json."""
    run_card_path = Path(run_dir) / "run_card.json"
    if not run_card_path.exists():
        return None
    run_card = json.loads(run_card_path.read_text(encoding="utf-8"))
    metrics = run_card.get("metrics", {})
    return metrics if isinstance(metrics, dict) else None


def check_data_quality(run_card: dict[str, Any]) -> dict[str, Any]:
    """Extract lightweight data-quality evidence from a run card.

    METR-03/RPT-03 focuses on whether the run produced enough trades and
    artifacts to support comparison rather than re-computing the entire
    backtest quality pipeline.
    """
    metrics = run_card.get("metrics", {}) if isinstance(run_card.get("metrics"), dict) else {}
    artifacts = run_card.get("artifacts", []) if isinstance(run_card.get("artifacts"), list) else []
    data_sources = run_card.get("data_sources", [])
    backtest = run_card.get("backtest", {}) if isinstance(run_card.get("backtest"), dict) else {}

    artifact_paths = {
        str(item.get("path", ""))
        for item in artifacts
        if isinstance(item, dict)
    }
    trade_count = int(metrics.get("trade_count", metrics.get("total_trades", 0)) or 0)

    quality = "good"
    warnings: list[str] = []
    if not data_sources:
        quality = "degraded"
        warnings.append("no data source recorded")
    if "artifacts/equity.csv" not in artifact_paths:
        quality = "degraded"
        warnings.append("equity.csv artifact missing")
    if trade_count == 0:
        warnings.append("no completed trades")

    return {
        "quality": quality,
        "warnings": warnings,
        "trade_count": trade_count,
        "data_sources": data_sources,
        "date_range": f"{backtest.get('start_date', '')} to {backtest.get('end_date', '')}".strip(),
        "artifact_count": len(artifact_paths),
    }


def _load_run_card(run_dir: Path) -> dict[str, Any]:
    """Load run_card.json from a run directory."""
    run_card_path = Path(run_dir) / "run_card.json"
    if not run_card_path.exists():
        raise FileNotFoundError(f"run_card.json not found in {run_dir}")
    return json.loads(run_card_path.read_text(encoding="utf-8"))


def _best_name(comparator: StrategyComparator, metric: str) -> str:
    """Return best strategy name for a metric, or N/A."""
    best = comparator.get_best(metric)
    return best.name if best is not None else "N/A"


def _per_source_section(run_dirs: List[Tuple[str, Path]]) -> str:
    """Build a per-source signal breakdown from signals_per_source.json artifacts."""
    lines = ["| Run | Source | Signals | Avg Score | Bullish | Bearish | Ready |", "|-----|--------|---------|-----------|---------|---------|-------|"]
    found = False

    for name, run_dir in run_dirs:
        path = Path(run_dir) / "artifacts" / "signals_per_source.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        for source, stats in per_source_stats(raw).items():
            found = True
            lines.append(
                f"| {name} | {source} | {stats.get('signal_count', 0)} | "
                f"{stats.get('avg_score', 0):.2f} | "
                f"{stats.get('bullish_pct', 0):.1%} | "
                f"{stats.get('bearish_pct', 0):.1%} | "
                f"{stats.get('readiness_ready_pct', 0):.1%} |"
            )

    if not found:
        return "No per-source signal artifact found."
    return "\n".join(lines)


def _data_quality_section(run_dirs: List[Tuple[str, Path]], notes: str = "") -> str:
    """Build data-quality report section from run cards."""
    lines = ["| Run | Quality | Trades | Sources | Warnings |", "|-----|---------|--------|---------|----------|"]
    for name, run_dir in run_dirs:
        qc = check_data_quality(_load_run_card(run_dir))
        warnings = "; ".join(qc.get("warnings", [])) or "-"
        sources = ", ".join(str(src) for src in qc.get("data_sources", [])) or "-"
        lines.append(
            f"| {name} | {qc.get('quality', 'unknown')} | {qc.get('trade_count', 0)} | "
            f"{sources} | {warnings} |"
        )
    if notes:
        lines.extend(["", f"Notes: {notes}"])
    return "\n".join(lines)


def generate_composite_report(
    run_dirs: List[Tuple[str, Path]],
    config: CompositeReportConfig | None = None,
) -> str:
    """Generate markdown report comparing composite and single-source runs."""
    report_config = config or CompositeReportConfig()

    comparator = StrategyComparator()
    for name, run_dir in run_dirs:
        comparator.add_from_path(name, Path(run_dir))

    comparison = comparator.compare(ranked_by=report_config.ranked_by)
    symbol = report_config.symbol or "N/A"
    period = report_config.period or "N/A"

    sections = [
        "# Composite Strategy Backtest Report",
        "",
        f"**Symbol**: {symbol}",
        f"**Period**: {period}",
        "",
        "## Strategy Comparison (RPT-01)",
        "",
        comparison.to_markdown(),
        "",
        "## Best Configuration (RPT-02)",
        "",
        f"- Best by Sharpe: {_best_name(comparator, 'sharpe_ratio')}",
        f"- Best by Total Return: {_best_name(comparator, 'total_return')}",
        f"- Best by Win Rate: {_best_name(comparator, 'win_rate')}",
        "",
        "## Per-Source Performance (METR-03)",
        "",
        _per_source_section(run_dirs),
        "",
        "## Data Quality (RPT-03)",
        "",
        _data_quality_section(run_dirs, report_config.data_quality_notes),
        "",
    ]
    return "\n".join(sections)


__all__ = [
    "CompositeReportConfig",
    "generate_composite_report",
    "load_single_strategy_metrics",
    "check_data_quality",
]
