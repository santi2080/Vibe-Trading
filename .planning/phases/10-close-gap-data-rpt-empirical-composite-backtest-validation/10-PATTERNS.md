# Phase 10: Empirical Composite Backtest Evidence Closure - Pattern Map

**Mapped:** 2026-06-07
**Files analyzed:** 16 planned/modified files or artifacts
**Analogs found:** 16 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/environment.json` | artifact/config | batch, file-I/O | `agent/backtest/run_card.py` | role-match |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data_health_us_futures.json` | artifact | batch, file-I/O | `scripts/check_watchlist_data.py` + `agent/src/data/watchlist_data_health.py` | exact |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data_health_etf.json` | artifact | batch, file-I/O | `scripts/check_watchlist_data.py` + `agent/src/data/watchlist_data_health.py` | exact |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/run_manifest.json` | config/artifact | batch, transform | `agent/backtest/run_card.py` | role-match |
| `agent/backtest/configs/phase10_us_futures_1d.yaml` | config | batch | `agent/backtest/configs/composite_backtest.yaml` | exact |
| `agent/backtest/configs/phase10_us_futures_4h.yaml` | config | batch | `agent/backtest/configs/composite_backtest.yaml` | exact |
| `agent/backtest/configs/phase10_etf_1d.yaml` | config | batch | `agent/backtest/configs/composite_backtest.yaml` | exact |
| `agent/runs/composite_compare/phase10-*/comparison_report.md` | report artifact | batch, transform | `agent/backtest/composite_backtest_compare.py` | exact |
| `agent/runs/composite_compare/phase10-*/*/run_card.json` | reproducibility artifact | batch, file-I/O | `agent/backtest/run_card.py` | exact |
| `agent/runs/composite_compare/phase10-*/*/artifacts/signals_per_source.json` | metrics artifact | batch, file-I/O | `agent/backtest/reporting/composite_report.py` | exact |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/empirical_composite_report.md` | report | batch, transform | `agent/backtest/reporting/composite_report.py` | exact |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/requirements_traceability.md` | documentation artifact | transform | `.planning/REQUIREMENTS.md` + `09-UAT.md` | role-match |
| `.planning/REQUIREMENTS.md` | planning config/documentation | transform | existing `.planning/REQUIREMENTS.md` traceability table | exact |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-UAT.md` | test documentation | batch validation | `.planning/phases/09-composite-strategy-backtest/09-UAT.md` | exact |
| `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-SUMMARY.md` | summary documentation | transform | `.planning/phases/09-composite-strategy-backtest/09-UAT.md` + plan front matter | role-match |
| `scripts/generate_phase10_composite_report.py` or equivalent small closure helper | utility | batch, file-I/O, transform | `agent/backtest/reporting/composite_report.py` + `scripts/check_watchlist_data.py` | role-match |

## Pattern Assignments

### `agent/backtest/configs/phase10_us_futures_1d.yaml`, `phase10_us_futures_4h.yaml`, `phase10_etf_1d.yaml` (config, batch)

**Analog:** `agent/backtest/configs/composite_backtest.yaml`

**Config structure pattern** (lines 0-17):
```yaml
# Composite strategy backtest reference configuration
#
# This file can be copied or converted to run_dir/config.json for
# `python -m backtest.runner <run_dir>`.

# ── Backtest parameters ──────────────────────────────────────
codes:
  - "GC=F"      # Gold futures
  - "SI=F"      # Silver futures
  - "CL=F"      # Crude oil

start_date: "2024-01-01"
end_date: "2026-01-01"
interval: "1D"
source: "yfinance"
engine: "daily"
initial_cash: 1000000
commission: 0.001
```

**Strategy parameter pattern** (lines 19-44):
```yaml
# ── MTES v3 configuration ────────────────────────────────────
# The signal engine maps these user-facing keys onto the current MTESv3Config
# fields. Unknown keys are ignored for forward compatibility.
mtes_config:
  fast_ema: 12
  slow_ema: 26
  adx_period: 14
  adx_threshold: 25.0
  min_bull_ema_gap: 0.5
  min_bear_ema_gap: -0.5
  min_valid_confidence: 0.30

