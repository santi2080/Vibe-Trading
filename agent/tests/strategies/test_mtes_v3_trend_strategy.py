"""Tests for MTES v3 trend strategy adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.mtes_v3 import EntrySignal, MTESv3Result, StrengthRatingResult, TrendBias
from src.strategies.trend.mtes_v3 import MTESv3TrendStrategy


def make_ohlcv(length: int = 220) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series([100 + i for i in range(length)], index=index, dtype="float64")
    return pd.DataFrame(
        {"open": close - 0.2, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1000.0},
        index=index,
    )


def make_result(
    *,
    passed_prefilter: bool = True,
    direction: str = "BULL",
    strength: str = "READY",
    final_score: float = 65.0,
    final_confidence: float = 0.72,
) -> MTESv3Result:
    return MTESv3Result(
        passed_prefilter=passed_prefilter,
        mtf_trend=TrendBias(direction=direction, confidence=0.76, signals={"ichimoku": "bull"}),
        strength=StrengthRatingResult(rating=strength, adx_value=28.0, divergence=False, regime="TRENDING"),
        entry=EntrySignal(signal="LONG", entry_price=101.0, stop_loss=98.0, reason="RSI recovery"),
        final_score=final_score,
        final_confidence=final_confidence,
    )


class FakeMTESv3:
    def __init__(self, result: MTESv3Result) -> None:
        self.result = result
        self.calls = []

    def analyze(self, df: pd.DataFrame) -> MTESv3Result:
        self.calls.append(df)
        return self.result


def test_mtes_v3_adapter_calls_evaluator_and_maps_core_fields() -> None:
    evaluator = FakeMTESv3(make_result())
    strategy = MTESv3TrendStrategy(evaluator=evaluator)
    df = make_ohlcv()

    result = strategy.analyze(df)

    assert evaluator.calls == [df]
    assert result.status == "VALID"
    assert result.direction == "BULL"
    assert result.confidence == pytest.approx(0.72)
    assert result.signed_score == pytest.approx(65.0)
    assert result.passed_prefilter is True
    assert result.strength_rating == "READY"
    assert result.readiness == "READY"
    assert result.regime == "TRENDING"
    assert result.components["final_score"] == pytest.approx(65.0)
    assert result.components["trend_confidence"] == pytest.approx(76.0)
    assert result.components["adx"] == pytest.approx(28.0)
    assert result.metadata["source"] == "mtes_v3"
    assert result.metadata["entry"]["signal"] == "LONG"
    assert not hasattr(result, "entry")


def test_mtes_v3_prefilter_failure_is_no_signal_not_filtered() -> None:
    strategy = MTESv3TrendStrategy(evaluator=FakeMTESv3(make_result(passed_prefilter=False, direction="NEUTRAL", final_score=0.0, final_confidence=0.0)))

    result = strategy.analyze(make_ohlcv())

    assert result.status == "NO_SIGNAL"
    assert result.direction == "NEUTRAL"
    assert result.readiness == "NOT_READY"
    assert result.passed_prefilter is False


@pytest.mark.parametrize(
    ("strength", "expected_readiness"),
    [
        ("STRONG", "READY"),
        ("READY", "READY"),
        ("EXHAUSTED", "EXHAUSTED"),
        ("WEAK", "NOT_READY"),
    ],
)
def test_mtes_v3_strength_maps_to_readiness(strength: str, expected_readiness: str) -> None:
    strategy = MTESv3TrendStrategy(evaluator=FakeMTESv3(make_result(strength=strength)))

    result = strategy.analyze(make_ohlcv())

    assert result.strength_rating == strength
    assert result.readiness == expected_readiness
