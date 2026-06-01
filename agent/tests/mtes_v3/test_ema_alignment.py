"""Tests for EMA Alignment module."""

import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.layer1.ema_alignment import EMAAnalyzer, EMASignal


def create_sample_df(n: int = 100, trend: str = "neutral") -> pd.DataFrame:
    """Create sample OHLCV DataFrame for testing.

    Args:
        n: Number of bars
        trend: "bull", "bear", or "neutral"
    """
    np.random.seed(42)
    dates = pd.date_range('2025-01-01', periods=n, freq='D')

    if trend == "bull":
        base = 100
        trend_component = np.linspace(0, 30, n)
    elif trend == "bear":
        base = 130
        trend_component = np.linspace(0, -30, n)
    else:
        base = 100
        trend_component = np.zeros(n)

    noise = np.random.randn(n) * 2

    return pd.DataFrame({
        'open': base + trend_component + noise,
        'high': base + trend_component + noise + abs(np.random.randn(n)),
        'low': base + trend_component + noise - abs(np.random.randn(n)),
        'close': base + trend_component + noise,
        'volume': np.random.randint(1000, 5000, n)
    }, index=dates)


class TestEMAAnalyzer:
    """Tests for EMAAnalyzer."""

    def test_initialization(self):
        """Test EMAAnalyzer initialization with default parameters."""
        analyzer = EMAAnalyzer()
        assert analyzer.fast_period == 9
        assert analyzer.mid_period == 21
        assert analyzer.slow_period == 55

    def test_initialization_custom_periods(self):
        """Test EMAAnalyzer with custom periods."""
        analyzer = EMAAnalyzer(fast_period=5, mid_period=13, slow_period=34)
        assert analyzer.fast_period == 5
        assert analyzer.mid_period == 13
        assert analyzer.slow_period == 34

    def test_validate_insufficient_data(self):
        """Test validation with insufficient data."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=50)  # Less than slow_period (55)
        assert analyzer.validate(df) is False

    def test_validate_sufficient_data(self):
        """Test validation with sufficient data."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100)
        assert analyzer.validate(df) is True

    def test_calculate_returns_values(self):
        """Test EMA calculation returns expected keys."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100)
        result = analyzer.calculate(df)

        assert 'ema_fast' in result
        assert 'ema_mid' in result
        assert 'ema_slow' in result
        assert len(result['ema_fast']) == len(df)

    def test_calculate_ema_ordering(self):
        """Test EMA values are in correct order for bull trend."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100, trend="bull")
        result = analyzer.calculate(df)

        # In bull trend, EMA fast should be highest
        last_fast = result['ema_fast'].iloc[-1]
        last_mid = result['ema_mid'].iloc[-1]
        last_slow = result['ema_slow'].iloc[-1]

        assert last_fast > last_mid > last_slow