# ── Enhanced SuperTrend configuration ────────────────────────
supertrend_config:
  st_period: 10
  st_multiplier: 3.0
  adx_period: 14
  adx_threshold: 25.0

# ── Position management (D-02) ───────────────────────────────
atr_multiplier: 2.0
atr_period: 14

# ── Reporting ────────────────────────────────────────────────
emit_key_nodes: true
compare_single: true
```

**Copy guidance:** keep the same key names (`codes`, `start_date`, `end_date`, `interval`, `source`, `engine`, `mtes_config`, `supertrend_config`, `atr_multiplier`, `emit_key_nodes`, `compare_single`). For Phase 10 only change symbols, interval, and any evidence-specific comments. Do not invent a new config schema.

---

### `agent/runs/composite_compare/phase10-*/comparison_report.md` (report artifact, batch transform)

**Analog:** `agent/backtest/composite_backtest_compare.py`

**Imports and dependencies pattern** (lines 11-24):
```python
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from backtest.strategies.comparison import StrategyComparator
from src.tools.path_utils import safe_run_dir
```

**Variant allowlist pattern** (lines 26-30):
```python
_VARIANTS = {
    "MTES+SuperTrend": "composite",
    "MTESv3-only": "mtes_only",
    "SuperTrend-only": "supertrend_only",
}
```

**Safe config loading pattern** (lines 52-58):
```python
def _load_config(config_path: Path) -> dict[str, Any]:
    """Load YAML or JSON comparison config."""
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        return json.loads(text)
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}
```

**Run directory preparation pattern** (lines 127-141):
```python
def _prepare_run_dir(run_root: Path, label: str, config: dict[str, Any]) -> Path:
    """Create a safe run_dir with config.json and code/signal_engine.py."""
    safe_label = label.lower().replace("+", "_").replace("-", "_").replace(" ", "_")
    run_dir = safe_run_dir(str(run_root / safe_label))
    code_dir = run_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    template = _agent_root() / "backtest" / "configs" / "signal_engine.py"
    shutil.copy2(template, code_dir / "signal_engine.py")
    return run_dir
```

**Subprocess execution and error handling pattern** (lines 155-176):
```python
    timeout = _compare_timeout_seconds(timeout_seconds)
    cmd = [sys.executable, "-m", "backtest.runner", str(run_dir)]
    try:
        result = subprocess.run(
            cmd,
            cwd=_agent_root(),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        output = _format_subprocess_output(exc.stdout, exc.stderr)
        raise RuntimeError(
            f"Backtest variant {label!r} timed out after {timeout:g}s\n{output}"
        ) from exc
    if result.returncode != 0:
        output = _format_subprocess_output(result.stdout, result.stderr)
        raise RuntimeError(
            f"Backtest variant {label!r} failed with exit code {result.returncode}\n{output}"
        )
    return run_dir
```

**Comparison report write pattern** (lines 179-226):
```python
def run_comparison(
    config_path: Path,
    run_root: Path | None = None,
    timeout_seconds: float | None = None,
) -> str:
    """Run composite vs single-source comparisons and return markdown report.

    Args:
        config_path: YAML/JSON config path.
        run_root: Optional output root. Defaults to ``agent/runs/composite_compare``.
        timeout_seconds: Optional per-variant subprocess timeout.

    Returns:
        Markdown comparison report.
    """
    config_path = Path(config_path)
    config = _load_config(config_path)
    if not config:
        raise ValueError(f"Empty or invalid config: {config_path}")

    default_root = _agent_root() / "runs" / "composite_compare"
    run_root = safe_run_dir(str(run_root if run_root is not None else default_root))
    run_root.mkdir(parents=True, exist_ok=True)

    run_dirs: list[tuple[str, Path]] = []
    for label, variant in _VARIANTS.items():
        run_dirs.append((label, _run_variant(label, variant, config, run_root, timeout_seconds)))

    comparator = StrategyComparator()
    for label, run_dir in run_dirs:
        comparator.add_from_path(label, run_dir)

    comparison = comparator.compare(ranked_by="sharpe_ratio")
    report = comparison.to_markdown()

    best_sharpe = comparator.get_best("sharpe_ratio")
    best_return = comparator.get_best("total_return")
    best_win_rate = comparator.get_best("win_rate")
    report += "\n\n## Best Configuration\n"
    report += f"- Best by Sharpe: {best_sharpe.name if best_sharpe else 'N/A'}\n"
    report += f"- Best by Total Return: {best_return.name if best_return else 'N/A'}\n"
    report += f"- Best by Win Rate: {best_win_rate.name if best_win_rate else 'N/A'}\n"
    report += "\n## Run Directories\n"
    for label, run_dir in run_dirs:
        report += f"- {label}: `{run_dir}`\n"

    (run_root / "comparison_report.md").write_text(report, encoding="utf-8")
    return report
```

**CLI pattern** (lines 229-244):
```python
def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Path to YAML/JSON config")
    parser.add_argument("--run-root", type=Path, default=None, help="Optional output run root")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Per-variant subprocess timeout (default: env or 300 seconds)",
    )
    args = parser.parse_args(argv)

    report = run_comparison(args.config, args.run_root, args.timeout_seconds)
    print(report)
    return 0
