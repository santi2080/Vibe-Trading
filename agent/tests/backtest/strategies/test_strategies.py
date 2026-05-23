"""Tests for strategy system.

Run with: pytest agent/tests/backtest/strategies/ -v
"""

import pytest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from agent.backtest.strategies import (
    BaseStrategy,
    StrategyType,
    StrategyRegistry,
)


def create_sample_ohlcv(
    start_date: datetime,
    end_date: datetime,
    freq: str = "1D",
    initial_price: float = 100.0,
) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    n = len(dates)

    # Generate realistic price data with trend
    np.random.seed(42)
    returns = np.random.randn(n) * 0.02 + 0.001  # Slight upward bias
    prices = initial_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(n)) * 0.01),
            "low": prices * (1 - np.abs(np.random.randn(n)) * 0.01),
            "close": prices,
            "volume": np.random.randint(1000, 10000, n),
        },
        index=dates,
    )

    # Ensure OHLC consistency
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)

    df.index.name = "timestamp"
    return df


class TestStrategyRegistry:
    """Tests for StrategyRegistry."""

    def test_register_strategy(self):
        """Test registering a strategy."""
        # Get initial count
        initial_count = len(StrategyRegistry.list_strategies())

        # Register a new strategy (using trend module)
        from agent.backtest.strategies.trend import TrendDualEmaStrategy

        strategy = TrendDualEmaStrategy(fast_period=5, slow_period=10)
        StrategyRegistry.register(strategy)

        assert strategy.name in StrategyRegistry.list_strategies()

    def test_get_strategy(self):
        """Test getting a registered strategy."""
        from agent.backtest.strategies.trend import TrendDualEmaStrategy

        strategy = TrendDualEmaStrategy()
        StrategyRegistry.register(strategy)

        retrieved = StrategyRegistry.get(strategy.name)
        assert retrieved is not None
        assert retrieved.name == strategy.name

    def test_list_by_type(self):
        """Test listing strategies by type."""
        # Import and use strategies to ensure registration
        from agent.backtest.strategies.trend import TrendDualEmaStrategy
        from agent.backtest.strategies.pullback import PullbackRsiStrategy
        from agent.backtest.strategies.entry import BreakoutEntryStrategy

        # Verify registry has strategies (auto-registered on import)
        all_strategies = StrategyRegistry.list_strategies()
        assert len(all_strategies) >= 1


class TestTrendStrategies:
    """Tests for trend strategies."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return create_sample_ohlcv(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            freq="1D",
        )

    def test_ema_adx_strategy(self, sample_data):
        """Test EMA ADX strategy."""
        from agent.backtest.strategies.trend import TrendEmaAdxStrategy

        strategy = TrendEmaAdxStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "ema_fast" in result.columns
        assert "ema_slow" in result.columns
        assert "adx" in result.columns
        assert len(result) == len(sample_data)

    def test_ema_adx_signal_values(self, sample_data):
        """Test EMA ADX produces valid signals."""
        from agent.backtest.strategies.trend import TrendEmaAdxStrategy

        strategy = TrendEmaAdxStrategy()
        result = strategy.generate(sample_data)

        # Signals should be -1, 0, or 1
        valid_signals = result["signal"].isin([-1, 0, 1]).all()
        assert valid_signals

    def test_macd_strategy(self, sample_data):
        """Test MACD strategy."""
        from agent.backtest.strategies.trend import TrendMacdStrategy

        strategy = TrendMacdStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "macd" in result.columns
        assert "signal" in result.columns  # Renamed from signal_line
        assert "histogram" in result.columns

    def test_dual_ema_strategy(self, sample_data):
        """Test dual EMA strategy."""
        from agent.backtest.strategies.trend import TrendDualEmaStrategy

        strategy = TrendDualEmaStrategy(fast_period=10, slow_period=30)
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "ema_fast" in result.columns
        assert "ema_slow" in result.columns

    def test_custom_parameters(self, sample_data):
        """Test custom parameters."""
        from agent.backtest.strategies.trend import TrendEmaAdxStrategy, TrendParameters

        # Create custom parameters
        params = TrendParameters(ema_fast=10, ema_slow=100, adx_threshold=30.0)
        strategy = TrendEmaAdxStrategy(parameters=params)

        assert strategy.parameters["ema_fast"] == 10
        assert strategy.parameters["ema_slow"] == 100


class TestPullbackStrategies:
    """Tests for pullback strategies."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return create_sample_ohlcv(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            freq="1D",
        )

    def test_rsi_strategy(self, sample_data):
        """Test RSI strategy."""
        from agent.backtest.strategies.pullback import PullbackRsiStrategy

        strategy = PullbackRsiStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "rsi" in result.columns
        # RSI should be between 0 and 100 (ignoring NaN at start)
        valid_rsi = result["rsi"].dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_bollinger_strategy(self, sample_data):
        """Test Bollinger Bands strategy."""
        from agent.backtest.strategies.pullback import PullbackBollingerBandsStrategy

        strategy = PullbackBollingerBandsStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "upper_band" in result.columns
        assert "lower_band" in result.columns

    def test_stochastic_strategy(self, sample_data):
        """Test Stochastic strategy."""
        from agent.backtest.strategies.pullback import PullbackStochasticStrategy

        strategy = PullbackStochasticStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "k_percent" in result.columns
        assert "d_percent" in result.columns