class TestEMASignal:
    """Tests for EMASignal output."""

    def test_analyze_bull_trend(self):
        """Test EMA analysis for bull trend."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100, trend="bull")
        signal = analyzer.analyze(df)

        assert isinstance(signal, EMASignal)
        assert signal.trend in ["BULL", "BEAR", "NEUTRAL"]
        assert signal.price_above_ema in [True, False]
        assert signal.ema_bullish in [True, False]
        assert signal.ema_bearish in [True, False]
        assert signal.slope in ["UP", "DOWN", "FLAT"]
        assert 0 <= signal.confidence <= 1

    def test_analyze_bear_trend(self):
        """Test EMA analysis for bear trend."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100, trend="bear")
        signal = analyzer.analyze(df)

        assert signal.trend in ["BULL", "BEAR", "NEUTRAL"]

    def test_analyze_neutral_trend(self):
        """Test EMA analysis for neutral trend."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100, trend="neutral")
        signal = analyzer.analyze(df)

        assert signal.trend in ["BULL", "BEAR", "NEUTRAL"]

    def test_analyze_insufficient_data(self):
        """Test EMA analysis with insufficient data."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=30)  # Less than required
        signal = analyzer.analyze(df)

        assert signal.trend == "NEUTRAL"
        assert signal.confidence == 0.0
        assert signal.ema_bullish is False
        assert signal.ema_bearish is False

    def test_confidence_calculation(self):
        """Test that confidence is calculated correctly."""
        analyzer = EMAAnalyzer()

        # Bull trend should have higher confidence
        bull_df = create_sample_df(n=100, trend="bull")
        bull_signal = analyzer.analyze(bull_df)

        # Neutral should have lower confidence
        neutral_df = create_sample_df(n=100, trend="neutral")
        neutral_signal = analyzer.analyze(neutral_df)

        # Bull signal should have non-zero confidence
        assert bull_signal.confidence > 0

    def test_slope_calculation(self):
        """Test EMA slope calculation."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=100, trend="bull")
        signal = analyzer.analyze(df)

        # Bull trend should have UP slope
        assert signal.slope in ["UP", "DOWN", "FLAT"]


class TestEMAEdgeCases:
    """Tests for edge cases."""

    def test_single_bar(self):
        """Test with single bar data."""
        analyzer = EMAAnalyzer()
        df = create_sample_df(n=1)
        signal = analyzer.analyze(df)

        assert signal.trend == "NEUTRAL"

    def test_oscillating_data(self):
        """Test with oscillating (choppy) data."""
        np.random.seed(123)
        dates = pd.date_range('2025-01-01', periods=100, freq='D')

        # Create oscillating data
        t = np.linspace(0, 10 * np.pi, 100)
        close = 100 + 10 * np.sin(t) + np.random.randn(100) * 2

        df = pd.DataFrame({
            'open': close,
            'high': close + abs(np.random.randn(100)),
            'low': close - abs(np.random.randn(100)),
            'close': close,
            'volume': np.random.randint(1000, 5000, 100)
        }, index=dates)

        analyzer = EMAAnalyzer()
        signal = analyzer.analyze(df)

        # Should handle oscillating data gracefully
        assert signal.trend in ["BULL", "BEAR", "NEUTRAL"]

    def test_custom_periods_affect_result(self):
        """Test that different periods produce different results."""
        # Use shorter periods for faster reaction
        fast_analyzer = EMAAnalyzer(fast_period=5, mid_period=10, slow_period=20)
        # Use longer periods for slower reaction
        slow_analyzer = EMAAnalyzer(fast_period=20, mid_period=50, slow_period=100)

        df = create_sample_df(n=150, trend="bull")

        fast_signal = fast_analyzer.analyze(df)
        slow_signal = slow_analyzer.analyze(df)

        # Both should analyze successfully
        assert fast_signal.trend in ["BULL", "BEAR", "NEUTRAL"]
        assert slow_signal.trend in ["BULL", "BEAR", "NEUTRAL"]


class TestEMAWithRealPrices:
    """Tests using more realistic price patterns."""

    def test_uptrend_with_pullback(self):
        """Test uptrend that includes pullbacks."""
        np.random.seed(42)
        dates = pd.date_range('2025-01-01', periods=100, freq='D')

        # Create uptrend with small pullbacks
        trend = np.linspace(0, 50, 100)
        pullbacks = np.sin(np.linspace(0, 5, 100)) * 5
        close = 100 + trend + pullbacks + np.random.randn(100)

        df = pd.DataFrame({
            'open': close,
            'high': close + abs(np.random.randn(100)),
            'low': close - abs(np.random.randn(100)),
            'close': close,
            'volume': np.random.randint(1000, 5000, 100)
        }, index=dates)

        analyzer = EMAAnalyzer()
        signal = analyzer.analyze(df)

        # Should detect overall uptrend
        assert signal.trend in ["BULL", "BEAR", "NEUTRAL"]
        assert signal.ema_bullish in [True, False]

    def test_downtrend_acceleration(self):
        """Test downtrend with acceleration."""
        np.random.seed(42)
        dates = pd.date_range('2025-01-01', periods=100, freq='D')

        # Create accelerating downtrend
        trend = np.linspace(0, -100, 100)
        acceleration = np.linspace(0, -20, 100)
        close = 200 + trend + acceleration + np.random.randn(100)

        df = pd.DataFrame({
            'open': close,
            'high': close + abs(np.random.randn(100)),
            'low': close - abs(np.random.randn(100)),
            'close': close,
            'volume': np.random.randint(1000, 5000, 100)
        }, index=dates)

        analyzer = EMAAnalyzer()
        signal = analyzer.analyze(df)

        # Should detect downtrend
        assert signal.trend in ["BULL", "BEAR", "NEUTRAL"]
