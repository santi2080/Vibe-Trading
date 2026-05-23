"""Strategy comparison tool for backtesting results.

Provides comparison of multiple strategies across key metrics:
- Returns (total, annual, monthly)
- Risk metrics (Sharpe, Sortino, Calmar, max drawdown)
- Trade statistics (win rate, profit factor, etc.)
- Visual comparison tables and heatmaps
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class StrategyMetrics:
    """Metrics for a single strategy."""

    name: str
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # in bars
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    avg_holding_bars: float = 0.0
    trade_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "returns": {
                "total": f"{self.total_return:.2%}",
                "annual": f"{self.annual_return:.2%}",
            },
            "risk": {
                "sharpe": f"{self.sharpe_ratio:.2f}",
                "sortino": f"{self.sortino_ratio:.2f}",
                "calmar": f"{self.calmar_ratio:.2f}",
                "max_drawdown": f"{self.max_drawdown:.2%}",
                "max_dd_duration": f"{self.max_drawdown_duration} bars",
            },
            "trades": {
                "count": self.total_trades,
                "win_rate": f"{self.win_rate:.2%}",
                "profit_factor": f"{self.profit_factor:.2f}",
                "avg_return": f"{self.avg_trade_return:.2%}",
                "avg_holding": f"{self.avg_holding_bars:.1f} bars",
            },
        }


@dataclass
class ComparisonResult:
    """Comparison of multiple strategies."""

    strategies: List[StrategyMetrics]
    period_days: int = 0
    ranked_by: str = "sharpe"  # default ranking metric

    def get_ranking(self, metric: str = "sharpe") -> List[Tuple[str, float]]:
        """Get strategies ranked by a specific metric.

        Args:
            metric: Metric to rank by (sharpe, total_return, win_rate, etc.)

        Returns:
            List of (strategy_name, value) tuples, sorted descending
        """
        rankings = []
        for s in self.strategies:
            value = getattr(s, metric, 0.0)
            rankings.append((s.name, value))
        return sorted(rankings, key=lambda x: x[1], reverse=True)

    def get_winners(self, metric: str = "sharpe") -> List[str]:
        """Get strategy names that win on a specific metric."""
        rankings = self.get_ranking(metric)
        if not rankings:
            return []
        max_value = rankings[0][1]
        return [name for name, value in rankings if abs(value - max_value) < 1e-10]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame for easy comparison."""
        rows = []
        for s in self.strategies:
            rows.append({
                "Strategy": s.name,
                "Total Return": s.total_return,
                "Annual Return": s.annual_return,
                "Sharpe": s.sharpe_ratio,
                "Sortino": s.sortino_ratio,
                "Calmar": s.calmar_ratio,
                "Max DD": s.max_drawdown,
                "Win Rate": s.win_rate,
                "Profit Factor": s.profit_factor,
                "Trades": s.total_trades,
                "Avg Trade": s.avg_trade_return,
            })
        return pd.DataFrame(rows)

    def to_markdown(self) -> str:
        """Generate markdown comparison table."""
        lines = ["# Strategy Comparison\n"]

        # Summary table
        lines.append("## Summary\n")
        lines.append("| Strategy | Total Ret | Sharpe | Sortino | Max DD | Win Rate | Trades |")
        lines.append("|----------|-----------|--------|---------|--------|---------|-------|")
        sorted_strategies = sorted(
            self.strategies,
            key=lambda x: getattr(x, self.ranked_by, 0.0),
            reverse=True
        )
        for s in sorted_strategies:
            lines.append(
                f"| {s.name} | {s.total_return:>8.2%} | "
                f"{s.sharpe_ratio:>6.2f} | {s.sortino_ratio:>6.2f} | "
                f"{s.max_drawdown:>7.2%} | {s.win_rate:>8.1%} | {s.total_trades:>5d} |"
            )

        # Winners
        lines.append("\n## Winners\n")
        for metric in ["sharpe_ratio", "total_return", "win_rate", "max_drawdown"]:
            winners = self.get_winners(metric)
            metric_name = metric.replace("_", " ").title()
            lines.append(f"- **{metric_name}**: {', '.join(winners)}")

        # Risk-adjusted ranking
        lines.append("\n## Risk-Adjusted Ranking\n")
        rankings = self.get_ranking("sharpe")
        for i, (name, sharpe) in enumerate(rankings, 1):
            lines.append(f"{i}. {name} (Sharpe: {sharpe:.2f})")

        return "\n".join(lines)


