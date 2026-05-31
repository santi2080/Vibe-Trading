"""Order execution simulator: simulates fills, slippage, and order state machine.

This module provides:
- OrderType: MARKET, LIMIT order types
- OrderStatus: PENDING, FILLED, PARTIAL, REJECTED, CANCELLED states
- Order: order with all parameters
- ExecutionSimulator: stateful execution engine
- simulate_fill: single-bar fill simulation
- apply_slippage: slippage calculation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class OrderType(Enum):
    """Order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status states."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Order:
    """An order to be executed.

    Args:
        order_id: Unique order identifier.
        symbol: Instrument identifier.
        side: BUY or SELL.
        order_type: MARKET, LIMIT, STOP, or STOP_LIMIT.
        quantity: Order quantity.
        price: Limit/stop price (None for market orders).
        filled_quantity: Amount filled so far.
        avg_fill_price: Average fill price.
        status: Current order status.
        created_at: When order was created.
        filled_at: When order was filled.
        slippage_bps: Slippage in basis points.
    """

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    slippage_bps: float = 1.0

    @property
    def remaining_quantity(self) -> float:
        """Quantity remaining to be filled."""
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        """Whether order is still active (pending or partial)."""
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIAL)


@dataclass
class SlippageConfig:
    """Configuration for slippage model.

    Args:
        market_slippage_bps: Slippage for market orders (default 1 bps).
        limit_slippage_bps: Slippage for limit orders (default 0 bps).
        directional_bias: Whether to add directional bias to slippage.
        volatility_adjustment: Whether to adjust slippage by volatility.
    """

    market_slippage_bps: float = 1.0
    limit_slippage_bps: float = 0.0
    directional_bias: bool = False
    volatility_adjustment: bool = False


@dataclass
class FillResult:
    """Result of a fill attempt.

    Args:
        filled: Whether the order was filled.
        fill_price: Price at which order was filled.
        fill_quantity: Quantity filled.
        status: Final order status.
        slippage_bps: Actual slippage applied.
        message: Additional information.
    """

    filled: bool
    fill_price: float
    fill_quantity: float
    status: OrderStatus
    slippage_bps: float
    message: str = ""


def apply_slippage(
    base_price: float,
    side: OrderSide,
    order_type: OrderType,
    slippage_bps: float = 1.0,
    volatility: Optional[float] = None,
) -> float:
    """Apply slippage to base price.

    For market orders: slippage reduces execution price.
    For limit orders: slippage is typically 0 (at limit price).

    Args:
        base_price: Base price (e.g., open price).
        side: BUY or SELL.
        order_type: MARKET, LIMIT, etc.
        slippage_bps: Slippage in basis points.
        volatility: Optional volatility factor.

    Returns:
        Price after slippage adjustment.
    """
    if slippage_bps <= 0:
        return base_price

    slippage_multiplier = slippage_bps / 10000.0

    if volatility is not None and volatility > 0:
        slippage_multiplier *= (1 + volatility)

    if order_type == OrderType.MARKET:
        if side == OrderSide.BUY:
            return base_price * (1 + slippage_multiplier)
        else:
            return base_price * (1 - slippage_multiplier)
    else:
        return base_price


def simulate_fill(
    order: Order,
    bar: pd.Series,
    slippage_config: Optional[SlippageConfig] = None,
    volume: Optional[float] = None,
) -> FillResult:
    """Simulate order fill on a bar.

    Args:
        order: Order to attempt to fill.
        bar: OHLCV bar with open, high, low, close.
        slippage_config: Slippage configuration.
        volume: Optional volume for limit orders.

    Returns:
        FillResult with fill details.
    """
    if slippage_config is None:
        slippage_config = SlippageConfig()

    if order.status not in (OrderStatus.PENDING, OrderStatus.PARTIAL):
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=order.status,
            slippage_bps=0.0,
            message=f"Order not fillable, status: {order.status.value}",
        )

    open_price = bar.get("open", bar.get("Open", 0))
    high_price = bar.get("high", bar.get("High", open_price))
    low_price = bar.get("low", bar.get("Low", open_price))
    close_price = bar.get("close", bar.get("Close", open_price))

    if open_price <= 0:
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.REJECTED,
            slippage_bps=0.0,
            message="Invalid price data",
        )

    if order.order_type == OrderType.MARKET:
        return _fill_market_order(order, open_price, slippage_config)
    elif order.order_type == OrderType.LIMIT:
        return _fill_limit_order(order, open_price, high_price, low_price, slippage_config, volume)
    elif order.order_type == OrderType.STOP:
        return _fill_stop_order(order, high_price, low_price, slippage_config)
    else:
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.REJECTED,
            slippage_bps=0.0,
            message=f"Unsupported order type: {order.order_type}",
        )


def _fill_market_order(
    order: Order,
    open_price: float,
    config: SlippageConfig,
) -> FillResult:
    """Fill a market order."""
    slippage_bps = config.market_slippage_bps
    fill_price = apply_slippage(open_price, order.side, OrderType.MARKET, slippage_bps)

    return FillResult(
        filled=True,
        fill_price=fill_price,
        fill_quantity=order.remaining_quantity,
        status=OrderStatus.FILLED,
        slippage_bps=slippage_bps,
        message=f"Market order filled at {fill_price:.4f}",
    )


