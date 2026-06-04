"""Tests for MTES v2 trend strategy adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.major_trend_evaluator import MajorTrendResult, TrendState
from src.strategies.trend.mtes_v2 import MTESv2TrendStrategy, MTESv2TrendStrategyConfig


def make_ohlcv(length: int = 220) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series([100 + i for i in range(length)], index=index, dtype="float64")
    return pd.DataFrame(
        {"open": close - 0.2, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1000.0},
        index=index,
    )


def make_result(
    *,
    direction: str = "BULL",
    trend_score: float = 82.0,
    direction_signal: float = 82.0,
    confidence: float = 0.82,
) -> MajorTrendResult:
    sub_scores = {"direction": 14.0, "strength": 13.0, "structure": 24.0, "momentum": 12.0, "volatility_regime": 11.0, "mtf": 8.0}
    raw_scores = {"direction": 93.0, "strength": 87.0, "structure": 96.0, "momentum": 80.0, "volatility_regime": 73.0, "mtf": 66.0}
    weights = {"direction": 15.0, "strength": 15.0, "structure": 25.0, "momentum": 15.0, "volatility_regime": 15.0, "mtf": 15.0}
    return MajorTrendResult(
        asset_class="stock",
        trend_score=trend_score,
        trend_state=TrendState.BULL_CONFIRMED.value if direction == "BULL" else TrendState.BEAR_CONFIRMED.value,
        direction=direction,
        confidence=confidence,
        regime="trend_friendly",
        sub_scores=sub_scores,
        raw_scores=raw_scores,
        weights=weights,
        top_drivers=[{"name": "structure", "sub_score": 24.0, "raw_score": 96.0}],
        regime_flags=["trend_friendly"],
        explanation="mocked result",
        metadata={"status": "scored"},
        direction_signal=direction_signal,
        direction_confidence=confidence,
        strength_score=75.0,
        strength_components={"strength": 75.0, "structure": 80.0},
        use_v2_scoring=True,
    )


class FakeEvaluator:
    def __init__(self, result: MajorTrendResult) -> None:
        self.result = result
        self.calls = []

    def evaluate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def test_mtes_v2_adapter_calls_evaluator_with_expected_arguments() -> None:
    evaluator = FakeEvaluator(make_result())
    strategy = MTESv2TrendStrategy(config=MTESv2TrendStrategyConfig(asset_class="futures"), evaluator=evaluator)
    df = make_ohlcv()

    result = strategy.analyze(df)

    assert result.status == "VALID"
    assert evaluator.calls
    args, kwargs = evaluator.calls[0]
    assert args[0] is df
    assert kwargs["asset_class"] == "futures"
    assert kwargs["base_timeframe"] == "1d"
    assert kwargs["higher_timeframe_name"] == "1w"


def test_mtes_v2_adapter_maps_core_fields_and_metadata() -> None:
    strategy = MTESv2TrendStrategy(evaluator=FakeEvaluator(make_result(direction_signal=88.0)))

    result = strategy.analyze(make_ohlcv())

    assert result.direction == "BULL"
    assert result.confidence == pytest.approx(0.82)
    assert result.signed_score == pytest.approx(88.0)
    assert result.strength_rating == "STRONG"
    assert result.readiness == "READY"
    assert result.regime == "trend_friendly"
    assert result.components["direction"] == pytest.approx(88.0)
    assert result.components["strength"] == pytest.approx(75.0)
    assert result.metadata["source"] == "mtes_v2"
    assert result.metadata["trend_state"] == TrendState.BULL_CONFIRMED.value
    assert result.metadata["sub_scores"]
    assert result.metadata["raw_scores"]
    assert result.metadata["weights"]
    assert result.metadata["top_drivers"]
    assert result.metadata["regime_flags"] == ["trend_friendly"]
    assert result.metadata["use_v2_scoring"] is True


def test_mtes_v2_signed_score_falls_back_to_trend_score() -> None:
    strategy = MTESv2TrendStrategy(evaluator=FakeEvaluator(make_result(direction_signal=0.0, trend_score=-55.0, direction="BEAR", confidence=0.6)))

    result = strategy.analyze(make_ohlcv())

    assert result.direction == "BEAR"
    assert result.signed_score == pytest.approx(-55.0)
    assert result.strength_rating == "READY"
    assert result.readiness == "READY"


def test_mtes_v2_weak_result_not_ready() -> None:
    strategy = MTESv2TrendStrategy(evaluator=FakeEvaluator(make_result(direction_signal=20.0, confidence=0.45)))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "VALID"
    assert result.strength_rating == "WEAK"
    assert result.readiness == "NOT_READY"
