"""Portfolio tracker: tracks cash, positions, equity, and trade records.

This module provides:
- PortfolioTracker: stateful portfolio management
- update_position: update position with current prices
- close_position: close position and record trade
- get_equity: calculate current total equity
- get_drawdown: calculate current drawdown
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from agent.src.analysis.signal_executor import (
    ClosedTrade,
    ExitReason,
    Position,
    TradeDirection,
)
from agent.backtest.models import EquitySnapshot


@dataclass
class PortfolioTracker:
    """Portfolio state tracker with equity curve and trade recording.

    Args:
        initial_capital: Starting capital.
        capital: Current free cash.
        positions: Dict of symbol -> Position.
        equity_history: List of equity snapshots.
        closed_trades: List of completed trades.
        max_drawdown: Peak equity for drawdown calculation.
    """

    initial_capital: float
    capital: float
    positions: dict[str, Position] = field(default_factory=dict)
    equity_history: list[EquitySnapshot] = field(default_factory=list)
    closed_trades: list[ClosedTrade] = field(default_factory=list)
    max_drawdown: float = 0.0

    @property
    def total_equity(self) -> float:
        """Total equity = capital + sum of position values."""
        position_value = sum(self._calc_position_value(p) for p in self.positions.values())
        return self.capital + position_value

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L across all positions."""
        return sum(self._calc_unrealized(p) for p in self.positions.values())

    @property
    def open_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)

    @property
    def closed_count(self) -> int:
        """Number of closed trades."""
        return len(self.closed_trades)

    def _calc_position_value(self, pos: Position) -> float:
        """Calculate current value of a position (notional)."""
        return pos.size * pos.entry_price

    def _calc_unrealized(self, pos: Position) -> float:
        """Calculate unrealised P&L for a position."""
        if pos.is_long:
            return 0.0
        else:
            return 0.0

    def has_position(self, symbol: str) -> bool:
        """Check if symbol has an open position."""
        return symbol in self.positions

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        return self.positions.get(symbol)

    def update_position(
        self,
        symbol: str,
        direction: TradeDirection,
        entry_price: float,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        entry_time: Optional[pd.Timestamp] = None,
        entry_bar_idx: int = 0,
    ) -> Position:
        """Open or update a position.

        Args:
            symbol: Instrument identifier.
            direction: LONG or SHORT.
            entry_price: Entry price.
            size: Position size.
            stop_loss: Stop loss price.
            take_profit: Take profit price.
            entry_time: Entry timestamp.
            entry_bar_idx: Entry bar index.

        Returns:
            Updated position.
        """
        if entry_time is None:
            entry_time = pd.Timestamp.now()

        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.size = size
            pos.stop_loss = stop_loss
            pos.take_profit = take_profit
            return pos
        else:
            pos = Position(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                entry_time=entry_time,
                size=size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_bar_idx=entry_bar_idx,
            )
            self.positions[symbol] = pos
            return pos

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_time: pd.Timestamp,
        exit_reason: ExitReason,
        bar_idx: Optional[int] = None,
        commission: float = 0.0,
    ) -> Optional[ClosedTrade]:
        """Close a position and record the trade.

        Args:
            symbol: Instrument to close.
            exit_price: Exit execution price.
            exit_time: Exit timestamp.
            exit_reason: Reason for exit.
            bar_idx: Exit bar index.
            commission: Commission paid.

        Returns:
            ClosedTrade if position existed, None otherwise.
        """
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]

        if bar_idx is None:
            bar_idx = 0

        holding_bars = bar_idx - pos.entry_bar_idx

        if pos.is_long:
            pnl = (exit_price - pos.entry_price) * pos.size - commission
        else:
            pnl = (pos.entry_price - exit_price) * pos.size - commission

        pnl_pct = (pnl / (pos.entry_price * pos.size)) * 100 if pos.entry_price > 0 else 0.0

        trade = ClosedTrade(
            symbol=symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            size=pos.size,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            holding_bars=holding_bars,
        )

        self.closed_trades.append(trade)
        self.capital += pnl
        del self.positions[symbol]

        return trade

    def record_snapshot(self, timestamp: pd.Timestamp) -> None:
        """Record an equity snapshot.

        Args:
            timestamp: Bar timestamp.
        """
        equity = self.total_equity

        snapshot = EquitySnapshot(
            timestamp=timestamp,
            capital=self.capital,
            unrealized=self.unrealized_pnl,
            equity=equity,
            positions=self.open_count,
        )
        self.equity_history.append(snapshot)

        if equity > self.max_drawdown:
            self.max_drawdown = equity

    def get_equity_series(self) -> pd.Series:
        """Get equity history as Series.

        Returns:
            Series with equity values.
        """
        if not self.equity_history:
            return pd.Series([], dtype=float)

        return pd.Series(
            [s.equity for s in self.equity_history],
            index=[s.timestamp for s in self.equity_history],
        )

    def get_drawdown_series(self) -> pd.Series:
        """Get drawdown history as Series.

        Returns:
            Series with drawdown percentages.
        """
        if not self.equity_history:
            return pd.Series([], dtype=float)

        max_equity = 0.0
        drawdowns = []

        for s in self.equity_history:
            if s.equity > max_equity:
                max_equity = s.equity
            if max_equity > 0:
                dd = (max_equity - s.equity) / max_equity
            else:
                dd = 0.0
            drawdowns.append(dd)

        return pd.Series(
            drawdowns,
            index=[s.timestamp for s in self.equity_history],
        )

    def get_drawdown(self) -> float:
        """Get current drawdown percentage.

        Returns:
            Current drawdown (positive = loss from peak).
        """
        if self.max_drawdown <= 0:
            return 0.0

        equity = self.total_equity
        if equity >= self.max_drawdown:
            return 0.0

        return (self.max_drawdown - equity) / self.max_drawdown

    def get_trade_summary(self) -> dict:
        """Get summary statistics of closed trades.

        Returns:
            Dict with trade statistics.
        """
        if not self.closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
            }

        winning = [t for t in self.closed_trades if t.pnl > 0]
        losing = [t for t in self.closed_trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in self.closed_trades)
        avg_pnl = total_pnl / len(self.closed_trades) if self.closed_trades else 0.0

        return {
            "total_trades": len(self.closed_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(self.closed_trades) if self.closed_trades else 0.0,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
        }

    def reset(self) -> None:
        """Reset portfolio state."""
        self.capital = self.initial_capital
        self.positions.clear()
        self.equity_history.clear()
        self.closed_trades.clear()
        self.max_drawdown = 0.0