```

**Copy guidance:** Phase 10 execution should call this module directly rather than building another runner loop. Use command form:

```bash
PYTHONPATH=agent python -m backtest.composite_backtest_compare \
  --config agent/backtest/configs/phase10_us_futures_1d.yaml \
  --run-root agent/runs/composite_compare/phase10-us-futures-1d \
  --timeout-seconds 300
```

---

### `.planning/.../artifacts/empirical_composite_report.md` and optional `scripts/generate_phase10_composite_report.py` (report/utility, batch transform)

**Analog:** `agent/backtest/reporting/composite_report.py`

**Imports pattern** (lines 8-15):
```python
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from backtest.metrics import equity_gap_check, per_source_stats
from backtest.strategies.comparison import StrategyComparator
```

**Config dataclass pattern** (lines 17-25):
```python
@dataclass
class CompositeReportConfig:
    """Configuration for composite strategy report generation."""

    symbol: str = ""
    period: str = ""
    data_quality_notes: str = ""
    ranked_by: str = "sharpe_ratio"
```

**Run-card data quality extraction pattern** (lines 37-74):
```python
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
```

**Per-source section pattern** (lines 91-115):
```python
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
```

**Final report section pattern** (lines 134-174):
```python
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
```

**Copy guidance:** If a Phase 10 helper is added, make it a thin wrapper around `generate_composite_report()`. It should only collect run directories, add `CompositeReportConfig(symbol=..., period=..., data_quality_notes=...)`, and write `.planning/.../artifacts/empirical_composite_report.md` with `Path.write_text(..., encoding="utf-8")`.

---

### `.planning/.../artifacts/data_health_us_futures.json` and `data_health_etf.json` (artifact, batch file-I/O)

**Analogs:** `scripts/check_watchlist_data.py`, `agent/src/data/watchlist_data_health.py`

**CLI imports/path setup pattern** (`scripts/check_watchlist_data.py` lines 5-17):
```python
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
```

**Argument pattern** (`scripts/check_watchlist_data.py` lines 20-64):
```python
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
```

**Main error/write/exit-code pattern** (`scripts/check_watchlist_data.py` lines 67-105):
```python
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
```

**Data-health JSON schema pattern** (`agent/src/data/watchlist_data_health.py` lines 107-168):
```python
@dataclass
class WatchlistDataHealthReport:
    """Aggregated watchlist data health report."""

    watchlist: str
    checked_at: datetime
    data_dir: str
    items: list[TimeframeDataHealth]
    calendar_adjusted: bool = False

    @property
    def can_backtest(self) -> bool:
        return not self.is_empty and self.blocking_failures == 0

    @property
    def gate_status(self) -> str:
        if self.is_empty or self.blocking_failures:
            return "FAIL"
        if self.warnings:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "watchlist": self.watchlist,
            "checked_at": self.checked_at.isoformat(),
            "data_dir": self.data_dir,
            "calendar_adjusted": self.calendar_adjusted,
            "gate": {
                "empty_watchlist": self.is_empty,
                "status": self.gate_status,
                "can_backtest": self.can_backtest,
                "blocking_failures": self.blocking_failures,
                "warnings": self.warnings,
                "total_checks": len(self.items),
            },
            "rules": {
                "blocking_timeframes": list(BLOCKING_TIMEFRAMES),
                "staleness_thresholds": {
                    timeframe: format_timedelta(delta)
                    for timeframe, delta in STALE_AFTER.items()
                },
```

**Watchlist traversal pattern** (`agent/src/data/watchlist_data_health.py` lines 208-238):
```python
def check_watchlist_data(
    watchlist_path: str | Path,
    data_dir: str | Path = "data",
    now: datetime | None = None,
) -> WatchlistDataHealthReport:
    """Check local parquet data for every symbol/timeframe in a watchlist."""
    checked_at = now or datetime.now()
    data_path = Path(data_dir)
    watchlist = Path(watchlist_path)
    reader = WatchlistReader(str(watchlist))
    items: list[TimeframeDataHealth] = []

    for raw_item in reader.load_raw():
        symbol = raw_item.get("symbol", "").strip()
        if not symbol or symbol.lower() in {"symbol", "code", "name"}:
            continue

        name = raw_item.get("name") or symbol
        market = raw_item.get("market") or "us_futures"
        timeframes = raw_item.get("timeframes") or "1D-1H"

        for timeframe in required_and_declared_timeframes(timeframes):
            cache_file = resolve_cache_file(data_path, market, symbol, timeframe)
            items.append(check_timeframe_data(str(watchlist), symbol, name, market, timeframe, cache_file, checked_at))

    return WatchlistDataHealthReport(
        watchlist=str(watchlist),
        checked_at=checked_at,
        data_dir=str(data_path),
        items=items,
    )
```

**Copy guidance:** Use the existing CLI exactly for Phase 10 artifacts:

```bash
python scripts/check_watchlist_data.py \
  --watchlist watchlist/us_futures_watchlist.csv \
  --data-dir data \
  --format both \
  --json-output .planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data_health_us_futures.json
```

Repeat with `watchlist/etf_watchlist.csv` and `data_health_etf.json` if ETF evidence is included.

---

### `.planning/.../artifacts/run_manifest.json` and `environment.json` (artifact/config, batch file-I/O)

**Analog:** `agent/backtest/run_card.py`

**Run-card payload pattern** (lines 23-79):
```python
def write_run_card(
    run_dir: Path,
    config: Mapping[str, Any],
    metrics: Mapping[str, Any],
    *,
    data_sources: Sequence[str] | None = None,
    strategy_path: Path | None = None,
    warnings: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Write JSON and Markdown run cards for a backtest run.

    Args:
        run_dir: Directory where run_card.json and run_card.md are written.
        config: Full backtest configuration. Only a summary and hash are stored.
        metrics: Backtest metrics. Scalar values are stored; ``validation`` is
            stored separately when present.
        data_sources: Data sources used by the run.
        strategy_path: Optional strategy source file to hash for reproducibility.
        warnings: Optional warnings to include in the card.

    Returns:
        The run card payload written to ``run_card.json``.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    config_file = run_dir / "config.json"
    reproducibility: dict[str, Any] = {
        "config_hash": _file_hash(config_file) if config_file.exists() else _json_hash(config),
    }
    if strategy_path is not None:
        strategy_file = Path(strategy_path)
        if strategy_file.exists() and strategy_file.is_file():
            reproducibility["strategy_hash"] = _file_hash(strategy_file)

    card: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "run_dir": str(run_dir),
        "backtest": _backtest_summary(config),
        "reproducibility": reproducibility,
        "data_sources": list(data_sources or []),
        "metrics": _scalar_metrics(metrics),
        "warnings": list(warnings or []),
        "artifacts": _list_artifacts(run_dir),
    }
```

**Artifact inventory pattern** (lines 121-141):
```python
def _list_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for relative in (Path("config.json"), Path("code/signal_engine.py")):
        path = run_dir / relative
        if path.exists() and path.is_file():
            candidates.append(path)

    artifacts_dir = run_dir / "artifacts"
    if artifacts_dir.exists() and artifacts_dir.is_dir():
        candidates.extend(path for path in artifacts_dir.rglob("*") if path.is_file())

    artifacts = []
    for path in sorted(candidates, key=lambda item: item.relative_to(run_dir).as_posix()):
        artifacts.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_hash(path),
            }
        )
    return artifacts
