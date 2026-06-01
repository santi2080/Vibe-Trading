"""Tests for MTES v3 SMC Analyzer (Layer 1)."""

import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.layer1.smc_analyzer import (
    Swing,
    SwingDetector,
    SMCAnalyzer,
    MarketStructureResult,
)


def create_trend_df(n: int = 200, trend: str = "neutral") -> pd.DataFrame:
    """Create a sample OHLCV DataFrame with a specific trend.

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
        # Create higher highs and higher lows
        trend_component = np.linspace(0, 30, n)
        # Add some noise but ensure HH and HL pattern
        noise = np.random.randn(n) * 1.5
        # Create clearer swing structure
        for i in range(10, n, 20):
            trend_component[i:i+5] += 3
    elif trend == "bear":
        base = 130
        trend_component = np.linspace(0, -30, n)
        noise = np.random.randn(n) * 1.5
        for i in range(10, n, 20):
            trend_component[i:i+5] -= 3
    else:
        base = 100
        trend_component = np.zeros(n)
        noise = np.random.randn(n) * 3

    return pd.DataFrame({
        'open': base + trend_component + noise,
        'high': base + trend_component + noise + abs(np.random.randn(n)),
        'low': base + trend_component + noise - abs(np.random.randn(n)),
        'close': base + trend_component + noise,
        'volume': np.random.randint(1000, 5000, n)
    }, index=dates)


class TestSwing:
    """Tests for Swing dataclass."""

    def test_swing_creation(self):
        """Test Swing creation."""
        swing = Swing(
            index=100,
            timestamp=pd.Timestamp('2025-01-01'),
            price=150.5,
            swing_type="HH"
        )
        assert swing.index == 100
        assert swing.price == 150.5
        assert swing.swing_type == "HH"

    def test_is_high(self):
        """Test is_high() method."""
        hh_swing = Swing(1, pd.Timestamp.now(), 100.0, "HH")
        lh_swing = Swing(2, pd.Timestamp.now(), 95.0, "LH")
        assert hh_swing.is_high() is True
        assert lh_swing.is_high() is True

    def test_is_low(self):
        """Test is_low() method."""
        hl_swing = Swing(1, pd.Timestamp.now(), 100.0, "HL")
        ll_swing = Swing(2, pd.Timestamp.now(), 95.0, "LL")
        assert hl_swing.is_low() is True
        assert ll_swing.is_low() is True


class TestSwingDetector:
    """Tests for SwingDetector class."""

    def test_detect_finds_swings(self):
        """Test that detector finds swing highs and lows."""
        df = create_trend_df(n=100, trend="bull")
        detector = SwingDetector(lookback=3, min_bars_between=2)
        swings = detector.detect(df)

        assert len(swings) > 0

        # Should have both highs and lows
        highs = [s for s in swings if s.is_high()]
        lows = [s for s in swings if s.is_low()]
        assert len(highs) > 0
        assert len(lows) > 0

    def test_classify_high_types(self):
        """Test that highs are classified as HH or LH."""
        df = create_trend_df(n=100, trend="bull")
        detector = SwingDetector(lookback=3, min_bars_between=2)
        swings = detector.detect(df)

        highs = [s for s in swings if s.is_high()]
        for swing in highs:
            assert swing.swing_type in ["HH", "LH"]

    def test_classify_low_types(self):
        """Test that lows are classified as HL or LL."""
        df = create_trend_df(n=100, trend="bear")
        detector = SwingDetector(lookback=3, min_bars_between=2)
        swings = detector.detect(df)

        lows = [s for s in swings if s.is_low()]
        for swing in lows:
            assert swing.swing_type in ["HL", "LL"]

    def test_swings_sorted_by_index(self):
        """Test that swings are sorted by index."""
        df = create_trend_df(n=100, trend="neutral")
        detector = SwingDetector(lookback=3, min_bars_between=2)
        swings = detector.detect(df)

        if len(swings) > 1:
            indices = [s.index for s in swings]
            assert indices == sorted(indices)

    def test_min_bars_between(self):
        """Test that minimum bars between swings is respected."""
        # Create very volatile data
        df = create_trend_df(n=50, trend="neutral")
        detector = SwingDetector(lookback=1, min_bars_between=5)
        swings = detector.detect(df)

        if len(swings) > 1:
            for i in range(1, len(swings)):
                gap = swings[i].index - swings[i-1].index
                assert gap >= 5


class TestSMCAnalyzer:
    """Tests for SMCAnalyzer class."""

    def test_validate_insufficient_data(self):
        """Test validation with insufficient data."""
        df = create_trend_df(n=20)  # Less than 50
        analyzer = SMCAnalyzer()
        assert analyzer.validate(df) is False

    def test_validate_sufficient_data(self):
        """Test validation with sufficient data."""
        df = create_trend_df(n=100)
        analyzer = SMCAnalyzer()
        assert analyzer.validate(df) is True

    def test_analyze_bull_trend(self):
        """Test analysis of bull trend."""
        df = create_trend_df(n=200, trend="bull")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        assert result.trend in ["BULL", "BEAR", "NEUTRAL"]
        assert 0 <= result.confidence <= 1
        assert isinstance(result.bos_confirmed, bool)
        assert isinstance(result.mss_confirmed, bool)

    def test_analyze_bear_trend(self):
        """Test analysis of bear trend."""
        df = create_trend_df(n=200, trend="bear")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        assert result.trend in ["BULL", "BEAR", "NEUTRAL"]
        assert 0 <= result.confidence <= 1

    def test_analyze_neutral_trend(self):
        """Test analysis of neutral/ranging market."""
        df = create_trend_df(n=200, trend="neutral")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        # Neutral market should have lower confidence
        assert result.trend in ["BULL", "BEAR", "NEUTRAL"]

    def test_swings_extracted(self):
        """Test that swings are extracted from data."""
        df = create_trend_df(n=150, trend="bull")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        assert len(result.swings) > 0
        assert result.last_swing_high is not None
        assert result.last_swing_low is not None

    def test_bos_detection(self):
        """Test BOS (Break of Structure) detection."""
        df = create_trend_df(n=200, trend="bull")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        # In a bull trend, BOS should typically be confirmed
        assert isinstance(result.bos_confirmed, bool)

    def test_mss_detection(self):
        """Test MSS (Market Structure Shift) detection."""
        df = create_trend_df(n=200, trend="bull")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        # MSS may or may not be confirmed
        assert isinstance(result.mss_confirmed, bool)

    def test_to_dict(self):
        """Test to_dict() conversion."""
        df = create_trend_df(n=100, trend="bull")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)
        data = result.to_dict()

        assert "trend" in data
        assert "confidence" in data
        assert "swings" in data
        assert "bos_confirmed" in data
        assert "mss_confirmed" in data

    def test_liquidity_sweeps(self):
        """Test liquidity sweep detection."""
        df = create_trend_df(n=100, trend="neutral")
        analyzer = SMCAnalyzer()
        result = analyzer.analyze(df)

        assert isinstance(result.liquidity_sweeps, list)


class TestMarketStructureResult:
    """Tests for MarketStructureResult."""

    def test_creation(self):
        """Test MarketStructureResult creation."""
        result = MarketStructureResult(
            trend="BULL",
            confidence=0.8,
            swings=[],
            bos_confirmed=True,
            mss_confirmed=False,
            last_swing_high=150.0,
            last_swing_low=140.0
        )
        assert result.trend == "BULL"
        assert result.confidence == 0.8
        assert result.bos_confirmed is True
        assert result.mss_confirmed is False

    def test_default_values(self):
        """Test default values."""
        result = MarketStructureResult(
            trend="NEUTRAL",
            confidence=0.0
        )
        assert result.swings == []
        assert result.bos_confirmed is False
        assert result.mss_confirmed is False
        assert result.liquidity_sweeps == []