class TestEntryStrategies:
    """Tests for entry strategies."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return create_sample_ohlcv(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            freq="1D",
        )

    def test_breakout_strategy(self, sample_data):
        """Test breakout strategy."""
        from agent.backtest.strategies.entry import BreakoutEntryStrategy

        strategy = BreakoutEntryStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "rolling_high" in result.columns
        assert "rolling_low" in result.columns

    def test_volume_spike_strategy(self, sample_data):
        """Test volume spike strategy."""
        from agent.backtest.strategies.entry import VolumeSpikeEntryStrategy

        strategy = VolumeSpikeEntryStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "volume_ratio" in result.columns

    def test_vwap_strategy(self, sample_data):
        """Test VWAP strategy."""
        from agent.backtest.strategies.entry import VwapEntryStrategy

        strategy = VwapEntryStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "vwap" in result.columns

    def test_confluence_strategy(self, sample_data):
        """Test confluence strategy."""
        from agent.backtest.strategies.entry import SignalConfluenceStrategy

        strategy = SignalConfluenceStrategy()
        result = strategy.generate(sample_data)

        assert "signal" in result.columns
        assert "rsi" in result.columns


class TestStrategyValidation:
    """Tests for strategy validation."""

    def test_insufficient_data(self):
        """Test validation rejects insufficient data."""
        from agent.backtest.strategies.trend import TrendDualEmaStrategy

        strategy = TrendDualEmaStrategy()

        # Create data with only 5 bars
        df = create_sample_ohlcv(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5),
            freq="1D",
        )

        valid, error = strategy.validate(df)
        assert valid is False
        assert "20" in error

    def test_missing_columns(self):
        """Test validation rejects missing columns."""
        from agent.backtest.strategies.trend import TrendDualEmaStrategy

        strategy = TrendDualEmaStrategy()

        # Create DataFrame without required columns
        df = pd.DataFrame({"close": [100, 101, 102]})

        valid, error = strategy.validate(df)
        assert valid is False
        assert "open" in error


class TestStrategySignals:
    """Tests for signal generation."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return create_sample_ohlcv(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            freq="1D",
        )

    def test_signal_range(self, sample_data):
        """Test all strategies produce valid signal values."""
        from agent.backtest.strategies.trend import TrendDualEmaStrategy
        from agent.backtest.strategies.pullback import PullbackRsiStrategy
        from agent.backtest.strategies.entry import BreakoutEntryStrategy

        strategies = [
            TrendDualEmaStrategy(),
            PullbackRsiStrategy(),
            BreakoutEntryStrategy(),
        ]

        for strategy in strategies:
            result = strategy.generate(sample_data.copy())
            assert result["signal"].isin([-1, 0, 1]).all(), f"{strategy.name} has invalid signals"

    def test_strategy_metadata(self, sample_data):
        """Test strategy metadata is accessible."""
        from agent.backtest.strategies.trend import TrendEmaAdxStrategy

        strategy = TrendEmaAdxStrategy()
        metadata = strategy.get_metadata()

        assert metadata.name == "trend_ema_adx"
        assert metadata.type == StrategyType.TREND
        assert isinstance(metadata.parameters, dict)