```

**Markdown run-card rendering pattern** (lines 144-199):
```python
def _render_markdown(card: Mapping[str, Any]) -> str:
    lines = [
        "# Backtest Run Card",
        "",
        f"Generated: {card['generated_at']}",
        f"Run directory: `{card['run_dir']}`",
        "",
        "## Backtest Summary",
    ]

    backtest = card.get("backtest", {})
    if backtest:
        lines.extend(f"- {key}: {value}" for key, value in backtest.items())
    else:
        lines.append("- No backtest summary fields provided.")

    lines.extend(["", "## Reproducibility"])
    reproducibility = card.get("reproducibility", {})
    lines.append(f"- config_hash: `{reproducibility.get('config_hash', '')}`")
    if "strategy_hash" in reproducibility:
        lines.append(f"- strategy_hash: `{reproducibility['strategy_hash']}`")
```

**Copy guidance:** A Phase 10 `run_manifest.json` should mirror run-card semantics: `schema_version`, `generated_at`, `requirement_ids`, each run’s config path, command, run root, status, warnings, and expected/actual artifacts. Include hashes for generated configs/reports if a helper writes them.

---

### `agent/runs/composite_compare/phase10-*/*/run_card.json` (reproducibility artifact, batch file-I/O)

**Analog:** `agent/backtest/run_card.py`

**Required fields to rely on:**

- `backtest.codes`, `backtest.start_date`, `backtest.end_date`, `backtest.interval`, `backtest.source` from lines 12-20 and 105-106.
- `reproducibility.config_hash` and `strategy_hash` from lines 49-57.
- `data_sources`, `metrics`, `warnings`, `artifacts` from lines 58-68.
- `artifacts[*].path`, `size_bytes`, `sha256` from lines 132-140.

**Copy guidance:** Do not manually edit run cards. Phase 10 closure should inspect them and cite exact paths in `run_manifest.json`, `empirical_composite_report.md`, `requirements_traceability.md`, and `10-UAT.md`.

---

### `agent/runs/composite_compare/phase10-*/*/artifacts/signals_per_source.json` (metrics artifact, file-I/O)

**Analog:** `agent/backtest/reporting/composite_report.py`

**Consumption pattern** (lines 96-111):
```python
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
```

**Copy guidance:** Phase 10 acceptance checks should verify the artifact exists for composite runs and that final report contains `## Per-Source Performance (METR-03)`.

