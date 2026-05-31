"""Performance metrics: calculate trading performance metrics from trade records and equity curve.

This module provides:
- PerformanceMetrics: comprehensive performance metrics dataclass
- calculate_metrics: calculate all metrics from trade records
- calculate_sharpe: Sharpe ratio calculation
- calculate_sortino: Sortino ratio calculation
- calculate_max_drawdown: maximum drawdown calculation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from agent.src.analysis.portfolio_tracker import PortfolioTracker
from agent.src.analysis.signal_executor import ClosedTrade, ExitReason


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics.

    Args:
        total_return: Total return as decimal (e.g., 0.15 = 15%).
        total_return_pct: Total return as percentage.
        sharpe_ratio: Sharpe ratio.
        sortino_ratio: Sortino ratio.
        max_drawdown: Maximum drawdown as decimal.
        max_drawdown_pct: Maximum drawdown as percentage.
        max_drawdown_duration: Max drawdown duration in bars.
        win_rate: Win rate as decimal.
        profit_factor: Profit factor (gross profit / gross loss).
        avg_win: Average winning trade amount.
        avg_loss: Average losing trade amount.
        total_trades: Total number of trades.
        winning_trades: Number of winning trades.
        losing_trades: Number of losing trades.
        avg_trade_pnl: Average P&L per trade.
        avg_holding_bars: Average holding period in bars.
        equity_final: Final equity value.
        equity_peak: Peak equity value.
        annualized_return: Annualized return.
        calmar_ratio: Calmar ratio (return / max drawdown).
        volatility: Returns volatility.
        downside_deviation: Downside deviation (for Sortino).
    """

    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_pnl: float = 0.0
    avg_holding_bars: float = 0.0
    equity_final: float = 0.0
    equity_peak: float = 0.0
    annualized_return: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    downside_deviation: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "avg_holding_bars": self.avg_holding_bars,
            "equity_final": self.equity_final,
            "equity_peak": self.equity_peak,
            "annualized_return": self.annualized_return,
            "calmar_ratio": self.calmar_ratio,
        }


def calculate_metrics(
    tracker: PortfolioTracker,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    """Calculate comprehensive performance metrics from portfolio tracker.

    Args:
        tracker: Portfolio tracker with equity history and trades.
        risk_free_rate: Risk-free rate for Sharpe/Sortino (default 0).
        periods_per_year: Number of periods per year (default 252 for daily).

    Returns:
        PerformanceMetrics with all calculated values.
    """
    trades = tracker.closed_trades
    equity_history = tracker.equity_history

    if not trades:
        return PerformanceMetrics(
            equity_final=tracker.total_equity,
            equity_peak=tracker.max_drawdown,
        )

    initial_capital = tracker.initial_capital
    final_equity = tracker.total_equity

    total_return = (final_equity - initial_capital) / initial_capital
    total_return_pct = total_return * 100

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]

    winning_trades = len(winning)
    losing_trades = len(losing)
    total_trades = len(trades)

    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    gross_profit = sum(t.pnl for t in winning) if winning else 0.0
    gross_loss = abs(sum(t.pnl for t in losing)) if losing else 0.0

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
    avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0

    total_pnl = sum(t.pnl for t in trades)
    avg_trade_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

    avg_holding_bars = (
        sum(t.holding_bars for t in trades) / total_trades if total_trades > 0 else 0.0
    )

    max_dd, max_dd_pct, max_dd_duration = calculate_max_drawdown(tracker)

    equity_series = tracker.get_equity_series()
    returns = equity_series.pct_change().dropna()

    if len(returns) > 1:
        volatility = returns.std() * np.sqrt(periods_per_year)
        downside_returns = returns[returns < 0]
        downside_deviation = (
            downside_returns.std() * np.sqrt(periods_per_year)
            if len(downside_returns) > 0
            else 0.0
        )
    else:
        volatility = 0.0
        downside_deviation = 0.0

    excess_returns = returns - risk_free_rate / periods_per_year

    if volatility > 0:
        sharpe_ratio = (excess_returns.mean() * periods_per_year) / volatility
    else:
        sharpe_ratio = 0.0

    if downside_deviation > 0:
        sortino_ratio = (excess_returns.mean() * periods_per_year) / downside_deviation
    else:
        sortino_ratio = 0.0

    years = len(equity_history) / periods_per_year if periods_per_year > 0 else 1.0
    annualized_return = ((final_equity / initial_capital) ** (1 / years) - 1) if years > 0 else 0.0

    calmar_ratio = annualized_return / max_dd if max_dd > 0 else 0.0

    return PerformanceMetrics(
        total_return=total_return,
        total_return_pct=total_return_pct,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration=max_dd_duration,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_trade_pnl=avg_trade_pnl,
        avg_holding_bars=avg_holding_bars,
        equity_final=final_equity,
        equity_peak=tracker.max_drawdown,
        annualized_return=annualized_return,
        calmar_ratio=calmar_ratio,
        volatility=volatility,
        downside_deviation=downside_deviation,
    )


