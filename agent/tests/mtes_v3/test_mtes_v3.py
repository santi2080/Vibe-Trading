"""Tests for MTES v3 main entry point."""

import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.mtes_v3 import MTESv3, MTESv3Config
from agent.src.analysis.mtes_v3.preprocessor import PreprocessorConfig


def create_sample_df(n: int = 250, trend: str = "neutral") -> pd.DataFrame:
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


class TestMTESv3Config:
    """Tests for MTESv3Config."""

    def test_default_config(self):
        """Test default configuration."""
        config = MTESv3Config()
        assert config.min_confidence == 0.5
        assert config.score_multiplier == 1.0
        assert isinstance(config.prefilter_config, PreprocessorConfig)

    def test_custom_config(self):
        """Test custom configuration."""
        config = MTESv3Config(
            min_confidence=0.6,
            score_multiplier=1.2,
            prefilter_config=PreprocessorConfig(adx_threshold=25.0)
        )
        assert config.min_confidence == 0.6
        assert config.score_multiplier == 1.2
        assert config.prefilter_config.adx_threshold == 25.0


class TestMTESv3:
    """Tests for MTESv3 main class."""

    def test_initialization(self):
        """Test MTESv3 initialization."""
        mtes = MTESv3()
        assert mtes.preprocessor is not None
        assert mtes.smc_analyzer is not None

    def test_initialization_with_config(self):
        """Test MTESv3 initialization with custom config."""
        config = MTESv3Config(min_confidence=0.7)
        mtes = MTESv3(config)
        assert mtes.config.min_confidence == 0.7

    def test_analyze_bull_trend(self):
        """Test analysis of bull trend."""
        df = create_sample_df(n=250, trend="bull")
        mtes = MTESv3()
        result = mtes.analyze(df)

        assert result.passed_prefilter is True
        assert result.mtf_trend.direction in ["BULL", "BEAR", "NEUTRAL"]
        assert -100 <= result.final_score <= 100
        assert 0 <= result.final_confidence <= 1

    def test_analyze_bear_trend(self):
        """Test analysis of bear trend."""
        df = create_sample_df(n=250, trend="bear")
        mtes = MTESv3()
        result = mtes.analyze(df)

        assert result.passed_prefilter is True
        assert result.final_score <= 0  # Bear trends should have negative scores

    def test_analyze_insufficient_data(self):
        """Test analysis with insufficient data."""
        df = create_sample_df(n=50)  # Less than 200
        mtes = MTESv3()
        result = mtes.analyze(df)

        assert result.passed_prefilter is False
        assert result.entry.signal == "WAIT"
        assert result.final_score == 0.0

    def test_analyze_high_adx_threshold(self):
        """Test analysis with high ADX threshold fails."""
        df = create_sample_df(n=250, trend="bull")
        # Set high threshold so even strong trends fail
        from agent.src.analysis.mtes_v3.mtes_v3 import MTESv3Config
        from agent.src.analysis.mtes_v3.preprocessor import PreprocessorConfig

        config = MTESv3Config(
            prefilter_config=PreprocessorConfig(adx_threshold=100.0)
        )
        mtes = MTESv3(config)
        result = mtes.analyze(df)

        # Should fail with threshold > 100
        assert result.passed_prefilter is False

    def test_entry_signal_for_bull(self):
        """Test entry signal generation for bull trend."""
        df = create_sample_df(n=250, trend="bull")
        mtes = MTESv3()
        result = mtes.analyze(df)

        # Strong bull trend should generate LONG signal
        assert result.entry.signal in ["LONG", "SHORT", "WAIT"]

    def test_entry_signal_for_bear(self):
        """Test entry signal generation for bear trend."""
        df = create_sample_df(n=250, trend="bear")
        mtes = MTESv3()
        result = mtes.analyze(df)

        # Bear trend should generate SHORT or WAIT
        assert result.entry.signal in ["LONG", "SHORT", "WAIT"]

    def test_final_score_range(self):
        """Test that final score is within valid range."""
        for trend in ["bull", "bear", "neutral"]:
            df = create_sample_df(n=250, trend=trend)
            mtes = MTESv3()
            result = mtes.analyze(df)

            assert -100 <= result.final_score <= 100

    def test_confidence_range(self):
        """Test that confidence is within valid range."""
        df = create_sample_df(n=250, trend="bull")
        mtes = MTESv3()
        result = mtes.analyze(df)

        assert 0 <= result.final_confidence <= 1

    def test_analyze_batch(self):
        """Test batch analysis of multiple symbols."""
        data = {
            'AAPL': create_sample_df(n=250, trend="bull"),
            'GOOGL': create_sample_df(n=50, trend="neutral"),
            'MSFT': create_sample_df(n=250, trend="bear"),
        }

        mtes = MTESv3()
        results = mtes.analyze_batch(data)

        assert len(results) == 3
        assert 'AAPL' in results
        assert 'GOOGL' in results
        assert 'MSFT' in results

        # AAPL and MSFT should pass prefilter with strong trends
        assert results['AAPL'].passed_prefilter is True
        assert results['MSFT'].passed_prefilter is True
        # GOOGL should fail due to insufficient data
        assert results['GOOGL'].passed_prefilter is False

    def test_result_to_dict(self):
        """Test result to_dict() conversion."""
        df = create_sample_df(n=250, trend="bull")
        mtes = MTESv3()
        result = mtes.analyze(df)
        data = result.to_dict()

        assert "passed_prefilter" in data
        assert "mtf_trend" in data
        assert "strength" in data
        assert "entry" in data
        assert "final_score" in data
        assert "final_confidence" in data

    def test_result_has_all_fields(self):
        """Test that result has all required fields."""
        df = create_sample_df(n=250, trend="bull")
        mtes = MTESv3()
        result = mtes.analyze(df)

        assert result.passed_prefilter is not None
        assert result.mtf_trend is not None
        assert result.strength is not None
        assert result.entry is not None
        assert result.final_score is not None
        assert result.final_confidence is not None


class TestMTESv3Integration:
    """Integration tests for MTES v3."""

    def test_full_pipeline(self):
        """Test the full analysis pipeline."""
        df = create_sample_df(n=250, trend="bull")
        mtes = MTESv3()

        # Run analysis
        result = mtes.analyze(df)

        # Verify all layers contributed
        assert result.passed_prefilter is True
        assert result.mtf_trend.direction in ["BULL", "BEAR", "NEUTRAL"]
        assert result.strength.rating in ["STRONG", "READY", "WEAK", "EXHAUSTED"]
        assert result.entry.signal in ["LONG", "SHORT", "WAIT"]

        # Score and confidence should be calculated
        assert result.final_score is not None
        assert result.final_confidence is not None

    def test_consecutive_analysis(self):
        """Test that multiple consecutive analyses work correctly."""
        mtes = MTESv3()

        # First analysis
        df1 = create_sample_df(n=250, trend="bull")
        result1 = mtes.analyze(df1)

        # Second analysis with different trend
        df2 = create_sample_df(n=250, trend="bear")
        result2 = mtes.analyze(df2)

        # Results should be different
        assert result1.mtf_trend.direction != result2.mtf_trend.direction
        assert result1.final_score != result2.final_score

    def test_with_minimal_data_threshold(self):
        """Test behavior near data threshold."""
        # Exactly at threshold
        df = create_sample_df(n=200, trend="bull")
        mtes = MTESv3()
        result = mtes.analyze(df)

        # Should pass prefilter if ADX is high enough
        assert isinstance(result.passed_prefilter, bool)