def _fill_limit_order(
    order: Order,
    open_price: float,
    high_price: float,
    low_price: float,
    config: SlippageConfig,
    volume: Optional[float],
) -> FillResult:
    """Fill a limit order if price conditions are met."""
    if order.price is None:
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.REJECTED,
            slippage_bps=0.0,
            message="Limit order requires price",
        )

    limit_price = order.price
    slippage_bps = config.limit_slippage_bps

    can_fill = False
    if order.side == OrderSide.BUY:
        can_fill = low_price <= limit_price
    else:
        can_fill = high_price >= limit_price

    if not can_fill:
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.PENDING,
            slippage_bps=0.0,
            message=f"Limit price {limit_price} not reached",
        )

    fill_price = apply_slippage(limit_price, order.side, OrderType.LIMIT, slippage_bps)

    fill_qty = order.remaining_quantity
    if volume is not None and volume < fill_qty:
        fill_qty = volume

    return FillResult(
        filled=True,
        fill_price=fill_price,
        fill_quantity=fill_qty,
        status=OrderStatus.FILLED if fill_qty >= order.remaining_quantity else OrderStatus.PARTIAL,
        slippage_bps=slippage_bps,
        message=f"Limit order filled at {fill_price:.4f}",
    )


def _fill_stop_order(
    order: Order,
    high_price: float,
    low_price: float,
    config: SlippageConfig,
) -> FillResult:
    """Fill a stop order if price conditions are met."""
    if order.price is None:
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.REJECTED,
            slippage_bps=0.0,
            message="Stop order requires price",
        )

    stop_price = order.price
    slippage_bps = config.market_slippage_bps

    triggered = False
    if order.side == OrderSide.BUY:
        triggered = high_price >= stop_price
    else:
        triggered = low_price <= stop_price

    if not triggered:
        return FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.PENDING,
            slippage_bps=0.0,
            message=f"Stop price {stop_price} not triggered",
        )

    fill_price = apply_slippage(stop_price, order.side, OrderType.MARKET, slippage_bps)

    return FillResult(
        filled=True,
        fill_price=fill_price,
        fill_quantity=order.remaining_quantity,
        status=OrderStatus.FILLED,
        slippage_bps=slippage_bps,
        message=f"Stop order filled at {fill_price:.4f}",
    )


class ExecutionSimulator:
    """Stateful order execution simulator.

    Args:
        slippage_config: Slippage configuration.
        commission: Commission per trade (default 0).
        latency_bars: Bars of latency for order processing.
    """

    def __init__(
        self,
        slippage_config: Optional[SlippageConfig] = None,
        commission: float = 0.0,
        latency_bars: int = 0,
    ):
        self.slippage_config = slippage_config or SlippageConfig()
        self.commission = commission
        self.latency_bars = latency_bars
        self.orders: dict[str, Order] = {}
        self.order_counter = 0

    def create_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        slippage_bps: Optional[float] = None,
    ) -> Order:
        """Create a market order.

        Args:
            symbol: Instrument identifier.
            side: BUY or SELL.
            quantity: Order quantity.
            slippage_bps: Override slippage (optional).

        Returns:
            Created order.
        """
        self.order_counter += 1
        order = Order(
            order_id=f"ord_{self.order_counter}",
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            slippage_bps=slippage_bps or self.slippage_config.market_slippage_bps,
        )
        self.orders[order.order_id] = order
        return order

    def create_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        limit_price: float,
    ) -> Order:
        """Create a limit order.

        Args:
            symbol: Instrument identifier.
            side: BUY or SELL.
            quantity: Order quantity.
            limit_price: Limit price.

        Returns:
            Created order.
        """
        self.order_counter += 1
        order = Order(
            order_id=f"ord_{self.order_counter}",
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=limit_price,
            slippage_bps=self.slippage_config.limit_slippage_bps,
        )
        self.orders[order.order_id] = order
        return order

    def create_stop_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        stop_price: float,
    ) -> Order:
        """Create a stop order.

        Args:
            symbol: Instrument identifier.
            side: BUY or SELL.
            quantity: Order quantity.
            stop_price: Stop trigger price.

        Returns:
            Created order.
        """
        self.order_counter += 1
        order = Order(
            order_id=f"ord_{self.order_counter}",
            symbol=symbol,
            side=side,
            order_type=OrderType.STOP,
            quantity=quantity,
            price=stop_price,
            slippage_bps=self.slippage_config.market_slippage_bps,
        )
        self.orders[order.order_id] = order
        return order

    def process_bar(self, bar: pd.Series, volume: Optional[float] = None) -> list[FillResult]:
        """Process a bar and attempt to fill pending orders.

        Args:
            bar: OHLCV bar data.
            volume: Optional volume for limit order fills.

        Returns:
            List of fill results.
        """
        results = []

        for order in list(self.orders.values()):
            if not order.is_active:
                continue

            if order.symbol != bar.get("symbol", bar.get("Symbol", "")):
                continue

            result = simulate_fill(order, bar, self.slippage_config, volume)
            results.append(result)

            if result.filled:
                order.filled_quantity += result.fill_quantity
                order.avg_fill_price = _calc_avg_price(order, result)
                order.status = result.status
                order.filled_at = datetime.now()

        return results

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order to cancel.

        Returns:
            True if cancelled, False if not found or already filled.
        """
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if order.is_active:
            order.status = OrderStatus.CANCELLED
            return True
        return False

    def get_active_orders(self) -> list[Order]:
        """Get all active orders."""
        return [o for o in self.orders.values() if o.is_active]

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self.orders.get(order_id)

    def reset(self) -> None:
        """Reset simulator state."""
        self.orders.clear()
        self.order_counter = 0


def _calc_avg_price(order: Order, new_result: FillResult) -> float:
    """Calculate average fill price for partially filled orders."""
    if order.filled_quantity == new_result.fill_quantity:
        return new_result.fill_price

    total_value = (order.filled_quantity - new_result.fill_quantity) * order.avg_fill_price
    total_value += new_result.fill_quantity * new_result.fill_price
    return total_value / order.filled_quantity
