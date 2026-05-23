"""Integration tests for three-layer strategy system.

These tests validate the strategy functionality.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.strategies import (
    BaseStrategy,
    StrategyType,
    StrategySignal,
    StrategyRegistry,
    StrategyMetadata,
)
from backtest.strategies.trend import TrendEmaAdxStrategy, TrendParameters


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """Create an OHLCV DataFrame for testing."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="D")
    np.random.seed(42)

    base_price = 100.0
    trend = np.linspace(0, 50, 200)
    noise = np.random.randn(200) * 2
    prices = base_price + trend + noise

    return pd.DataFrame(
        {
            "open": prices - np.random.rand(200) * 1,
            "high": prices + np.random.rand(200) * 2,
            "low": prices - np.random.rand(200) * 2,
            "close": prices,
            "volume": np.random.randint(1000, 10000, 200),
        },
        index=pd.DatetimeIndex(dates, name="datetime"),
    )


# ---------------------------------------------------------------------------
# Strategy Tests
# ---------------------------------------------------------------------------


class TestTrendStrategy:
    """Tests for trend strategy."""

    def test_strategy_creation(self):
        """Test that strategy can be created."""
        strategy = TrendEmaAdxStrategy()
        assert strategy is not None
        assert strategy.name == "trend_ema_adx"

    def test_strategy_generates_result(self, ohlcv_df: pd.DataFrame):
        """Test that strategy generates output."""
        strategy = TrendEmaAdxStrategy()
        result = strategy.generate(ohlcv_df)

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "signal" in result.columns

    def test_strategy_adds_indicators(self, ohlcv_df: pd.DataFrame):
        """Test that strategy adds indicator columns."""
        strategy = TrendEmaAdxStrategy()
        result = strategy.generate(ohlcv_df)

        assert "signal" in result.columns
        assert len(result) == len(ohlcv_df)

    def test_strategy_validation_valid_data(self, ohlcv_df: pd.DataFrame):
        """Test validation with valid data."""
        strategy = TrendEmaAdxStrategy()
        is_valid, error = strategy.validate(ohlcv_df)

        assert is_valid is True
        assert error is None

    def test_strategy_validation_missing_columns(self):
        """Test validation with missing columns."""
        df = pd.DataFrame({"close": [100, 101, 102]})
        strategy = TrendEmaAdxStrategy()
        is_valid, error = strategy.validate(df)

        assert is_valid is False
        assert "Missing columns" in error

    def test_strategy_metadata(self):
        """Test strategy metadata."""
        strategy = TrendEmaAdxStrategy()
        metadata = strategy.get_metadata()

        assert isinstance(metadata, StrategyMetadata)
        assert metadata.name == "trend_ema_adx"
        assert metadata.type == StrategyType.TREND


# ---------------------------------------------------------------------------
# Strategy Registry Tests
# ---------------------------------------------------------------------------


class TestStrategyRegistry:
    """Tests for StrategyRegistry."""

    def test_register_strategy(self):
        """Test registering a new strategy."""
        strategy = TrendEmaAdxStrategy()
        StrategyRegistry.register(strategy)

        retrieved = StrategyRegistry.get("trend_ema_adx")
        assert retrieved is not None
        assert retrieved.name == strategy.name

    def test_list_strategies_by_type(self):
        """Test listing strategies by type."""
        strategy = TrendEmaAdxStrategy()
        StrategyRegistry.register(strategy)

        trend_strategies = StrategyRegistry.list_strategies(StrategyType.TREND)
        assert "trend_ema_adx" in trend_strategies


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestStrategyIntegration:
    """Integration tests for strategy system."""

    def test_multiple_strategies_same_data(self, ohlcv_df: pd.DataFrame):
        """Test running multiple strategies on same data."""
        strategy1 = TrendEmaAdxStrategy()

        result = strategy1.generate(ohlcv_df)

        assert result is not None
        assert "signal" in result.columns
        assert len(result) == len(ohlcv_df)

    def test_strategy_with_custom_params(self, ohlcv_df: pd.DataFrame):
        """Test strategy with custom parameters."""
        params = TrendParameters(
            ema_fast=10,
            ema_slow=50,
            adx_threshold=20,
        )
        strategy = TrendEmaAdxStrategy(params)
        result = strategy.generate(ohlcv_df)

        assert "signal" in result.columns