def calculate_sharpe(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate Sharpe ratio from returns series.

    Args:
        returns: Series of period returns.
        risk_free_rate: Annual risk-free rate (default 0).
        periods_per_year: Number of periods per year.

    Returns:
        Sharpe ratio.
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / periods_per_year
    volatility = returns.std() * np.sqrt(periods_per_year)

    if volatility == 0:
        return 0.0

    return (excess_returns.mean() * periods_per_year) / volatility


def calculate_sortino(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate Sortino ratio from returns series.

    Args:
        returns: Series of period returns.
        risk_free_rate: Annual risk-free rate (default 0).
        periods_per_year: Number of periods per year.

    Returns:
        Sortino ratio.
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = returns[returns < 0]

    if len(downside_returns) == 0:
        return 0.0

    downside_deviation = downside_returns.std() * np.sqrt(periods_per_year)

    if downside_deviation == 0:
        return 0.0

    return (excess_returns.mean() * periods_per_year) / downside_deviation


def calculate_max_drawdown(tracker: PortfolioTracker) -> tuple[float, float, int]:
    """Calculate maximum drawdown from portfolio tracker.

    Args:
        tracker: Portfolio tracker with equity history.

    Returns:
        Tuple of (max_drawdown, max_drawdown_pct, max_duration).
    """
    equity_history = tracker.equity_history

    if not equity_history:
        return 0.0, 0.0, 0

    equity_values = [s.equity for s in equity_history]

    max_equity = 0.0
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    max_duration = 0

    current_duration = 0
    peak = 0.0

    for equity in equity_values:
        if equity > peak:
            peak = equity
            current_duration = 0

        drawdown = peak - equity
        drawdown_pct = drawdown / peak if peak > 0 else 0.0

        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_pct = drawdown_pct
            max_duration = current_duration

        current_duration += 1

    return max_drawdown, max_drawdown_pct, max_duration


def calculate_trade_statistics(trades: list[ClosedTrade]) -> dict:
    """Calculate statistics from trade records.

    Args:
        trades: List of closed trades.

    Returns:
        Dict with trade statistics.
    """
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "avg_holding_bars": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "avg_entry_to_exit": 0.0,
        }

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]

    total_pnl = sum(t.pnl for t in trades)
    gross_profit = sum(t.pnl for t in winning) if winning else 0.0
    gross_loss = abs(sum(t.pnl for t in losing)) if losing else 0.0

    return {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(trades) if trades else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else 0.0,
        "avg_pnl": total_pnl / len(trades) if trades else 0.0,
        "avg_win": gross_profit / len(winning) if winning else 0.0,
        "avg_loss": gross_loss / len(losing) if losing else 0.0,
        "avg_holding_bars": sum(t.holding_bars for t in trades) / len(trades) if trades else 0.0,
        "largest_win": max((t.pnl for t in winning), default=0.0),
        "largest_loss": min((t.pnl for t in losing), default=0.0),
        "avg_entry_to_exit": sum(t.holding_bars for t in trades) / len(trades) if trades else 0.0,
    }


def format_metrics_report(metrics: PerformanceMetrics) -> str:
    """Format performance metrics as a readable report.

    Args:
        metrics: Performance metrics to format.

    Returns:
        Formatted string report.
    """
    lines = [
        "=" * 50,
        "PERFORMANCE METRICS REPORT",
        "=" * 50,
        "",
        "Returns",
        "-" * 30,
        f"  Total Return:     {metrics.total_return_pct:>10.2f}%",
        f"  Annualized:       {metrics.annualized_return * 100:>10.2f}%",
        f"  Final Equity:    ${metrics.equity_final:>10,.2f}",
        f"  Peak Equity:      ${metrics.equity_peak:>10,.2f}",
        "",
        "Risk Metrics",
        "-" * 30,
        f"  Sharpe Ratio:    {metrics.sharpe_ratio:>10.2f}",
        f"  Sortino Ratio:   {metrics.sortino_ratio:>10.2f}",
        f"  Max Drawdown:    {metrics.max_drawdown_pct:>10.2f}%",
        f"  Calmar Ratio:     {metrics.calmar_ratio:>10.2f}",
        "",
        "Trade Statistics",
        "-" * 30,
        f"  Total Trades:    {metrics.total_trades:>10}",
        f"  Winning:         {metrics.winning_trades:>10}",
        f"  Losing:          {metrics.losing_trades:>10}",
        f"  Win Rate:        {metrics.win_rate * 100:>10.2f}%",
        f"  Profit Factor:   {metrics.profit_factor:>10.2f}",
        "",
        "P&L Statistics",
        "-" * 30,
        f"  Avg Trade P&L:   ${metrics.avg_trade_pnl:>10.2f}",
        f"  Avg Win:         ${metrics.avg_win:>10.2f}",
        f"  Avg Loss:        ${metrics.avg_loss:>10.2f}",
        f"  Avg Holding Bars:{metrics.avg_holding_bars:>10.1f}",
        "",
        "=" * 50,
    ]

    return "\n".join(lines)
