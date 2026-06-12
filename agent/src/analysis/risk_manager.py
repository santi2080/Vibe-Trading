"""Risk management engine: position sizing, risk limits, and circuit breakers.

This module provides:
- RiskConfig: risk parameter configuration (enhanced with stop loss/take profit)
- RiskManager: stateful risk management with position sizing
- TradeDirection: enum for trade direction
- StopLossResult: frozen dataclass for stop loss calculation results
- TakeProfitResult: frozen dataclass for take profit calculation results
- RiskParams: frozen dataclass for comprehensive risk parameters
- calculate_position_size: ATR-based position sizing
- calculate_stop_loss: calculate stop loss price
- calculate_take_profit: calculate take profit price
- calculate_risk_params: calculate comprehensive risk parameters
- check_portfolio_risk: validates risk limits
- apply_circuit_breaker: daily loss protection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class TradeDirection(Enum):
    """Trade direction enum for consistent interface."""

    LONG = 1
    SHORT = -1


@dataclass(frozen=True)
class StopLossResult:
    """Frozen result of stop loss calculation.

    Args:
        stop_price: Calculated stop loss price.
        method: Method used ("atr" or "fixed_pct").
        risk_amount: Risk amount in currency units.
        risk_pct: Risk as percentage of entry price.
        stop_distance: Distance from entry to stop in price units.
    """

    stop_price: float
    method: str
    risk_amount: float
    risk_pct: float
    stop_distance: float


@dataclass(frozen=True)
class TakeProfitResult:
    """Frozen result of take profit calculation.

    Args:
        tp_price: Calculated take profit price.
        method: Method used ("rr", "fixed", or "atr_mult").
        reward_amount: Potential reward in currency units.
        reward_pct: Reward as percentage of entry price.
        reward_risk_ratio: Actual R:R ratio achieved.
        tp_distance: Distance from entry to take profit in price units.
    """

    tp_price: float
    method: str
    reward_amount: float
    reward_pct: float
    reward_risk_ratio: float
    tp_distance: float


@dataclass(frozen=True)
class RiskParams:
    """Comprehensive risk parameters for a trade.

    Args:
        entry_price: Entry price.
        direction: Trade direction (LONG or SHORT).
        stop_loss: Stop loss calculation result.
        take_profit: Take profit calculation result.
        position_size: Calculated position size.
        risk_amount: Total risk amount.
        reward_amount: Potential reward amount.
        risk_reward_ratio: R:R ratio.
        stop_loss_pct: Stop loss as percentage.
        take_profit_pct: Take profit as percentage.
        atr: ATR value used (if any).
        method: Method used for calculations.
    """

    entry_price: float
    direction: TradeDirection
    stop_loss: StopLossResult
    take_profit: TakeProfitResult
    position_size: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    stop_loss_pct: float
    take_profit_pct: float
    atr: Optional[float] = None
    method: str = "atr"


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
        stop_loss_method: Stop loss method ("atr" or "fixed_pct", default "atr").
        stop_loss_pct: Fixed percentage for stop loss (default 2%).
        take_profit_method: Take profit method ("rr", "fixed", or "atr_mult", default "rr").
        take_profit_rr: Risk:Reward ratio for take profit (default 2.0).
        take_profit_fixed_pct: Fixed percentage for take profit (default 4%).
        trailing_stop: Enable trailing stop (default False).
        trailing_pct: Trailing stop percentage (default 1%).
    """

    max_risk_per_trade: float = 0.02
    max_portfolio_risk: float = 0.06
    daily_loss_limit: float = 0.03
    atr_multiplier: float = 2.0
    min_position_size: float = 0.1
    max_position_size: float = 100.0
    stop_loss_method: str = "atr"
    stop_loss_pct: float = 0.02
    take_profit_method: str = "rr"
    take_profit_rr: float = 2.0
    take_profit_fixed_pct: float = 0.04
    trailing_stop: bool = False
    trailing_pct: float = 0.01

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
        if self.stop_loss_method not in ("atr", "fixed_pct"):
            raise ValueError("stop_loss_method must be 'atr' or 'fixed_pct'")
        if self.take_profit_method not in ("rr", "fixed", "atr_mult"):
            raise ValueError("take_profit_method must be 'rr', 'fixed', or 'atr_mult'")


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

    def calculate_risk_params(
        self,
        entry_price: float,
        direction: TradeDirection,
        equity: Optional[float] = None,
        atr: Optional[float] = None,
    ) -> RiskParams:
        """Calculate comprehensive risk parameters for a trade.

        Args:
            entry_price: Entry price for the trade.
            direction: Trade direction (LONG or SHORT).
            equity: Current equity (defaults to current_capital).
            atr: Average True Range (optional).

        Returns:
            RiskParams with all calculated risk parameters.
        """
        if equity is None:
            equity = self.current_capital

        # Calculate stop loss
        stop_loss = calculate_stop_loss(
            entry_price=entry_price,
            atr=atr,
            direction=direction,
            config=self.config,
        )

        # Calculate take profit
        take_profit = calculate_take_profit(
            entry_price=entry_price,
            stop_loss_price=stop_loss.stop_price,
            direction=direction,
            config=self.config,
        )

        # Calculate position size
        position_size = self.calculate_position_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss.stop_price,
            atr=atr,
        )

        return RiskParams(
            entry_price=entry_price,
            direction=direction,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            risk_amount=stop_loss.risk_amount,
            reward_amount=take_profit.reward_amount,
            risk_reward_ratio=take_profit.reward_risk_ratio,
            stop_loss_pct=stop_loss.risk_pct,
            take_profit_pct=take_profit.reward_pct,
            atr=atr,
            method=self.config.stop_loss_method if atr else "fixed_pct",
        )