---

### `.planning/REQUIREMENTS.md` and `.planning/.../artifacts/requirements_traceability.md` (documentation/config, transform)

**Analog:** `.planning/REQUIREMENTS.md`

**Requirement list pattern** (lines 19-29):
```markdown
### Data Coverage

- [ ] **DATA-01**: 使用近 2 年数据 (2024-2026) 进行回测
- [ ] **DATA-02**: 覆盖 watchlist 中的主要品种（期货/ETF）
- [ ] **DATA-03**: 支持 1D 和 4H 时间周期

### Analysis & Reporting

- [ ] **RPT-01**: 生成组合策略 vs 单一策略对比报告
- [ ] **RPT-02**: 识别最佳策略组合配置
- [ ] **RPT-03**: 记录数据质量和完整性检查
```

**Traceability table pattern** (lines 31-46):
```markdown
## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BKST-01 | Phase 1 | Pending |
| BKST-02 | Phase 1 | Pending |
| BKST-03 | Phase 1 | Pending |
| METR-01 | Phase 2 | Pending |
| METR-02 | Phase 2 | Pending |
| METR-03 | Phase 2 | Pending |
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| RPT-01 | Phase 3 | Pending |
| RPT-02 | Phase 3 | Pending |
| RPT-03 | Phase 3 | Pending |
```

