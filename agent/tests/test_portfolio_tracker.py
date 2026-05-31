"""Tests for portfolio_tracker module.

Covers:
- PortfolioTracker initialization
- Position management (open, update, close)
- Equity calculation
- Drawdown tracking
- Trade recording
"""

from __future__ import annotations

import pandas as pd
import pytest

from agent.src.analysis.portfolio_tracker import PortfolioTracker
from agent.src.analysis.signal_executor import ExitReason, TradeDirection


class TestPortfolioTracker:
    """Tests for PortfolioTracker class."""

    def test_create_tracker(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        assert tracker.initial_capital == 100000.0
        assert tracker.capital == 100000.0
        assert tracker.total_equity == 100000.0
        assert tracker.open_count == 0
        assert tracker.closed_count == 0

    def test_total_equity_with_positions(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        assert tracker.total_equity == 105000.0

    def test_has_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        assert tracker.has_position("ES=F") is False

        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        assert tracker.has_position("ES=F") is True

    def test_get_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        pos = tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        retrieved = tracker.get_position("ES=F")
        assert retrieved is pos

    def test_get_position_not_found(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        assert tracker.get_position("ES=F") is None


class TestUpdatePosition:
    """Tests for update_position method."""

    def test_open_long_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        pos = tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=2.0,
            stop_loss=4950.0,
            take_profit=5100.0,
        )
        assert pos.symbol == "ES=F"
        assert pos.direction == TradeDirection.LONG
        assert pos.entry_price == 5000.0
        assert pos.size == 2.0
        assert pos.stop_loss == 4950.0
        assert pos.take_profit == 5100.0
        assert tracker.open_count == 1

    def test_open_short_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        pos = tracker.update_position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            size=1.0,
        )
        assert pos.direction == TradeDirection.SHORT
        assert tracker.open_count == 1

    def test_update_existing_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=3.0,
        )
        assert tracker.open_count == 1
        assert tracker.get_position("ES=F").size == 3.0


class TestClosePosition:
    """Tests for close_position method."""

    def test_close_long_profitable(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        trade = tracker.close_position(
            symbol="ES=F",
            exit_price=5050.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.TAKE_PROFIT,
            bar_idx=10,
        )
        assert trade is not None
        assert trade.pnl == 50.0
        assert tracker.capital == 100050.0
        assert tracker.open_count == 0
        assert tracker.closed_count == 1

    def test_close_long_losing(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        trade = tracker.close_position(
            symbol="ES=F",
            exit_price=4950.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.STOP_LOSS,
            bar_idx=5,
        )
        assert trade is not None
        assert trade.pnl == -50.0
        assert tracker.capital == 99950.0

    def test_close_short_profitable(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            size=1.0,
        )
        trade = tracker.close_position(
            symbol="GC=F",
            exit_price=1950.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.TAKE_PROFIT,
            bar_idx=10,
        )
        assert trade is not None
        assert trade.pnl == 50.0

    def test_close_short_losing(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            size=1.0,
        )
        trade = tracker.close_position(
            symbol="GC=F",
            exit_price=2050.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.STOP_LOSS,
            bar_idx=5,
        )
        assert trade is not None
        assert trade.pnl == -50.0

    def test_close_nonexistent_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        trade = tracker.close_position(
            symbol="ES=F",
            exit_price=5050.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.TAKE_PROFIT,
        )
        assert trade is None

    def test_close_with_commission(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        trade = tracker.close_position(
            symbol="ES=F",
            exit_price=5050.0,
            exit_time=pd.Timestamp("2024-01-16 15:00"),
            exit_reason=ExitReason.TAKE_PROFIT,
            commission=5.0,
        )
        assert trade.pnl == 45.0


class TestEquityCalculation:
    """Tests for equity calculations."""

    def test_total_equity_no_positions(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        assert tracker.total_equity == 100000.0

    def test_total_equity_with_long_position(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        assert tracker.total_equity == 105000.0

    def test_unrealized_pnl(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        assert tracker.unrealized_pnl == 0.0


class TestDrawdown:
    """Tests for drawdown tracking."""

    def test_initial_drawdown_zero(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        assert tracker.get_drawdown() == 0.0

    def test_drawdown_after_loss(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))

        tracker.capital = 95000.0
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:00"))

        assert tracker.get_drawdown() > 0


class TestRecordSnapshot:
    """Tests for equity snapshots."""

    def test_record_snapshot(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))

        assert len(tracker.equity_history) == 1
        snap = tracker.equity_history[0]
        assert snap.equity == 105000.0
        assert snap.positions == 1

    def test_get_equity_series(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:00"))
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:30"))

        series = tracker.get_equity_series()
        assert len(series) == 3

    def test_get_drawdown_series(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))
        tracker.record_snapshot(pd.Timestamp("2024-01-15 10:00"))

        series = tracker.get_drawdown_series()
        assert len(series) == 2


class TestTradeSummary:
    """Tests for trade summary statistics."""

    def test_empty_summary(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        summary = tracker.get_trade_summary()

        assert summary["total_trades"] == 0
        assert summary["winning_trades"] == 0
        assert summary["losing_trades"] == 0
        assert summary["win_rate"] == 0.0

    def test_with_trades(self):
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

        summary = tracker.get_trade_summary()

        assert summary["total_trades"] == 2
        assert summary["winning_trades"] == 1
        assert summary["losing_trades"] == 1
        assert summary["win_rate"] == 0.5


class TestReset:
    """Tests for reset method."""

    def test_reset(self):
        tracker = PortfolioTracker(initial_capital=100000.0, capital=100000.0)
        tracker.update_position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            size=1.0,
        )
        tracker.record_snapshot(pd.Timestamp("2024-01-15 09:30"))

        tracker.reset()

        assert tracker.capital == 100000.0
        assert tracker.open_count == 0
        assert len(tracker.equity_history) == 0
