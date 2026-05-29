"""Contract tests for the MTES backtest strategy wrapper and registration."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from backtest.strategies import StrategyRegistry, StrategyType
from backtest.strategies.major_trend import MajorTrendEvaluationStrategy
from src.analysis.major_trend_evaluator import MajorTrendResult, TrendState

EXPECTED_MTES_COLUMNS = {
    "mtes_score",
    "mtes_state",
    "mtes_direction",
    "mtes_regime",
    "mtes_confidence",
    "mtes_direction_score",
    "mtes_strength_score",
    "mtes_structure_score",
    "mtes_momentum_score",
    "mtes_volatility_regime_score",
    "mtes_mtf_score",
}

FORBIDDEN_EXECUTION_COLUMNS = {
    "position_size",
    "order_quantity",
    "portfolio_allocation",
    "live_execution",
}


def make_ohlcv(length: int = 64, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    """Create deterministic OHLCV data for strategy tests."""
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series([start + i * step for i in range(length)], index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def make_result(
    *,
    trend_state: str = TrendState.BULL_CONFIRMED.value,
    direction: str = "BULL",
    trend_score: float = 82.0,
    regime: str = "trend_friendly",
) -> MajorTrendResult:
    """Create a deterministic MTES result for mocking the evaluator."""
    sub_scores = {
        "direction": 14.0,
        "strength": 13.0,
        "structure": 24.0,
        "momentum": 12.0,
        "volatility_regime": 11.0,
        "mtf": 8.0,
    }
    raw_scores = {
        "direction": 93.0,
        "strength": 87.0,
        "structure": 96.0,
        "momentum": 80.0,
        "volatility_regime": 73.0,
        "mtf": 66.0,
    }
    weights = {
        "direction": 15.0,
        "strength": 15.0,
        "structure": 25.0,
        "momentum": 15.0,
        "volatility_regime": 15.0,
        "mtf": 15.0,
    }
    return MajorTrendResult(
        asset_class="stock",
        trend_score=trend_score,
        trend_state=trend_state,
        direction=direction,
        confidence=round(trend_score / 100, 3),
        regime=regime,
        sub_scores=sub_scores,
        raw_scores=raw_scores,
        weights=weights,
        top_drivers=[
            {"name": "structure", "sub_score": sub_scores["structure"], "raw_score": raw_scores["structure"]},
            {"name": "direction", "sub_score": sub_scores["direction"], "raw_score": raw_scores["direction"]},
            {"name": "strength", "sub_score": sub_scores["strength"], "raw_score": raw_scores["strength"]},
        ],
        regime_flags=["trend_friendly"],
        explanation=f"{trend_state} with {trend_score:.1f}/100 quality",
        metadata={"status": "scored"},
    )


def test_major_trend_evaluation_strategy_is_registered_under_stable_name() -> None:
    """The MTES wrapper must be discoverable through the existing registry."""
    strategy = StrategyRegistry.get("major_trend_evaluation")

    assert isinstance(strategy, MajorTrendEvaluationStrategy)
    assert "major_trend_evaluation" in StrategyRegistry.list_strategies(StrategyType.TREND)
    assert strategy.get_metadata().name == "major_trend_evaluation"
    assert strategy.get_metadata().type is StrategyType.TREND


@pytest.mark.parametrize(
    ("trend_state", "expected_signal"),
    [
        (TrendState.BULL_CONFIRMED.value, 1),
        (TrendState.BULL_STRONG.value, 1),
        (TrendState.BULL_EARLY.value, 0),
        (TrendState.NEUTRAL_CHOPPY.value, 0),
        (TrendState.BEAR_EARLY.value, 0),
        (TrendState.BEAR_CONFIRMED.value, -1),
        (TrendState.BEAR_STRONG.value, -1),
    ],
)
def test_major_trend_evaluation_signal_mapping_from_states(
    trend_state: str,
    expected_signal: int,
) -> None:
    """Confirmed/strong bull and bear states map to directional evaluation signals only."""
    strategy = MajorTrendEvaluationStrategy()
    df = make_ohlcv(length=8)
    indicators = {
        "mtes_state": pd.Series([trend_state] * len(df), index=df.index),
        "mtes_direction": pd.Series(["BULL"] * len(df), index=df.index),
    }

    signals = strategy._generate_signals(df, indicators)

    assert signals.tolist() == [expected_signal] * len(df)


def test_major_trend_evaluation_generate_emits_mtes_columns_and_stays_evaluation_only() -> None:
    """The strategy should surface MTES fields without execution or sizing outputs."""
    strategy = MajorTrendEvaluationStrategy()
    df = make_ohlcv(length=64)
    mocked_result = make_result()

    with patch.object(strategy.evaluator, "evaluate", return_value=mocked_result) as evaluate_mock:
        output = strategy.generate(df)

    assert evaluate_mock.called
    assert output["signal_name"].eq("major_trend_evaluation").all()
    assert output["signal"].tolist() == [1] * len(output)
    assert EXPECTED_MTES_COLUMNS <= set(output.columns)
    assert FORBIDDEN_EXECUTION_COLUMNS.isdisjoint(output.columns)
    assert output["mtes_score"].iloc[0] == pytest.approx(mocked_result.trend_score)
    assert output["mtes_state"].iloc[0] == mocked_result.trend_state
    assert output["mtes_direction"].iloc[0] == mocked_result.direction
    assert output["mtes_regime"].iloc[0] == mocked_result.regime
    assert output["mtes_confidence"].iloc[0] == pytest.approx(mocked_result.confidence)