**Copy guidance:** For Phase 10, update traceability only after artifacts exist. Use artifact-linked status values such as `Closed in Phase 10 — see <path>` rather than unqualified `Complete`. `requirements_traceability.md` can be a more verbose companion table with columns: Requirement, Evidence Artifact, Validation Command, Status, Caveat.

---

### `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-UAT.md` (test documentation, batch validation)

**Analog:** `.planning/phases/09-composite-strategy-backtest/09-UAT.md`

**Front matter pattern** (lines 0-7):
```markdown
---
status: complete
phase: 09-composite-strategy-backtest
source:
  - 09-SUMMARY.md
started: 2026-06-06T06:09:16Z
updated: 2026-06-06T06:18:43Z
---
```

**Test case pattern** (lines 15-33):
```markdown
### 1. Composite Backtest Smoke Verification
expected: Running the Phase 09 smoke validation from the project virtual environment completes successfully and prints `PHASE09_SMOKE: PASS`, confirming YAML parsing, signal recording, trailing-stop behavior, composite engine behavior, metrics helpers, and report generation all work together.
result: pass

### 2. Composite Strategy Regression Suite
expected: The related regression suite for composite signal contracts, composite trend strategy, market detection, and metrics completes successfully with no failures.
result: pass

### 3. Runner Signal Artifact Output
expected: A runner-compatible composite backtest can write signal artifacts through the engine hook, producing `artifacts/signals_key_nodes.csv` and `artifacts/signals_per_source.json` when the signal engine exposes composite signal output.
result: pass

### 4. Composite vs Single Strategy Comparison
expected: The comparison orchestrator supports composite, MTES-only, and SuperTrend-only variants so performance can be compared across strategy configurations.
result: pass

### 5. Composite Report Generation
expected: Composite report generation produces a readable markdown report with composite metrics, per-source statistics, data-quality checks, and composite-vs-single comparison sections.
result: pass
```

**Summary pattern** (lines 35-46):
```markdown
## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
```

**Copy guidance:** Phase 10 UAT should be artifact-oriented. Suggested tests:

1. Data health artifacts exist and include `gate.status`.
2. `run_manifest.json` lists each Phase 10 command, config, run root, and status.
3. Each successful run root has `comparison_report.md` and per-variant `run_card.json`.
4. Final `empirical_composite_report.md` has `Strategy Comparison (RPT-01)`, `Best Configuration (RPT-02)`, `Per-Source Performance (METR-03)`, `Data Quality (RPT-03)` headings.
5. `.planning/REQUIREMENTS.md` maps DATA/METR/RPT requirements to Phase 10 evidence.

---

### `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-SUMMARY.md` (summary documentation, transform)

**Analog:** `09-UAT.md` and `09-04-PLAN.md`

**Plan front matter pattern** (`09-04-PLAN.md` lines 3-18):
```yaml
phase: "09"
plan: "04"
type: "execute"
wave: 3
depends_on: ["09-03"]
files_modified:
  - "agent/backtest/metrics.py"
  - "agent/backtest/reporting/composite_report.py"
autonomous: true
requirements:
  - "METR-01"
  - "METR-02"
  - "METR-03"
  - "RPT-01"
  - "RPT-02"
  - "RPT-03"
```

**Must-have artifact pattern** (`09-04-PLAN.md` lines 19-38):
```yaml
must_haves:
  truths:
    - "calc_metrics() computes win rate, Sharpe ratio, max drawdown for composite strategy"
    - "StrategyComparator compares composite vs single strategy runs"
    - "generate_composite_report() produces markdown comparison report"
    - "Per-source breakdown (MTESv3 alone, SuperTrend alone) is available in output"
  artifacts:
    - path: "agent/backtest/reporting/composite_report.py"
      provides: "generate_composite_report(), CompositeReportConfig"
      exports: ["generate_composite_report", "CompositeReportConfig"]
```

