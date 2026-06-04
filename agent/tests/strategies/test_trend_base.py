"""Tests for canonical trend strategy base contract."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.strategies.trend.base import TrendResult, TrendStrategyBase, clamp_confidence, clamp_signed_score


def make_ohlcv(length: int = 20) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series(range(100, 100 + length), index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        },
        index=index,
    )


class DummyTrendStrategy(TrendStrategyBase):
    name = "dummy_trend"

    def __init__(self, result: TrendResult | None = None, raises: bool = False) -> None:
        super().__init__()
        self.result = result or TrendResult(direction="BULL", confidence=0.8, signed_score=70, readiness="READY")
        self.raises = raises

    def _analyze_raw(self, df: pd.DataFrame) -> Any:
        if self.raises:
            raise RuntimeError("boom")
        return self.result

    def _normalize(self, raw: Any, df: pd.DataFrame) -> TrendResult:
        return raw

    def get_required_bars(self) -> int:
        return 10


def test_trend_result_actionable_requires_valid_directional_ready() -> None:
    assert TrendResult(direction="BULL", confidence=0.8, signed_score=80, readiness="READY").is_actionable_trend
    assert not TrendResult(direction="NEUTRAL", confidence=0.8, signed_score=0, readiness="READY").is_actionable_trend
    assert not TrendResult(direction="BULL", confidence=0.8, signed_score=80, readiness="NOT_READY").is_actionable_trend
    assert not TrendResult(direction="BULL", confidence=0.8, signed_score=80, status="FILTERED", readiness="READY").is_actionable_trend


def test_validate_missing_columns_returns_invalid_result() -> None:
    result = DummyTrendStrategy().analyze(make_ohlcv().drop(columns=["low"]))

    assert result.status == "INVALID"
    assert result.direction == "NEUTRAL"
    assert "missing columns" in result.explanation


def test_validate_empty_dataframe_returns_invalid_result() -> None:
    result = DummyTrendStrategy().analyze(make_ohlcv().iloc[0:0])

    assert result.status == "INVALID"
    assert result.explanation == "empty dataframe"


def test_validate_insufficient_bars_returns_invalid_result() -> None:
    result = DummyTrendStrategy().analyze(make_ohlcv(length=5))

    assert result.status == "INVALID"
    assert "insufficient bars" in result.explanation


def test_low_confidence_directional_result_is_filtered() -> None:
    strategy = DummyTrendStrategy(TrendResult(direction="BULL", confidence=0.2, signed_score=50, readiness="READY"))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "FILTERED"
    assert result.direction == "BULL"
    assert "low confidence filtered" in result.warnings


def test_valid_neutral_result_becomes_no_signal() -> None:
    strategy = DummyTrendStrategy(TrendResult(direction="NEUTRAL", confidence=0.8, signed_score=0, readiness="NOT_READY"))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "NO_SIGNAL"
    assert result.direction == "NEUTRAL"

def test_subclass_exception_returns_invalid_result() -> None:
    result = DummyTrendStrategy(raises=True).analyze(make_ohlcv())

    assert result.status == "INVALID"
    assert result.direction == "NEUTRAL"
    assert result.metadata["strategy"] == "dummy_trend"
    assert "boom" in result.warnings[0]


def test_clamp_helpers_treat_non_finite_values_as_zero() -> None:
    assert clamp_confidence(float("nan")) == 0.0
    assert clamp_confidence(float("inf")) == 0.0
    assert clamp_confidence(float("-inf")) == 0.0
    assert clamp_signed_score(float("nan")) == 0.0
    assert clamp_signed_score(float("inf")) == 0.0
    assert clamp_signed_score(float("-inf")) == 0.0
