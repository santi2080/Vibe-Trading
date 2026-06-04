"""Tests for Enhanced SuperTrend strategy adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.enhanced_supertrend import TrendSignal
from src.strategies.trend.enhanced_supertrend import EnhancedSuperTrendStrategy


def make_ohlcv(length: int = 50) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series([100 + i for i in range(length)], index=index, dtype="float64")
    return pd.DataFrame(
        {"open": close - 0.2, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1000.0},
        index=index,
    )


class FakeIndicator:
    def __init__(self, signal: TrendSignal) -> None:
        self.signal = signal
        self.calls = []

    def get_signal(self, df: pd.DataFrame) -> TrendSignal:
        self.calls.append(df)
        return self.signal


def test_enhanced_supertrend_maps_bull_signal() -> None:
    signal = TrendSignal("上涨", 1, 0.75, adx=32.0, supertrend_direction=1, trend_magic_direction=1, bars_since_flip=4)
    indicator = FakeIndicator(signal)
    strategy = EnhancedSuperTrendStrategy(indicator=indicator)
    df = make_ohlcv()

    result = strategy.analyze(df)

    assert indicator.calls == [df]
    assert result.status == "VALID"
    assert result.direction == "BULL"
    assert result.confidence == pytest.approx(0.75)
    assert result.signed_score == pytest.approx(75.0)
    assert result.strength_rating == "STRONG"
    assert result.readiness == "READY"
    assert result.regime == "TRENDING"
    assert result.metadata["source"] == "enhanced_supertrend"
    assert result.metadata["trend"] == "上涨"
    assert result.metadata["adx"] == pytest.approx(32.0)
    assert result.metadata["supertrend_direction"] == 1
    assert result.metadata["trend_magic_direction"] == 1
    assert result.metadata["bars_since_flip"] == 4


def test_enhanced_supertrend_maps_bear_signal() -> None:
    signal = TrendSignal("下跌", -1, 0.6, adx=26.0, supertrend_direction=-1, trend_magic_direction=-1, bars_since_flip=3)
    strategy = EnhancedSuperTrendStrategy(indicator=FakeIndicator(signal))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "VALID"
    assert result.direction == "BEAR"
    assert result.signed_score == pytest.approx(-60.0)
    assert result.strength_rating == "READY"
    assert result.readiness == "READY"


def test_enhanced_supertrend_maps_choppy_to_no_signal() -> None:
    signal = TrendSignal("震荡", 0, 0.8, adx=15.0, supertrend_direction=0, trend_magic_direction=1, bars_since_flip=1)
    strategy = EnhancedSuperTrendStrategy(indicator=FakeIndicator(signal))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "NO_SIGNAL"
    assert result.direction == "NEUTRAL"
    assert result.signed_score == pytest.approx(0.0)
    assert result.strength_rating == "WEAK"
    assert result.readiness == "NOT_READY"
    assert result.regime == "CHOPPY"


def test_enhanced_supertrend_low_confidence_directional_is_filtered() -> None:
    signal = TrendSignal("上涨", 1, 0.2, adx=30.0, supertrend_direction=1, trend_magic_direction=1, bars_since_flip=2)
    strategy = EnhancedSuperTrendStrategy(indicator=FakeIndicator(signal))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "FILTERED"
    assert result.direction == "BULL"
    assert result.strength_rating == "WEAK"
    assert "low confidence filtered" in result.warnings