**Copy guidance:** Phase 10 summary should state closure evidence, not implementation details. Include a table: Requirement, Evidence Path, Result, Caveat. Link to generated artifacts and UAT results.

---

### `scripts/generate_phase10_composite_report.py` or equivalent helper (utility, batch file-I/O transform)

**Analogs:** `scripts/check_watchlist_data.py`, `agent/backtest/reporting/composite_report.py`

**CLI skeleton to copy from** (`scripts/check_watchlist_data.py` lines 20-64 and 67-105): use `argparse`, typed `Path`/string args, explicit output path parent creation, `return 0/1/2` style for shell automation.

**Report API to copy from** (`agent/backtest/reporting/composite_report.py` lines 134-174): use `generate_composite_report(run_dirs, CompositeReportConfig(...))` and write text with UTF-8.

**Expected helper shape:**
```python
from pathlib import Path
from backtest.reporting.composite_report import CompositeReportConfig, generate_composite_report

# Parse --run-root, --output, --symbol, --period, --data-quality-notes.
# Build run_dirs = [("MTES+SuperTrend", run_root / "mtes_supertrend"), ...]
# Write output_path.write_text(report, encoding="utf-8")
```

**Do not copy:** subprocess orchestration; Phase 10 comparison runs already use `backtest.composite_backtest_compare`.

## Shared Patterns

### Safe run-root and subprocess guard

**Source:** `agent/backtest/composite_backtest_compare.py` lines 127-141, 155-176

**Apply to:** empirical comparison run commands, run manifest entries, and any helper that references `agent/runs/composite_compare/phase10-*`.

```python
run_dir = safe_run_dir(str(run_root / safe_label))
...
cmd = [sys.executable, "-m", "backtest.runner", str(run_dir)]
...
except subprocess.TimeoutExpired as exc:
    output = _format_subprocess_output(exc.stdout, exc.stderr)
    raise RuntimeError(
        f"Backtest variant {label!r} timed out after {timeout:g}s\n{output}"
    ) from exc
```

### Secret redaction and bounded diagnostics

**Source:** `agent/backtest/composite_backtest_compare.py` lines 36-39, 85-113

**Apply to:** UAT logs, run manifest failure messages, any helper that captures subprocess output.

```python
_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*([^\s]+)"),
    re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]+)"),
]
...
def _format_subprocess_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    """Return redacted, truncated stdout/stderr for exceptions."""
    safe_stdout = _truncate_output(_redact_output(stdout))
    safe_stderr = _truncate_output(_redact_output(stderr))
    return f"STDOUT:\n{safe_stdout}\nSTDERR:\n{safe_stderr}"
```

### Requirements-first report headings

**Source:** `agent/backtest/reporting/composite_report.py` lines 149-172

**Apply to:** final empirical report and UAT heading checks.

```python
sections = [
    "# Composite Strategy Backtest Report",
    ...
    "## Strategy Comparison (RPT-01)",
    ...
    "## Best Configuration (RPT-02)",
    ...
    "## Per-Source Performance (METR-03)",
    ...
    "## Data Quality (RPT-03)",
]
```

### Machine-readable data-health gate

**Source:** `agent/src/data/watchlist_data_health.py` lines 141-168 and `scripts/check_watchlist_data.py` lines 99-105

**Apply to:** `data_health_us_futures.json`, `data_health_etf.json`, `run_manifest.json`, UAT checks.

```python
"gate": {
    "empty_watchlist": self.is_empty,
    "status": self.gate_status,
    "can_backtest": self.can_backtest,
    "blocking_failures": self.blocking_failures,
    "warnings": self.warnings,
    "total_checks": len(self.items),
},
```

```python
if args.json_output:
    output_path = Path(args.json_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("JSON report written to %s", output_path)

return 0 if report.can_backtest else 1
```

