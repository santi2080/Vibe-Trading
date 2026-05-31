"""Tests for signal_executor module.

Covers:
- TradeInstruction dataclass creation
- TradeDirection and ExitReason enums
- convert_signal_to_instruction logic
- apply_stop_loss and apply_take_profit
- check_exit_conditions
- Position properties
- PortfolioState tracking
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from agent.src.analysis.signal_executor import (
    ClosedTrade,
    ExitReason,
    PortfolioState,
    Position,
    TradeDirection,
    TradeInstruction,
    apply_stop_loss,
    apply_take_profit,
    check_exit_conditions,
    convert_signal_to_instruction,
)


class TestTradeDirection:
    """Tests for TradeDirection enum."""

    def test_long_value(self):
        assert TradeDirection.LONG.value == 1

    def test_short_value(self):
        assert TradeDirection.SHORT.value == -1


class TestExitReason:
    """Tests for ExitReason enum."""

    def test_signal_value(self):
        assert ExitReason.SIGNAL.value == "signal"

    def test_stop_loss_value(self):
        assert ExitReason.STOP_LOSS.value == "stop_loss"

    def test_take_profit_value(self):
        assert ExitReason.TAKE_PROFIT.value == "take_profit"

    def test_end_of_backtest_value(self):
        assert ExitReason.END_OF_BACKTEST.value == "end_of_backtest"


class TestTradeInstruction:
    """Tests for TradeInstruction dataclass."""

    def test_create_long_instruction(self):
        ts = datetime(2024, 1, 15, 9, 30)
        instr = TradeInstruction(
            direction=TradeDirection.LONG,
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=104.0,
            size=10.0,
            timestamp=ts,
            signal_type="bull_entry",
        )
        assert instr.direction == TradeDirection.LONG
        assert instr.entry_price == 100.0
        assert instr.stop_loss == 98.0
        assert instr.take_profit == 104.0
        assert instr.size == 10.0
        assert instr.signal_type == "bull_entry"

    def test_create_short_instruction(self):
        instr = TradeInstruction(
            direction=TradeDirection.SHORT,
            entry_price=100.0,
            stop_loss=102.0,
            take_profit=96.0,
            size=5.0,
            signal_type="bear_entry",
        )
        assert instr.direction == TradeDirection.SHORT
        assert instr.entry_price == 100.0
        assert instr.stop_loss == 102.0
        assert instr.take_profit == 96.0

    def test_instruction_defaults(self):
        instr = TradeInstruction(
            direction=TradeDirection.LONG,
            entry_price=100.0,
        )
        assert instr.stop_loss is None
        assert instr.take_profit is None
        assert instr.size == 1.0
        assert instr.signal_type == "unknown"


class TestPosition:
    """Tests for Position dataclass."""

    def test_create_long_position(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=2.0,
            stop_loss=4950.0,
            take_profit=5100.0,
            entry_bar_idx=10,
        )
        assert pos.symbol == "ES=F"
        assert pos.direction == TradeDirection.LONG
        assert pos.entry_price == 5000.0
        assert pos.is_long is True
        assert pos.is_short is False

    def test_create_short_position(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            entry_time=ts,
            size=1.0,
        )
        assert pos.direction == TradeDirection.SHORT
        assert pos.is_long is False
        assert pos.is_short is True

    def test_position_properties(self):
        ts = pd.Timestamp("2024-01-15")
        long_pos = Position(
            symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            entry_time=ts,
            size=1.0,
        )
        assert long_pos.is_long is True
        assert long_pos.is_short is False

        short_pos = Position(
            symbol="TEST",
            direction=TradeDirection.SHORT,
            entry_price=100.0,
            entry_time=ts,
            size=1.0,
        )
        assert short_pos.is_long is False
        assert short_pos.is_short is True


class TestPortfolioState:
    """Tests for PortfolioState dataclass."""

    def test_create_portfolio(self):
        portfolio = PortfolioState(initial_capital=100000.0, capital=100000.0)
        assert portfolio.initial_capital == 100000.0
        assert portfolio.capital == 100000.0
        assert portfolio.positions == {}
        assert portfolio.equity_history == []
        assert portfolio.closed_trades == []
        assert portfolio.open_count == 0

    def test_total_equity_no_positions(self):
        portfolio = PortfolioState(initial_capital=100000.0, capital=100000.0)
        assert portfolio.total_equity == 100000.0

    def test_has_position_empty(self):
        portfolio = PortfolioState(initial_capital=100000.0, capital=100000.0)
        assert portfolio.has_position("ES=F") is False

    def test_record_snapshot(self):
        portfolio = PortfolioState(initial_capital=100000.0, capital=100000.0)
        ts = pd.Timestamp("2024-01-15 09:30")
        portfolio.record_snapshot(ts)
        assert len(portfolio.equity_history) == 1
        snap = portfolio.equity_history[0]
        assert snap["timestamp"] == ts
        assert snap["capital"] == 100000.0
        assert snap["positions"] == 0


class TestConvertSignalToInstruction:
    """Tests for convert_signal_to_instruction function."""

    def test_bull_signal_with_entry_trigger_generates_long(self):
        ts = datetime(2024, 1, 15, 9, 30)
        result = convert_signal_to_instruction(
            symbol="ES=F",
            bull_signal=True,
            bear_signal=False,
            entry_trigger=True,
            st_trend=1,
            current_price=5000.0,
            timestamp=ts,
        )
        assert result is not None
        assert result.direction == TradeDirection.LONG
        assert result.entry_price == 5000.0
        assert result.signal_type == "bull_entry"
        assert result.stop_loss == 5000.0 * 0.98
        assert result.take_profit == 5000.0 * 1.04

    def test_bear_signal_with_entry_trigger_generates_short(self):
        result = convert_signal_to_instruction(
            symbol="GC=F",
            bull_signal=False,
            bear_signal=True,
            entry_trigger=True,
            st_trend=-1,
            current_price=2000.0,
        )
        assert result is not None
        assert result.direction == TradeDirection.SHORT
        assert result.entry_price == 2000.0
        assert result.signal_type == "bear_entry"
        assert result.stop_loss == 2000.0 * 1.02
        assert result.take_profit == 2000.0 * 0.96

    def test_bull_signal_without_entry_trigger_returns_none(self):
        result = convert_signal_to_instruction(
            symbol="ES=F",
            bull_signal=True,
            bear_signal=False,
            entry_trigger=False,
            st_trend=1,
            current_price=5000.0,
        )
        assert result is None

    def test_bear_signal_without_entry_trigger_returns_none(self):
        result = convert_signal_to_instruction(
            symbol="GC=F",
            bull_signal=False,
            bear_signal=True,
            entry_trigger=False,
            st_trend=-1,
            current_price=2000.0,
        )
        assert result is None

    def test_no_signal_returns_none(self):
        result = convert_signal_to_instruction(
            symbol="ES=F",
            bull_signal=False,
            bear_signal=False,
            entry_trigger=True,
            st_trend=0,
            current_price=5000.0,
        )
        assert result is None

    def test_custom_sl_tp_percentages(self):
        result = convert_signal_to_instruction(
            symbol="ES=F",
            bull_signal=True,
            bear_signal=False,
            entry_trigger=True,
            st_trend=1,
            current_price=5000.0,
            sl_pct=0.01,
            tp_pct=0.03,
        )
        assert result is not None
        assert result.direction == TradeDirection.LONG
        assert result.stop_loss == 5000.0 * 0.99
        assert result.take_profit == 5000.0 * 1.03

    def test_custom_size(self):
        result = convert_signal_to_instruction(
            symbol="ES=F",
            bull_signal=True,
            bear_signal=False,
            entry_trigger=True,
            st_trend=1,
            current_price=5000.0,
            size=5.0,
        )
        assert result is not None
        assert result.size == 5.0

    def test_bear_and_bull_both_true_prefers_bull(self):
        """When both signals are True, bull takes priority (LONG)."""
        result = convert_signal_to_instruction(
            symbol="ES=F",
            bull_signal=True,
            bear_signal=True,
            entry_trigger=True,
            st_trend=1,
            current_price=5000.0,
        )
        assert result is not None
        assert result.direction == TradeDirection.LONG


class TestApplyStopLoss:
    """Tests for apply_stop_loss function."""

    def test_long_position_stop_loss_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
            stop_loss=4950.0,
        )
        hit, exit_price = apply_stop_loss(
            current_price=4949.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is True
        assert exit_price == 4950.0

    def test_long_position_stop_loss_not_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
            stop_loss=4950.0,
        )
        hit, exit_price = apply_stop_loss(
            current_price=4960.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is False
        assert exit_price is None

    def test_short_position_stop_loss_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            entry_time=ts,
            size=1.0,
            stop_loss=2020.0,
        )
        hit, exit_price = apply_stop_loss(
            current_price=2021.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is True
        assert exit_price == 2020.0

    def test_short_position_stop_loss_not_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            entry_time=ts,
            size=1.0,
            stop_loss=2020.0,
        )
        hit, exit_price = apply_stop_loss(
            current_price=2010.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is False
        assert exit_price is None

    def test_no_stop_loss_set(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
            stop_loss=None,
        )
        hit, exit_price = apply_stop_loss(
            current_price=4900.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is False
        assert exit_price is None


class TestApplyTakeProfit:
    """Tests for apply_take_profit function."""

    def test_long_position_take_profit_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
            take_profit=5100.0,
        )
        hit, exit_price = apply_take_profit(
            current_price=5101.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is True
        assert exit_price == 5100.0

    def test_long_position_take_profit_not_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
            take_profit=5100.0,
        )
        hit, exit_price = apply_take_profit(
            current_price=5050.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is False
        assert exit_price is None

    def test_short_position_take_profit_hit(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            entry_time=ts,
            size=1.0,
            take_profit=1950.0,
        )
        hit, exit_price = apply_take_profit(
            current_price=1949.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is True
        assert exit_price == 1950.0

    def test_no_take_profit_set(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
            take_profit=None,
        )
        hit, exit_price = apply_take_profit(
            current_price=5200.0,
            position=pos,
            timestamp=ts,
            bar_idx=5,
        )
        assert hit is False
        assert exit_price is None


class TestCheckExitConditions:
    """Tests for check_exit_conditions function."""

    def test_long_position_exit_on_bear_signal(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
        )
        result = check_exit_conditions(
            bull_signal=False,
            bear_signal=True,
            exit_trigger=True,
            position=pos,
        )
        assert result is True

    def test_short_position_exit_on_bull_signal(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="GC=F",
            direction=TradeDirection.SHORT,
            entry_price=2000.0,
            entry_time=ts,
            size=1.0,
        )
        result = check_exit_conditions(
            bull_signal=True,
            bear_signal=False,
            exit_trigger=True,
            position=pos,
        )
        assert result is True

    def test_long_position_no_exit_without_bear_signal(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
        )
        result = check_exit_conditions(
            bull_signal=True,
            bear_signal=False,
            exit_trigger=True,
            position=pos,
        )
        assert result is False

    def test_no_exit_without_exit_trigger(self):
        ts = pd.Timestamp("2024-01-15 09:30")
        pos = Position(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            entry_time=ts,
            size=1.0,
        )
        result = check_exit_conditions(
            bull_signal=False,
            bear_signal=True,
            exit_trigger=False,
            position=pos,
        )
        assert result is False


class TestClosedTrade:
    """Tests for ClosedTrade dataclass."""

    def test_create_closed_trade(self):
        entry_time = pd.Timestamp("2024-01-15 09:30")
        exit_time = pd.Timestamp("2024-01-16 15:00")
        trade = ClosedTrade(
            symbol="ES=F",
            direction=TradeDirection.LONG,
            entry_price=5000.0,
            exit_price=5050.0,
            entry_time=entry_time,
            exit_time=exit_time,
            size=1.0,
            pnl=50.0,
            pnl_pct=1.0,
            exit_reason=ExitReason.TAKE_PROFIT,
            holding_bars=30,
        )
        assert trade.symbol == "ES=F"
        assert trade.direction == TradeDirection.LONG
        assert trade.pnl == 50.0
        assert trade.exit_reason == ExitReason.TAKE_PROFIT
        assert trade.holding_bars == 30
