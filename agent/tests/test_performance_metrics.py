"""Tests for performance_metrics module.

Covers:
- PerformanceMetrics dataclass
- calculate_metrics function
- calculate_sharpe function
- calculate_sortino function
- calculate_max_drawdown function
- calculate_trade_statistics function
- format_metrics_report function
"""

from __future__ import annotations

import pandas as pd
import pytest

from agent.src.analysis.performance_metrics import (
    PerformanceMetrics,
    calculate_max_drawdown,
    calculate_metrics,
    calculate_sharpe,
    calculate_sortino,
    calculate_trade_statistics,
    format_metrics_report,
)
from agent.src.analysis.portfolio_tracker import PortfolioTracker
from agent.src.analysis.signal_executor import ExitReason, TradeDirection


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_default_values(self):
        metrics = PerformanceMetrics()
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.win_rate == 0.0
        assert metrics.total_trades == 0

    def test_to_dict(self):
        metrics = PerformanceMetrics(total_return=0.1, win_rate=0.6)
        d = metrics.to_dict()
        assert d["total_return"] == 0.1
        assert d["win_rate"] == 0.6


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""

    def test_empty_tracker(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        metrics = calculate_metrics(tracker)
        assert metrics.total_trades == 0
        assert metrics.equity_final == 100000.0

    def test_profitable_trades(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)

        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        tracker.close_position(
            symbol="ES=F",
            exit_price=5050.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.TAKE_PROFIT,
        )

        metrics = calculate_metrics(tracker)
        assert metrics.total_trades == 1
        assert metrics.equity_final > 100000.0
        assert metrics.win_rate == 1.0

    def test_mixed_trades(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)

        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        tracker.close_position(
            symbol="ES=F",
            exit_price=5050.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.TAKE_PROFIT,
        )

        tracker.update_position(
            symbol="GC=F",
            direction=TradeDirection.LONG,
            entry_price=2000.0,
            size=1.0,
        )
        tracker.close_position(
            symbol="GC=F",
            exit_price=1950.0,
            exit_time=pd.Timestamp("2024-01-17 15:00"),
            exit_reason=ExitReason.STOP_LOSS,
        )

        metrics = calculate_metrics(tracker)
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 0.5


class TestCalculateSharpe:
    """Tests for calculate_sharpe function."""

    def test_empty_returns(self):
        returns = pd.Series([])
        sharpe = calculate_sharpe(returns)
        assert sharpe == 0.0

    def test_single_return(self):
        returns = pd.Series([0.01])
        sharpe = calculate_sharpe(returns)
        assert sharpe == 0.0

    def test_positive_returns(self):
        returns = pd.Series([0.01, 0.02, 0.015, 0.01])
        sharpe = calculate_sharpe(returns)
        assert sharpe > 0

    def test_negative_returns(self):
        returns = pd.Series([-0.01, -0.02, -0.015, -0.01])
        sharpe = calculate_sharpe(returns)
        assert sharpe < 0


class TestCalculateSortino:
    """Tests for calculate_sortino function."""

    def test_empty_returns(self):
        returns = pd.Series([])
        sortino = calculate_sortino(returns)
        assert sortino == 0.0

    def test_positive_returns_only(self):
        returns = pd.Series([0.01, 0.02, 0.015, 0.01])
        sortino = calculate_sortino(returns)
        assert sortino == 0.0

    def test_mixed_returns(self):
        returns = pd.Series([0.01, -0.01, 0.02, -0.005, 0.015])
        sortino = calculate_sortino(returns)
        assert isinstance(sortino, float)


class TestCalculateMaxDrawdown:
    """Tests for calculate_max_drawdown function."""

    def test_empty_tracker(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        dd, dd_pct, duration = calculate_max_drawdown(tracker)
        assert dd == 0.0
        assert dd_pct == 0.0

    def test_no_drawdown(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:00"))
        tracker.capital = 105000.0
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:30"))
        tracker.capital = 110000.0
        tracker.record_snapshot(pd.Timestamp("2024-01-15 11:00"))

        dd, dd_pct, duration = calculate_max_drawdown(tracker)
        assert dd == 0.0
        assert dd_pct == 0.0

    def test_with_drawdown(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))
        tracker.capital = 105000.0
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:00"))
        tracker.capital = 95000.0
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:30"))
        tracker.capital = 100000.0
        tracker.record_snapshot(pd.Timestamp("2024-01-15 11:00"))

        dd, dd_pct, duration = calculate_max_drawdown(tracker)
        assert dd > 0


class TestCalculateTradeStatistics:
    """Tests for calculate_trade_statistics function."""

    def test_empty_trades(self):
        stats = calculate_trade_statistics([])
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0

    def test_single_win(self):
        from agent.src.analysis.signal_executor import ClosedTrade

        trades = [
            ClosedTrade(
                symbol="ES=F",
                direction=TradeDirection.LONG,
                entry_price=5000.0,
                exit_price=5050.0,
                entry_time=pd.Timestamp("2024-01-15"),
                exit_time=pd.Timestamp("2024-01-16"),
                size=1.0,
                pnl=50.0,
                pnl_pct=1.0,
                exit_reason=ExitReason.TAKE_PROFIT,
                holding_bars=10,
            )
        ]
        stats = calculate_trade_statistics(trades)
        assert stats["total_trades"] == 1
        assert stats["winning_trades"] == 1
        assert stats["largest_win"] == 50.0

    def test_multiple_trades(self):
        from agent.src.analysis.signal_executor import ClosedTrade

        trades = [
            ClosedTrade(
                symbol="ES=F",
                direction=TradeDirection.LONG,
                entry_price=5000.0,
                exit_price=5050.0,
                entry_time=pd.Timestamp("2024-01-15"),
                exit_time=pd.Timestamp("2024-01-16"),
                size=1.0,
                pnl=50.0,
                pnl_pct=1.0,
                exit_reason=ExitReason.TAKE_PROFIT,
                holding_bars=10,
            ),
            ClosedTrade(
                symbol="GC=F",
                direction=TradeDirection.LONG,
                entry_price=2000.0,
                exit_price=1950.0,
                entry_time=pd.Timestamp("2024-01-17"),
                exit_time=pd.Timestamp("2024-01-18"),
                size=1.0,
                pnl=-50.0,
                pnl_pct=-2.5,
                exit_reason=ExitReason.STOP_LOSS,
                holding_bars=5,
            ),
        ]
        stats = calculate_trade_statistics(trades)
        assert stats["total_trades"] == 2
        assert stats["winning_trades"] == 1
        assert stats["losing_trades"] == 1
        assert stats["win_rate"] == 0.5


class TestFormatMetricsReport:
    """Tests for format_metrics_report function."""

    def test_format_empty_metrics(self):
        metrics = PerformanceMetrics(equity_final=100000.0, equity_peak=100000.0)
        report = format_metrics_report(metrics)
        assert "PERFORMANCE METRICS REPORT" in report
        assert "Total Return:" in report

    def test_format_profitable_metrics(self):
        metrics = PerformanceMetrics(
            total_return=0.15,
            total_return_pct=15.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=0.1,
            max_drawdown_pct=10.0,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            avg_trade_pnl=100.0,
            avg_win=200.0,
            avg_loss=100.0,
            avg_holding_bars=15.0,
            equity_final=115000.0,
            equity_peak=120000.0,
        )
        report = format_metrics_report(metrics)
        assert "15.00%" in report
        assert "1.50" in report
        assert "60.00%" in report
