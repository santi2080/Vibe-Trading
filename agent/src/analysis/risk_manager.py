"""Risk management engine: position sizing, risk limits, and circuit breakers.

This module provides:
- RiskConfig: risk parameter configuration
- RiskManager: stateful risk management with position sizing
- calculate_position_size: ATR-based position sizing
- check_portfolio_risk: validates risk limits
- apply_circuit_breaker: daily loss protection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class RiskConfig:
    """Risk management configuration.

    Args:
        max_risk_per_trade: Maximum risk per trade as fraction of equity (default 2%).
        max_portfolio_risk: Maximum total portfolio risk (default 6%).
        daily_loss_limit: Circuit breaker daily loss limit (default 3%).
        atr_multiplier: ATR multiplier for stop loss distance (default 2.0).
        min_position_size: Minimum position size allowed.
        max_position_size: Maximum position size allowed.
    """

    max_risk_per_trade: float = 0.02
    max_portfolio_risk: float = 0.06
    daily_loss_limit: float = 0.03
    atr_multiplier: float = 2.0
    min_position_size: float = 0.1
    max_position_size: float = 100.0

    def __post_init__(self):
        """Validate risk configuration."""
        if not 0 < self.max_risk_per_trade <= 1:
            raise ValueError("max_risk_per_trade must be between 0 and 1")
        if not 0 < self.max_portfolio_risk <= 1:
            raise ValueError("max_portfolio_risk must be between 0 and 1")
        if not 0 < self.daily_loss_limit <= 1:
            raise ValueError("daily_loss_limit must be between 0 and 1")
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be positive")


@dataclass
class DailyLossRecord:
    """Track daily losses for circuit breaker.

    Args:
        date: Trading date.
        starting_equity: Equity at start of trading day.
        current_equity: Current equity.
        loss: Current loss for the day.
        circuit_breaker_triggered: Whether circuit breaker has been triggered today.
    """

    date: datetime
    starting_equity: float
    current_equity: float
    loss: float = 0.0
    circuit_breaker_triggered: bool = False

    @property
    def loss_pct(self) -> float:
        """Today's loss as percentage (positive = loss)."""
        if self.starting_equity == 0:
            return 0.0
        if self.starting_equity == self.current_equity:
            return 0.0
        return (self.starting_equity - self.current_equity) / self.starting_equity


