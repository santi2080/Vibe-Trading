"""Tests for MTES v3 Preprocessor (Layer 0)."""

import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.preprocessor import (
    Preprocessor,
    PreprocessorConfig,
    PreprocessorResult,
)


def create_sample_df(n: int = 200, trend: str = "neutral") -> pd.DataFrame:
    """Create a sample OHLCV DataFrame for testing.

    Args:
        n: Number of bars
        trend: "bull", "bear", or "neutral"

    Returns:
        OHLCV DataFrame
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


class TestPreprocessorConfig:
    """Tests for PreprocessorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PreprocessorConfig()
        assert config.adx_threshold == 20.0
        assert config.min_data_points == 200
        assert config.min_volume == 0.0
        assert config.price_col == 'close'

    def test_custom_config(self):
        """Test custom configuration."""
        config = PreprocessorConfig(
            adx_threshold=25.0,
            min_data_points=100,
            min_volume=1000.0
        )
        assert config.adx_threshold == 25.0
        assert config.min_data_points == 100
        assert config.min_volume == 1000.0


class TestPreprocessor:
    """Tests for Preprocessor class."""

    def test_validate_with_valid_data(self):
        """Test validation with valid OHLCV data."""
        df = create_sample_df(n=250)
        preprocessor = Preprocessor()
        assert preprocessor.validate(df) is True

    def test_validate_missing_columns(self):
        """Test validation with missing columns."""
        df = pd.DataFrame({'open': [1, 2, 3], 'close': [1, 2, 3]})
        preprocessor = Preprocessor()
        assert preprocessor.validate(df) is False

    def test_validate_empty_dataframe(self):
        """Test validation with empty DataFrame."""
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close'])
        preprocessor = Preprocessor()
        assert preprocessor.validate(df) is False

    def test_analyze_insufficient_data(self):
        """Test analysis with insufficient data points."""
        df = create_sample_df(n=50)  # Less than min_data_points
        preprocessor = Preprocessor()
        result = preprocessor.analyze(df)

        assert result.passed is False
        assert result.reason == "insufficient_data"
        assert result.data_points == 50

    def test_analyze_high_adx_threshold(self):
        """Test analysis with high ADX threshold."""
        df = create_sample_df(n=250, trend="bull")
        # Set high threshold so even strong trends fail
        preprocessor = Preprocessor(config=PreprocessorConfig(adx_threshold=100.0))
        result = preprocessor.analyze(df)

        # Should fail with threshold > 100
        assert result.passed is False
        assert result.reason == "adx_below_threshold"

    def test_analyze_strong_trend_passes(self):
        """Test analysis with strong trend passes prefilter."""
        df = create_sample_df(n=250, trend="bull")
        preprocessor = Preprocessor()
        result = preprocessor.analyze(df)

        assert result.passed is True
        assert result.adx_value >= 20.0
        assert result.data_points == 250

    def test_adx_calculation_accuracy(self):
        """Test ADX calculation accuracy."""
        # Create data with clear uptrend
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        df = pd.DataFrame({
            'open': np.arange(100, 200, 1.0),
            'high': np.arange(101, 201, 1.0),
            'low': np.arange(99, 199, 1.0),
            'close': np.arange(100, 200, 1.0),
        }, index=dates)

        preprocessor = Preprocessor()
        adx = preprocessor._calculate_adx(df)

        # Strong uptrend should have high ADX
        assert adx > 20.0

    def test_filter_batch(self):
        """Test batch filtering of multiple symbols."""
        data = {
            'AAPL': create_sample_df(n=250, trend="bull"),
            'GOOGL': create_sample_df(n=50, trend="neutral"),  # Insufficient data
            'MSFT': create_sample_df(n=250, trend="bear"),
        }

        preprocessor = Preprocessor()
        results = preprocessor.filter_batch(data)

        assert results['AAPL'] is True  # Strong trend
        assert results['GOOGL'] is False  # Insufficient data
        # MSFT may pass or fail depending on trend strength


class TestPreprocessorResult:
    """Tests for PreprocessorResult."""

    def test_passed_result(self):
        """Test passed result."""
        result = PreprocessorResult(
            passed=True,
            adx_value=35.0,
            data_points=250,
            avg_volume=2000.0
        )
        assert result.passed is True
        assert result.reason is None
        assert result.adx_value == 35.0

    def test_failed_result(self):
        """Test failed result."""
        result = PreprocessorResult(
            passed=False,
            reason="adx_below_threshold",
            adx_value=15.0,
            data_points=250
        )
        assert result.passed is False
        assert result.reason == "adx_below_threshold"

    def test_to_dict(self):
        """Test to_dict conversion."""
        result = PreprocessorResult(
            passed=True,
            adx_value=30.0,
            data_points=200
        )
        data = result.to_dict()
        assert data["passed"] is True
        assert data["adx_value"] == 30.0
        assert data["data_points"] == 200