### Reproducibility and artifact hashing

**Source:** `agent/backtest/run_card.py` lines 49-68, 121-141

**Apply to:** `run_manifest.json`, `requirements_traceability.md`, final summary.

```python
reproducibility: dict[str, Any] = {
    "config_hash": _file_hash(config_file) if config_file.exists() else _json_hash(config),
}
...
"artifacts": _list_artifacts(run_dir),
```

### Test patterns for closure validation

**Source:** `agent/tests/test_composite_backtest_compare.py` lines 32-48, 72-97; `agent/tests/test_watchlist_data_health.py` lines 195-226

**Apply to:** targeted regression commands and UAT evidence.

```python
def test_prepare_run_dir_accepts_configured_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))
    run_root = tmp_path / "compare"

    run_dir = compare._prepare_run_dir(run_root, "MTES+SuperTrend", {"codes": ["GC=F"]})

    assert run_dir == (run_root / "mtes_supertrend").resolve()
    assert (run_dir / "config.json").exists()
    assert (run_dir / "code" / "signal_engine.py").exists()
```

```python
def test_cli_returns_zero_and_prints_json_for_passing_report(tmp_path: Path) -> None:
    ...
    result = run_cli("--watchlist", str(watchlist), "--data-dir", str(data_dir), "--format", "json", "--now", now)

    assert result.returncode == 0
    assert json.loads(result.stdout)["gate"]["status"] == "PASS"
```

## Validation Commands to Reuse

### Static compile surface

```bash
python -m py_compile \
  agent/backtest/runner.py \
  agent/backtest/composite_backtest_compare.py \
  agent/backtest/reporting/composite_report.py \
  agent/backtest/configs/signal_engine.py
```

### Targeted regression suite

```bash
python -m pytest -q \
  agent/tests/test_composite_backtest_compare.py \
  agent/tests/test_metrics.py \
  agent/tests/test_watchlist_data_health.py \
  agent/tests/test_backtest_runner_security.py
```

### Empirical comparison command

```bash
PYTHONPATH=agent python -m backtest.composite_backtest_compare \
  --config agent/backtest/configs/phase10_us_futures_1d.yaml \
  --run-root agent/runs/composite_compare/phase10-us-futures-1d \
  --timeout-seconds 300
```

### Data-health command

```bash
python scripts/check_watchlist_data.py \
  --watchlist watchlist/us_futures_watchlist.csv \
  --data-dir data \
  --format both \
  --json-output .planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data_health_us_futures.json
```

## No Analog Found

No Phase 10 file lacks an analog. The only not-yet-existing source-style helper (`scripts/generate_phase10_composite_report.py` or equivalent) should be a thin wrapper around existing `generate_composite_report()` and script CLI patterns; it does not require new architecture.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All planned files map to existing config, CLI, report, run-card, data-health, UAT, or requirements patterns. |

## Metadata

**Analog search scope:** `.planning/`, `agent/backtest/`, `agent/src/data/`, `agent/tests/`, `scripts/`, `watchlist/`.
**Strong analogs read:** 11 files.
**Primary analogs:** `agent/backtest/composite_backtest_compare.py`, `agent/backtest/reporting/composite_report.py`, `scripts/check_watchlist_data.py`, `agent/src/data/watchlist_data_health.py`, `agent/backtest/run_card.py`, `agent/backtest/configs/composite_backtest.yaml`, `.planning/REQUIREMENTS.md`, `09-UAT.md`.
**Pattern extraction date:** 2026-06-07

## Planner Notes

- Phase 10 is closure/evidence production, not new strategy infrastructure.
- Prefer existing modules over new code: comparison CLI, runner, run cards, data-health CLI, and report generator already exist.
- If full 2024-2026 `4H` data cannot be obtained, record it as RPT-03 evidence in data-health JSON, run manifest warnings, and report notes; do not silently substitute `1D`.
- Do not expand into Daily Scan Report, scoring/ranking frameworks, or new data-source integrations.