def calculate_stop_loss(
    entry_price: float,
    direction: TradeDirection,
    atr: Optional[float] = None,
    config: Optional[RiskConfig] = None,
    atr_multiplier: float = 2.0,
    fixed_pct: float = 0.02,
) -> StopLossResult:
    """Calculate stop loss price.

    Uses ATR-based calculation when ATR is available:
        stop_price = entry_price - (atr * multiplier) for LONG
        stop_price = entry_price + (atr * multiplier) for SHORT

    Falls back to fixed percentage:
        stop_price = entry_price * (1 - pct) for LONG
        stop_price = entry_price * (1 + pct) for SHORT

    Args:
        entry_price: Entry price for the trade.
        direction: Trade direction (LONG or SHORT).
        atr: Average True Range (optional).
        config: RiskConfig (optional, uses default values if not provided).
        atr_multiplier: ATR multiplier (default 2.0).
        fixed_pct: Fixed percentage (default 2%).

    Returns:
        StopLossResult with calculated stop loss price and details.
    """
    # Use config values if provided
    if config is not None:
        atr_multiplier = config.atr_multiplier
        method = config.stop_loss_method
        fixed_pct = config.stop_loss_pct
    else:
        method = "atr" if atr is not None else "fixed_pct"

    if entry_price <= 0:
        return StopLossResult(
            stop_price=0.0,
            method=method,
            risk_amount=0.0,
            risk_pct=0.0,
            stop_distance=0.0,
        )

    is_long = direction == TradeDirection.LONG

    if method == "atr" and atr is not None and atr > 0:
        # ATR-based stop loss
        stop_distance = atr * atr_multiplier
        if is_long:
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance
        result_method = "atr"
    else:
        # Fixed percentage stop loss
        stop_distance = entry_price * fixed_pct
        if is_long:
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance
        result_method = "fixed_pct"

    risk_pct = fixed_pct if result_method == "fixed_pct" else (stop_distance / entry_price)
    risk_amount = entry_price * risk_pct

    return StopLossResult(
        stop_price=stop_price,
        method=result_method,
        risk_amount=risk_amount,
        risk_pct=risk_pct,
        stop_distance=stop_distance,
    )