class StrategyComparator:
    """Compare multiple backtest strategies."""

    def __init__(self):
        """Initialize comparator."""
        self.strategies: List[StrategyMetrics] = []

    def add_strategy(self, metrics: StrategyMetrics) -> None:
        """Add a strategy to comparison."""
        self.strategies.append(metrics)

    def add_from_dict(
        self,
        name: str,
        metrics: Dict[str, Any],
    ) -> None:
        """Add strategy from metrics dictionary.

        Args:
            name: Strategy name
            metrics: Metrics dict with keys like:
                - total_return, annual_return
                - sharpe, sortino, calmar
                - max_drawdown, max_drawdown_duration
                - win_rate, profit_factor
                - total_trades, avg_trade_return, avg_holding_bars
        """
        strategy = StrategyMetrics(
            name=name,
            total_return=metrics.get("total_return", 0.0),
            annual_return=metrics.get("annual_return", 0.0),
            sharpe_ratio=metrics.get("sharpe", metrics.get("sharpe_ratio", 0.0)),
            sortino_ratio=metrics.get("sortino", metrics.get("sortino_ratio", 0.0)),
            calmar_ratio=metrics.get("calmar", metrics.get("calmar_ratio", 0.0)),
            max_drawdown=metrics.get("max_drawdown", 0.0),
            max_drawdown_duration=metrics.get("max_drawdown_duration", 0),
            win_rate=metrics.get("win_rate", 0.0),
            profit_factor=metrics.get("profit_factor", 0.0),
            total_trades=metrics.get("total_trades", 0),
            avg_trade_return=metrics.get("avg_trade_return", 0.0),
            avg_holding_bars=metrics.get("avg_holding_bars", 0.0),
        )
        self.strategies.append(strategy)

    def add_from_run_card(
        self,
        name: str,
        run_card: Dict[str, Any],
    ) -> None:
        """Add strategy from run card.

        Args:
            name: Strategy name
            run_card: Run card dict from run_card.json
        """
        metrics = run_card.get("metrics", {})
        self.add_from_dict(name, metrics)

    def add_from_path(
        self,
        name: str,
        run_dir: Path,
    ) -> None:
        """Add strategy from run directory.

        Args:
            name: Strategy name
            run_dir: Path to backtest run directory
        """
        import json

        run_card_path = Path(run_dir) / "run_card.json"
        if run_card_path.exists():
            with open(run_card_path) as f:
                run_card = json.load(f)
            self.add_from_run_card(name, run_card)
        else:
            raise FileNotFoundError(f"run_card.json not found in {run_dir}")

    def compare(self, ranked_by: str = "sharpe") -> ComparisonResult:
        """Generate comparison result.

        Args:
            ranked_by: Metric to rank by (sharpe, total_return, etc.)

        Returns:
            ComparisonResult with all strategies
        """
        result = ComparisonResult(
            strategies=self.strategies,
            ranked_by=ranked_by,
        )
        return result

    def get_best(self, metric: str = "sharpe") -> Optional[StrategyMetrics]:
        """Get best strategy by metric.

        Args:
            metric: Metric to evaluate (sharpe, total_return, etc.)

        Returns:
            Best strategy or None if empty
        """
        if not self.strategies:
            return None
        return max(self.strategies, key=lambda x: getattr(x, metric, 0.0))

    def get_worst(self, metric: str = "sharpe") -> Optional[StrategyMetrics]:
        """Get worst strategy by metric.

        Args:
            metric: Metric to evaluate

        Returns:
            Worst strategy or None if empty
        """
        if not self.strategies:
            return None
        return min(self.strategies, key=lambda x: getattr(x, metric, 0.0))

    def filter_by_return(
        self,
        min_return: float = 0.0,
    ) -> List[StrategyMetrics]:
        """Filter strategies by minimum return.

        Args:
            min_return: Minimum total return threshold

        Returns:
            Strategies meeting the threshold
        """
        return [s for s in self.strategies if s.total_return >= min_return]

    def filter_by_sharpe(
        self,
        min_sharpe: float = 0.0,
    ) -> List[StrategyMetrics]:
        """Filter strategies by minimum Sharpe ratio.

        Args:
            min_sharpe: Minimum Sharpe ratio threshold

        Returns:
            Strategies meeting the threshold
        """
        return [s for s in self.strategies if s.sharpe_ratio >= min_sharpe]

    def filter_by_drawdown(
        self,
        max_drawdown: float = 1.0,
    ) -> List[StrategyMetrics]:
        """Filter strategies by maximum drawdown.

        Args:
            max_drawdown: Maximum drawdown threshold (e.g., 0.2 = 20%)

        Returns:
            Strategies meeting the threshold
        """
        return [s for s in self.strategies if abs(s.max_drawdown) <= max_drawdown]

    def summary(self) -> str:
        """Generate text summary."""
        if not self.strategies:
            return "No strategies to compare."

        lines = ["Strategy Comparison Summary\n" + "=" * 40]

        # Best by each metric
        for metric, label in [
            ("sharpe_ratio", "Sharpe Ratio"),
            ("total_return", "Total Return"),
            ("win_rate", "Win Rate"),
            ("max_drawdown", "Lowest Drawdown"),
        ]:
            best = self.get_best(metric if metric != "max_drawdown" else "max_drawdown")
            if best:
                value = getattr(best, metric if metric != "max_drawdown" else "max_drawdown")
                if "return" in metric or "drawdown" in metric:
                    lines.append(f"Best {label}: {best.name} ({value:.2%})")
                else:
                    lines.append(f"Best {label}: {best.name} ({value:.2f})")

        lines.append(f"\nTotal strategies: {len(self.strategies)}")

        return "\n".join(lines)


# Convenience function
def compare_strategies(
    strategies: List[Tuple[str, Dict[str, Any]]],
    ranked_by: str = "sharpe",
) -> ComparisonResult:
    """Compare multiple strategies.

    Args:
        strategies: List of (name, metrics_dict) tuples
        ranked_by: Metric to rank by

    Returns:
        ComparisonResult

    Example:
        >>> strategies = [
        ...     ("EMA Cross", {"sharpe": 1.5, "total_return": 0.25, ...}),
        ...     ("RSI Mean Rev", {"sharpe": 1.2, "total_return": 0.18, ...}),
        ... ]
        >>> result = compare_strategies(strategies)
        >>> print(result.to_markdown())
    """
    comparator = StrategyComparator()
    for name, metrics in strategies:
        comparator.add_from_dict(name, metrics)
    return comparator.compare(ranked_by=ranked_by)
