"""Signal execution engine: converts MTES+SuperTrend signals into trade instructions.

This module provides:
- TradeInstruction: actionable trade command
- Position: open position tracking
- PortfolioState: portfolio-level state management
- Signal conversion: turn boolean signals into instructions
- Stop loss / take profit application
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class TradeDirection(Enum):
    """Trade direction."""

    LONG = 1
    SHORT = -1


class ExitReason(Enum):
    """Why a trade was exited."""

    SIGNAL = "signal"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    END_OF_BACKTEST = "end_of_backtest"


@dataclass(frozen=True)
class TradeInstruction:
    """An actionable trade command.

    Args:
        direction: LONG or SHORT.
        entry_price: Desired entry price.
        stop_loss: Stop loss price (None if not set).
        take_profit: Take profit price (None if not set).
        size: Position size.
        timestamp: When instruction was generated.
        signal_type: Source signal type for debugging.
    """

    direction: TradeDirection
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    size: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    signal_type: str = "unknown"


@dataclass(frozen=True)
class ClosedTrade:
    """A completed round-trip trade.

    Args:
        symbol: Instrument identifier.
        direction: LONG or SHORT.
        entry_price: Execution price at entry.
        exit_price: Execution price at exit.
        entry_time: Entry timestamp.
        exit_time: Exit timestamp.
        size: Position size.
        pnl: Realised profit/loss.
        pnl_pct: P&L as percentage of notional.
        exit_reason: Why closed.
        holding_bars: Number of bars held.
    """

    symbol: str
    direction: TradeDirection
    entry_price: float
    exit_price: float
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    size: float
    pnl: float
    pnl_pct: float
    exit_reason: ExitReason
    holding_bars: int


@dataclass
class Position:
    """An open position in a single instrument.

    Args:
        symbol: Instrument identifier.
        direction: LONG or SHORT.
        entry_price: Execution price at entry.
        entry_time: Timestamp when position was opened.
        size: Number of shares / coins.
        stop_loss: Current stop loss price.
        take_profit: Current take profit price.
        entry_bar_idx: Index in the dates array at entry.
    """

    symbol: str
    direction: TradeDirection
    entry_price: float
    entry_time: pd.Timestamp
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_bar_idx: int = 0

    @property
    def is_long(self) -> bool:
        """Whether this is a long position."""
        return self.direction == TradeDirection.LONG

    @property
    def is_short(self) -> bool:
        """Whether this is a short position."""
        return self.direction == TradeDirection.SHORT


@dataclass
class PortfolioState:
    """Portfolio-level state for tracking cash, positions, and equity.

    Args:
        initial_capital: Starting capital.
        capital: Current free cash.
        positions: Dict of symbol -> open Position.
        equity_history: List of equity snapshots.
        closed_trades: List of completed trades.
    """

    initial_capital: float
    capital: float
    positions: dict[str, Position] = field(default_factory=dict)
    equity_history: list[dict] = field(default_factory=list)
    closed_trades: list[ClosedTrade] = field(default_factory=list)

    @property
    def total_equity(self) -> float:
        """Total equity = capital + sum of position values."""
        position_value = sum(self._position_value(p) for p in self.positions.values())
        return self.capital + position_value

    @property
    def open_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)

    def _position_value(self, pos: Position) -> float:
        """Calculate current value of a position."""
        if pos.stop_loss is not None and pos.take_profit is not None:
            return pos.size
        return pos.size

    def has_position(self, symbol: str) -> bool:
        """Check if symbol has an open position."""
        return symbol in self.positions

    def record_snapshot(self, timestamp: pd.Timestamp) -> None:
        """Record an equity snapshot."""
        unrealized = sum(
            self._calc_unrealized(p) for p in self.positions.values()
        )
        self.equity_history.append(
            {
                "timestamp": timestamp,
                "capital": self.capital,
                "unrealized": unrealized,
                "equity": self.capital + unrealized,
                "positions": len(self.positions),
            }
        )

    def _calc_unrealized(self, pos: Position) -> float:
        """Calculate unrealised P&L for a position."""
        return 0.0


def convert_signal_to_instruction(
    symbol: str,
    bull_signal: bool,
    bear_signal: bool,
    entry_trigger: bool,
    st_trend: int,
    current_price: float,
    timestamp: Optional[datetime] = None,
    sl_pct: float = 0.02,
    tp_pct: float = 0.04,
    size: float = 1.0,
) -> Optional[TradeInstruction]:
    """Convert MTES+SuperTrend signals to a TradeInstruction.

    Generates a LONG instruction when bull_signal=True AND entry_trigger=True.
    Generates a SHORT instruction when bear_signal=True AND entry_trigger=True.

    Args:
        symbol: Instrument identifier.
        bull_signal: MTES bullish signal.
        bear_signal: MTES bearish signal.
        entry_trigger: SuperTrend entry trigger.
        st_trend: SuperTrend direction (1=bull, -1=bear).
        current_price: Current market price.
        timestamp: Instruction timestamp (default: now).
        sl_pct: Stop loss percentage (default: 2%).
        tp_pct: Take profit percentage (default: 4%).
        size: Position size (default: 1.0).

    Returns:
        TradeInstruction if entry conditions met, None otherwise.
    """
    if timestamp is None:
        timestamp = datetime.now()

    direction: Optional[TradeDirection] = None
    signal_type = "unknown"

    if bull_signal and entry_trigger:
        direction = TradeDirection.LONG
        signal_type = "bull_entry"
    elif bear_signal and entry_trigger:
        direction = TradeDirection.SHORT
        signal_type = "bear_entry"
    else:
        return None

    assert direction is not None

    if direction == TradeDirection.LONG:
        stop_loss = current_price * (1 - sl_pct)
        take_profit = current_price * (1 + tp_pct)
    else:
        stop_loss = current_price * (1 + sl_pct)
        take_profit = current_price * (1 - tp_pct)

    return TradeInstruction(
        direction=direction,
        entry_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        size=size,
        timestamp=timestamp,
        signal_type=signal_type,
    )


def apply_stop_loss(
    current_price: float,
    position: Position,
    timestamp: pd.Timestamp,
    bar_idx: int,
) -> tuple[bool, Optional[float]]:
    """Check if stop loss is hit and return exit price.

    Args:
        current_price: Current market price.
        position: Open position to check.
        timestamp: Current bar timestamp.
        bar_idx: Current bar index.

    Returns:
        Tuple of (stop_loss_hit, exit_price).
    """
    if position.stop_loss is None:
        return False, None

    if position.is_long and current_price <= position.stop_loss:
        return True, position.stop_loss
    if position.is_short and current_price >= position.stop_loss:
        return True, position.stop_loss

    return False, None


def apply_take_profit(
    current_price: float,
    position: Position,
    timestamp: pd.Timestamp,
    bar_idx: int,
) -> tuple[bool, Optional[float]]:
    """Check if take profit is hit and return exit price.

    Args:
        current_price: Current market price.
        position: Open position to check.
        timestamp: Current bar timestamp.
        bar_idx: Current bar index.

    Returns:
        Tuple of (take_profit_hit, exit_price).
    """
    if position.take_profit is None:
        return False, None

    if position.is_long and current_price >= position.take_profit:
        return True, position.take_profit
    if position.is_short and current_price <= position.take_profit:
        return True, position.take_profit

    return False, None


def check_exit_conditions(
    bull_signal: bool,
    bear_signal: bool,
    exit_trigger: bool,
    position: Position,
) -> bool:
    """Check if position should exit based on signals.

    Args:
        bull_signal: MTES bullish signal.
        bear_signal: MTES bearish signal.
        exit_trigger: SuperTrend exit trigger.
        position: Open position to check.

    Returns:
        True if position should exit.
    """
    if position.is_long and bear_signal and exit_trigger:
        return True
    if position.is_short and bull_signal and exit_trigger:
        return True
    return False