def calculate_take_profit(
    entry_price: float,
    stop_loss_price: float,
    direction: TradeDirection,
    atr: Optional[float] = None,
    config: Optional[RiskConfig] = None,
    rr_ratio: float = 2.0,
    fixed_pct: float = 0.04,
    atr_multiplier: float = 4.0,
) -> TakeProfitResult:
    """Calculate take profit price.

    Methods:
    - "rr": Based on risk:reward ratio from stop loss distance
    - "fixed": Fixed percentage from entry price
    - "atr_mult": ATR multiple from entry price

    Args:
        entry_price: Entry price for the trade.
        stop_loss_price: Stop loss price.
        direction: Trade direction (LONG or SHORT).
        atr: Average True Range (optional).
        config: RiskConfig (optional, uses default values if not provided).
        rr_ratio: Risk:Reward ratio (default 2.0).
        fixed_pct: Fixed percentage (default 4%).
        atr_multiplier: ATR multiplier for atr_mult method (default 4.0).

    Returns:
        TakeProfitResult with calculated take profit price and details.
    """
    # Use config values if provided
    if config is not None:
        method = config.take_profit_method
        rr_ratio = config.take_profit_rr
        fixed_pct = config.take_profit_fixed_pct
        atr_multiplier = config.atr_multiplier * 2  # Default tp at 2x SL distance
    else:
        method = "rr"

    if entry_price <= 0 or stop_loss_price <= 0:
        return TakeProfitResult(
            tp_price=0.0,
            method=method,
            reward_amount=0.0,
            reward_pct=0.0,
            reward_risk_ratio=0.0,
            tp_distance=0.0,
        )

    is_long = direction == TradeDirection.LONG
    stop_distance = abs(entry_price - stop_loss_price)

    if method == "rr":
        # R:R based take profit
        tp_distance = stop_distance * rr_ratio
        if is_long:
            tp_price = entry_price + tp_distance
        else:
            tp_price = entry_price - tp_distance
        result_method = "rr"
    elif method == "atr_mult" and atr is not None and atr > 0:
        # ATR multiple based take profit
        tp_distance = atr * atr_multiplier
        if is_long:
            tp_price = entry_price + tp_distance
        else:
            tp_price = entry_price - tp_distance
        result_method = "atr_mult"
    else:
        # Fixed percentage take profit
        tp_distance = entry_price * fixed_pct
        if is_long:
            tp_price = entry_price + tp_distance
        else:
            tp_price = entry_price - tp_distance
        result_method = "fixed"

    reward_pct = tp_distance / entry_price
    reward_amount = entry_price * reward_pct

    # Calculate actual R:R achieved
    if stop_distance > 0:
        reward_risk_ratio = tp_distance / stop_distance
    else:
        reward_risk_ratio = 0.0

    return TakeProfitResult(
        tp_price=tp_price,
        method=result_method,
        reward_amount=reward_amount,
        reward_pct=reward_pct,
        reward_risk_ratio=reward_risk_ratio,
        tp_distance=tp_distance,
    )


def calculate_risk_params(
    entry_price: float,
    direction: TradeDirection,
    equity: float,
    atr: Optional[float] = None,
    config: Optional[RiskConfig] = None,
    risk_pct: float = 0.02,
    atr_multiplier: float = 2.0,
    rr_ratio: float = 2.0,
) -> RiskParams:
    """Calculate comprehensive risk parameters for a trade.

    This is a convenience function that combines stop loss, take profit,
    and position size calculations.

    Args:
        entry_price: Entry price for the trade.
        direction: Trade direction (LONG or SHORT).
        equity: Current equity/capital.
        atr: Average True Range (optional).
        config: RiskConfig (optional, uses default values if not provided).
        risk_pct: Risk percentage (default 2%).
        atr_multiplier: ATR multiplier (default 2.0).
        rr_ratio: Risk:Reward ratio (default 2.0).

    Returns:
        RiskParams with all calculated risk parameters.
    """
    # Create a default config if not provided
    if config is None:
        config = RiskConfig(
            max_risk_per_trade=risk_pct,
            atr_multiplier=atr_multiplier,
            take_profit_rr=rr_ratio,
        )

    # Calculate stop loss
    stop_loss = calculate_stop_loss(
        entry_price=entry_price,
        atr=atr,
        direction=direction,
        config=config,
    )

    # Calculate take profit
    take_profit = calculate_take_profit(
        entry_price=entry_price,
        stop_loss_price=stop_loss.stop_price,
        direction=direction,
        atr=atr,
        config=config,
    )

    # Calculate position size
    position_size = calculate_position_size(
        equity=equity,
        entry_price=entry_price,
        stop_loss_price=stop_loss.stop_price,
        risk_pct=risk_pct,
        atr=atr,
        atr_multiplier=atr_multiplier,
    )

    return RiskParams(
        entry_price=entry_price,
        direction=direction,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        risk_amount=stop_loss.risk_amount,
        reward_amount=take_profit.reward_amount,
        risk_reward_ratio=take_profit.reward_risk_ratio,
        stop_loss_pct=stop_loss.risk_pct,
        take_profit_pct=take_profit.reward_pct,
        atr=atr,
        method=config.stop_loss_method if atr else "fixed_pct",
    )


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