@dataclass
class RiskManager:
    """Stateful risk management engine.

    Args:
        config: Risk configuration.
        initial_capital: Initial trading capital.
        current_capital: Current available capital.
        daily_record: Current day's loss record.
    """

    config: RiskConfig
    initial_capital: float
    current_capital: float
    daily_record: Optional[DailyLossRecord] = None

    def __post_init__(self):
        """Initialize daily record for today."""
        if self.daily_record is None:
            self._reset_daily_record()

    def _reset_daily_record(self) -> None:
        """Reset daily record for new trading day."""
        self.daily_record = DailyLossRecord(
            date=datetime.now(),
            starting_equity=self.current_capital,
            current_equity=self.current_capital,
        )

    def reset_for_new_day(self) -> None:
        """Reset circuit breaker for new trading day."""
        self._reset_daily_record()

    @property
    def total_equity(self) -> float:
        """Current total equity (capital + open P&L)."""
        return self.current_capital

    @property
    def daily_loss_pct(self) -> float:
        """Today's loss as percentage."""
        if self.daily_record is None:
            return 0.0
        return self.daily_record.loss_pct

    @property
    def is_circuit_breaker_triggered(self) -> bool:
        """Check if circuit breaker has been triggered today."""
        if self.daily_record is None:
            return False
        return self.daily_record.circuit_breaker_triggered

    def update_capital(self, new_capital: float) -> None:
        """Update capital after trade or daily change."""
        if self.daily_record is not None:
            self.daily_record.current_equity = new_capital
            self.daily_record.loss = self.starting_equity - new_capital

            if self.daily_loss_pct >= self.config.daily_loss_limit:
                self.daily_record.circuit_breaker_triggered = True
        self.current_capital = new_capital

    @property
    def starting_equity(self) -> float:
        """Equity at start of trading day."""
        if self.daily_record is None:
            return self.current_capital
        return self.daily_record.starting_equity

    def can_take_trade(self) -> tuple[bool, str]:
        """Check if a new trade can be taken.

        Returns:
            Tuple of (can_trade, reason).
        """
        if self.is_circuit_breaker_triggered:
            return False, "Circuit breaker triggered"

        if self.current_capital <= 0:
            return False, "No capital available"

        return True, "OK"

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        atr: Optional[float] = None,
        asset_class: str = "stock",
    ) -> float:
        """Calculate position size based on risk parameters.

        Uses ATR-based calculation when ATR is available:
            size = (equity * risk_pct) / (atr * atr_multiplier)

        Falls back to stop-loss based calculation:
            size = (equity * risk_pct) / |entry - stop_loss|

        Args:
            entry_price: Entry price for the trade.
            stop_loss_price: Stop loss price.
            atr: Average True Range (optional).
            asset_class: Asset class (stock, futures, crypto).

        Returns:
            Calculated position size.
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return self.config.min_position_size

        equity = self.current_capital
        risk_amount = equity * self.config.max_risk_per_trade

        if atr is not None and atr > 0:
            stop_distance = atr * self.config.atr_multiplier
        else:
            stop_distance = abs(entry_price - stop_loss_price)

        if stop_distance <= 0:
            return self.config.min_position_size

        size = risk_amount / stop_distance

        leverage = self._get_leverage(asset_class)
        size = size * leverage

        return max(self.config.min_position_size, min(size, self.config.max_position_size))

    def _get_leverage(self, asset_class: str) -> float:
        """Get leverage multiplier for asset class."""
        leverage_map = {
            "stock": 1.0,
            "etf": 1.0,
            "futures": 1.0,
            "crypto": 0.5,
            "forex": 1.0,
        }
        return leverage_map.get(asset_class.lower(), 1.0)


def calculate_position_size(
    equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = 0.02,
    atr: Optional[float] = None,
    atr_multiplier: float = 2.0,
    min_size: float = 0.1,
    max_size: float = 100.0,
) -> float:
    """Calculate position size based on risk parameters.

    Uses ATR-based calculation when ATR is available:
        size = (equity * risk_pct) / (atr * atr_multiplier)

    Falls back to stop-loss based calculation:
        size = (equity * risk_pct) / |entry - stop_loss|

    Args:
        equity: Current equity/capital.
        entry_price: Entry price for the trade.
        stop_loss_price: Stop loss price.
        risk_pct: Risk percentage (default 2%).
        atr: Average True Range (optional).
        atr_multiplier: ATR multiplier (default 2.0).
        min_size: Minimum position size (default 0.1).
        max_size: Maximum position size (default 100.0).

    Returns:
        Calculated position size.
    """
    if entry_price <= 0 or stop_loss_price <= 0 or equity <= 0:
        return min_size

    risk_amount = equity * risk_pct

    if atr is not None and atr > 0:
        stop_distance = atr * atr_multiplier
    else:
        stop_distance = abs(entry_price - stop_loss_price)

    if stop_distance <= 0:
        return min_size

    size = risk_amount / stop_distance

    return max(min_size, min(size, max_size))


def check_portfolio_risk(
    open_positions: list[dict],
    current_equity: float,
    max_portfolio_risk: float = 0.06,
) -> tuple[bool, float]:
    """Check if total portfolio risk is within limits.

    Args:
        open_positions: List of position dicts with 'risk_amount' key.
        current_equity: Current portfolio equity.
        max_portfolio_risk: Maximum portfolio risk as fraction (default 6%).

    Returns:
        Tuple of (within_limits, total_risk_pct).
    """
    if current_equity <= 0:
        return False, 1.0

    total_risk = sum(pos.get("risk_amount", 0) for pos in open_positions)
    total_risk_pct = total_risk / current_equity

    return total_risk_pct <= max_portfolio_risk, total_risk_pct


def apply_circuit_breaker(
    daily_loss_pct: float,
    daily_loss_limit: float = 0.03,
) -> tuple[bool, str]:
    """Check if circuit breaker should be triggered.

    Args:
        daily_loss_pct: Today's loss as positive percentage (e.g., 0.05 = 5%).
        daily_loss_limit: Circuit breaker threshold (default 3%).

    Returns:
        Tuple of (circuit_breaker_triggered, reason).
    """
    if daily_loss_pct <= 0:
        return False, "No loss"

    if daily_loss_pct >= daily_loss_limit:
        return True, f"Daily loss {daily_loss_pct:.2%} exceeds limit {daily_loss_limit:.2%}"

    return False, "OK"


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
) -> float:
    """Calculate risk/reward ratio for a trade.

    Args:
        entry_price: Entry price.
        stop_loss_price: Stop loss price.
        take_profit_price: Take profit price.

    Returns:
        Risk/reward ratio (higher is better).
    """
    if entry_price <= 0 or stop_loss_price <= 0 or take_profit_price <= 0:
        return 0.0

    risk = abs(entry_price - stop_loss_price)
    reward = abs(take_profit_price - entry_price)

    if risk <= 0:
        return 0.0

    return reward / risk


def calculate_kelly_criterion(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """Calculate Kelly Criterion for position sizing.

    Args:
        win_rate: Win rate (0-1).
        avg_win: Average winning amount.
        avg_loss: Average losing amount.

    Returns:
        Kelly percentage (0-1).
    """
    if avg_loss <= 0 or win_rate < 0 or win_rate > 1:
        return 0.0

    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p

    kelly = (b * p - q) / b

    return max(0.0, min(kelly, 1.0))
