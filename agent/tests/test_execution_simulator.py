"""Tests for execution_simulator module.

Covers:
- OrderType, OrderSide, OrderStatus enums
- Order dataclass
- apply_slippage function
- simulate_fill function
- ExecutionSimulator class
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from agent.src.analysis.execution_simulator import (
    ExecutionSimulator,
    FillResult,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SlippageConfig,
    apply_slippage,
    simulate_fill,
)


class TestOrderType:
    """Tests for OrderType enum."""

    def test_market_value(self):
        assert OrderType.MARKET.value == "market"

    def test_limit_value(self):
        assert OrderType.LIMIT.value == "limit"

    def test_stop_value(self):
        assert OrderType.STOP.value == "stop"


class TestOrderSide:
    """Tests for OrderSide enum."""

    def test_buy_value(self):
        assert OrderSide.BUY.value == "buy"

    def test_sell_value(self):
        assert OrderSide.SELL.value == "sell"


class TestOrderStatus:
    """Tests for OrderStatus enum."""

    def test_pending_value(self):
        assert OrderStatus.PENDING.value == "pending"

    def test_filled_value(self):
        assert OrderStatus.FILLED.value == "filled"

    def test_partial_value(self):
        assert OrderStatus.PARTIAL.value == "partial"


class TestOrder:
    """Tests for Order dataclass."""

    def test_create_market_order(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
        )
        assert order.order_id == "ord_1"
        assert order.symbol == "ES=F"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 10.0
        assert order.filled_quantity == 0.0
        assert order.status == OrderStatus.PENDING

    def test_remaining_quantity(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
        )
        assert order.remaining_quantity == 10.0
        order.filled_quantity = 3.0
        assert order.remaining_quantity == 7.0

    def test_is_active_pending(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
        )
        assert order.is_active is True

    def test_is_active_filled(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
            status=OrderStatus.FILLED,
        )
        assert order.is_active is False


class TestSlippageConfig:
    """Tests for SlippageConfig dataclass."""

    def test_default_values(self):
        config = SlippageConfig()
        assert config.market_slippage_bps == 1.0
        assert config.limit_slippage_bps == 0.0

    def test_custom_values(self):
        config = SlippageConfig(
            market_slippage_bps=2.0,
            limit_slippage_bps=0.5,
        )
        assert config.market_slippage_bps == 2.0
        assert config.limit_slippage_bps == 0.5


class TestApplySlippage:
    """Tests for apply_slippage function."""

    def test_no_slippage(self):
        price = apply_slippage(100.0, OrderSide.BUY, OrderType.MARKET, 0.0)
        assert price == 100.0

    def test_market_buy_slippage(self):
        price = apply_slippage(100.0, OrderSide.BUY, OrderType.MARKET, 10.0)
        expected = 100.0 * (1 + 10.0 / 10000.0)
        assert price == pytest.approx(expected)

    def test_market_sell_slippage(self):
        price = apply_slippage(100.0, OrderSide.SELL, OrderType.MARKET, 10.0)
        expected = 100.0 * (1 - 10.0 / 10000.0)
        assert price == pytest.approx(expected)

    def test_limit_order_no_slippage(self):
        price = apply_slippage(100.0, OrderSide.BUY, OrderType.LIMIT, 10.0)
        assert price == 100.0


class TestSimulateFill:
    """Tests for simulate_fill function."""

    def create_bar(self, open_p=100.0, high_p=101.0, low_p=99.0, close_p=100.0):
        return pd.Series({
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
        })

    def test_market_order_fills(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
        )
        bar = self.create_bar()
        result = simulate_fill(order, bar)

        assert result.filled is True
        assert result.fill_quantity == 10.0
        assert result.status == OrderStatus.FILLED

    def test_market_sell_order_fills(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=10.0,
        )
        bar = self.create_bar()
        result = simulate_fill(order, bar)

        assert result.filled is True
        assert result.fill_quantity == 10.0

    def test_limit_order_buy_fills_when_price_reaches(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10.0,
            price=100.0,
        )
        bar = self.create_bar(open_p=100.0, high_p=101.0, low_p=99.0)
        result = simulate_fill(order, bar)

        assert result.filled is True
        assert result.fill_quantity == 10.0

    def test_limit_order_buy_does_not_fill_above_limit(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10.0,
            price=98.0,
        )
        bar = self.create_bar(open_p=100.0, high_p=101.0, low_p=99.0)
        result = simulate_fill(order, bar)

        assert result.filled is False
        assert result.status == OrderStatus.PENDING

    def test_limit_order_sell_fills_when_price_reaches(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=10.0,
            price=100.0,
        )
        bar = self.create_bar(open_p=100.0, high_p=101.0, low_p=99.0)
        result = simulate_fill(order, bar)

        assert result.filled is True
        assert result.fill_quantity == 10.0

    def test_stop_order_triggered(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.STOP,
            quantity=10.0,
            price=101.0,
        )
        bar = self.create_bar(open_p=100.0, high_p=102.0, low_p=99.0)
        result = simulate_fill(order, bar)

        assert result.filled is True
        assert result.fill_quantity == 10.0

    def test_stop_order_not_triggered(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.STOP,
            quantity=10.0,
            price=103.0,
        )
        bar = self.create_bar(open_p=100.0, high_p=102.0, low_p=99.0)
        result = simulate_fill(order, bar)

        assert result.filled is False
        assert result.status == OrderStatus.PENDING

    def test_already_filled_order(self):
        order = Order(
            order_id="ord_1",
            symbol="ES=F",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
            status=OrderStatus.FILLED,
        )
        bar = self.create_bar()
        result = simulate_fill(order, bar)

        assert result.filled is False


class TestExecutionSimulator:
    """Tests for ExecutionSimulator class."""

    def test_create_simulator(self):
        sim = ExecutionSimulator()
        assert sim.slippage_config.market_slippage_bps == 1.0
        assert sim.commission == 0.0
        assert len(sim.orders) == 0

    def test_create_market_order(self):
        sim = ExecutionSimulator()
        order = sim.create_market_order("ES=F", OrderSide.BUY, 10.0)

        assert order.symbol == "ES=F"
        assert order.side == OrderSide.BUY
        assert order.quantity == 10.0
        assert order.order_type == OrderType.MARKET
        assert order.order_id == "ord_1"

    def test_create_limit_order(self):
        sim = ExecutionSimulator()
        order = sim.create_limit_order("ES=F", OrderSide.BUY, 10.0, 100.0)

        assert order.order_type == OrderType.LIMIT
        assert order.price == 100.0
        assert order.order_id == "ord_1"

    def test_create_stop_order(self):
        sim = ExecutionSimulator()
        order = sim.create_stop_order("ES=F", OrderSide.BUY, 10.0, 105.0)

        assert order.order_type == OrderType.STOP
        assert order.price == 105.0

    def test_process_bar_market_order(self):
        sim = ExecutionSimulator()
        sim.create_market_order("ES=F", OrderSide.BUY, 10.0)

        bar = pd.Series({
            "symbol": "ES=F",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
        })
        results = sim.process_bar(bar)

        assert len(results) == 1
        assert results[0].filled is True

    def test_process_bar_no_matching_orders(self):
        sim = ExecutionSimulator()
        sim.create_market_order("ES=F", OrderSide.BUY, 10.0)

        bar = pd.Series({
            "symbol": "GC=F",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
        })
        results = sim.process_bar(bar)

        assert len(results) == 0

    def test_cancel_order(self):
        sim = ExecutionSimulator()
        order = sim.create_market_order("ES=F", OrderSide.BUY, 10.0)

        cancelled = sim.cancel_order(order.order_id)
        assert cancelled is True
        assert order.status == OrderStatus.CANCELLED

    def test_get_active_orders(self):
        sim = ExecutionSimulator()
        sim.create_market_order("ES=F", OrderSide.BUY, 10.0)
        order2 = sim.create_market_order("GC=F", OrderSide.SELL, 5.0)

        active = sim.get_active_orders()
        assert len(active) == 2

        sim.cancel_order(order2.order_id)
        active = sim.get_active_orders()
        assert len(active) == 1

    def test_reset(self):
        sim = ExecutionSimulator()
        sim.create_market_order("ES=F", OrderSide.BUY, 10.0)

        sim.reset()
        assert len(sim.orders) == 0
        assert sim.order_counter == 0

    def test_order_counter_increments(self):
        sim = ExecutionSimulator()
        sim.create_market_order("ES=F", OrderSide.BUY, 10.0)
        sim.create_limit_order("GC=F", OrderSide.SELL, 5.0, 2000.0)
        sim.create_stop_order("CL=F", OrderSide.BUY, 3.0, 80.0)

        assert sim.order_counter == 3


class TestFillResult:
    """Tests for FillResult dataclass."""

    def test_create_success_result(self):
        result = FillResult(
            filled=True,
            fill_price=100.0,
            fill_quantity=10.0,
            status=OrderStatus.FILLED,
            slippage_bps=1.0,
        )
        assert result.filled is True
        assert result.fill_price == 100.0
        assert result.fill_quantity == 10.0
        assert result.status == OrderStatus.FILLED
        assert result.slippage_bps == 1.0

    def test_create_failure_result(self):
        result = FillResult(
            filled=False,
            fill_price=0.0,
            fill_quantity=0.0,
            status=OrderStatus.PENDING,
            slippage_bps=0.0,
            message="Price not reached",
        )
        assert result.filled is False
        assert result.message == "Price not reached"
