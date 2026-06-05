"""Contract tests for the Major Trend Evaluation System evaluator."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.analysis.major_trend_evaluator import (
    ASSET_WEIGHT_PROFILES,
    BASE_WEIGHTS,
    DIRECTION_PERIODS,
    MajorTrendEvaluator,
    TrendState,
    classify_trend_state_v2,
    get_weight_profile,
)


EXPECTED_DIMENSIONS = {
    "direction",
    "strength",
    "structure",
    "momentum",
    "volatility_regime",
    "mtf",
}


def make_ohlcv(
    length: int = 320,
    start: float = 100.0,
    step: float = 1.0,
    noise: float = 0.0,
) -> pd.DataFrame:
    """Create deterministic OHLCV data for evaluator tests."""
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    trend = pd.Series([start + i * step for i in range(length)], index=index, dtype="float64")
    if noise:
        trend = trend + pd.Series([(-1) ** i * noise for i in range(length)], index=index)
    high = trend + 1.0
    low = trend - 1.0
    return pd.DataFrame(
        {
            "open": trend - 0.2,
            "high": high,
            "low": low,
            "close": trend,
            "volume": 1000.0,
        },
        index=index,
    )


def test_base_profile_uses_locked_structure_first_weights() -> None:
    """The base profile must expose the locked D-01/D-04 weights."""
    assert BASE_WEIGHTS == {
        "direction": 15,
        "strength": 15,
        "structure": 25,
        "momentum": 15,
        "volatility_regime": 15,
        "mtf": 15,
    }


def test_asset_profiles_are_composed_from_base_overrides_and_total_100() -> None:
    """Every supported profile is composed from BASE_WEIGHTS plus explicit overrides."""
    assert set(ASSET_WEIGHT_PROFILES) == {"stock", "etf", "futures", "crypto", "fx"}

    for asset_class, overrides in ASSET_WEIGHT_PROFILES.items():
        profile = get_weight_profile(asset_class)
        expected = BASE_WEIGHTS | overrides

        assert set(profile) == EXPECTED_DIMENSIONS
        assert profile == expected
        assert sum(profile.values()) == 100


def test_unsupported_asset_class_fails_clearly() -> None:
    """Unsupported asset classes fail with a clear validation error."""
    with pytest.raises(ValueError, match="unsupported asset class"):
        get_weight_profile("unknown")


def test_asset_class_specific_direction_periods_are_observable() -> None:
    """D-06 requires direction periods to vary by asset class."""
    periods_by_asset = {asset: DIRECTION_PERIODS[asset] for asset in ASSET_WEIGHT_PROFILES}

    assert set(periods_by_asset) == {"stock", "etf", "futures", "crypto", "fx"}
    assert len({tuple(periods.items()) for periods in periods_by_asset.values()}) > 1
    for periods in periods_by_asset.values():
        assert {"intermediate", "long", "slope", "return"} <= set(periods)
        assert periods["long"] >= periods["intermediate"]
        assert periods["return"] >= periods["intermediate"]


def test_strong_bull_fixture_scores_and_classifies() -> None:
    """A sufficient bullish fixture receives six weighted dimensions and a bull state."""
    result = MajorTrendEvaluator().evaluate(make_ohlcv(step=1.0), asset_class="futures")

    assert result.direction == "BULL"
    assert result.trend_state in {
        TrendState.BULL_CONFIRMED.value,
        TrendState.BULL_STRONG.value,
    }
    # V2: trend_score 范围 -100 ~ +100
    assert -100 <= result.trend_score <= 100
    assert result.trend_score >= 0  # BULL 方向时为正
    assert set(result.sub_scores) == EXPECTED_DIMENSIONS
    # V2: sub_scores 总和不再等于 trend_score（因为 V2 使用新公式）
    # 只验证 sub_scores 存在且值在 0-100 范围内
    assert all(0 <= v <= 100 for v in result.sub_scores.values())
    assert len(result.top_drivers) >= 3
    assert result.to_dict()["trend_score"] == result.trend_score
    # V2 新增字段验证
    assert hasattr(result, "direction_signal")
    assert hasattr(result, "direction_confidence")
    assert hasattr(result, "strength_score")
    assert 0 <= result.direction_signal <= 100  # BULL 方向时为正
    assert 0 <= result.direction_confidence <= 1
    assert 0 <= result.strength_score <= 100

def test_v2_strong_state_requires_strength_confirmation() -> None:
    """V2 STRONG classification requires both signed score and strength confirmation."""
    assert (
        classify_trend_state_v2(61.0, "BULL", strength_score=49.0)
        == TrendState.BULL_CONFIRMED.value
    )
    assert (
        classify_trend_state_v2(61.0, "BULL", strength_score=50.0)
        == TrendState.BULL_STRONG.value
    )
    assert (
        classify_trend_state_v2(-61.0, "BEAR", strength_score=49.0)
        == TrendState.BEAR_CONFIRMED.value
    )
    assert (
        classify_trend_state_v2(-61.0, "BEAR", strength_score=50.0)
        == TrendState.BEAR_STRONG.value
    )


def test_insufficient_long_horizon_data_returns_no_score_metadata() -> None:
    """Frames shorter than resolved long-horizon direction data return no score."""
    required = DIRECTION_PERIODS["stock"]["long"]
    result = MajorTrendEvaluator().evaluate(make_ohlcv(length=required - 1), asset_class="stock")

    assert result.trend_state == TrendState.NEUTRAL_CHOPPY.value
    assert result.regime_flags == ["insufficient_data"]
    assert result.trend_score == 0.0
    assert result.metadata["status"] == "no_score"
    assert result.metadata["required_bars"] == required


def test_missing_volume_does_not_crash() -> None:
    """Missing optional volume degrades only its own metadata and does not crash."""
    df = make_ohlcv().drop(columns=["volume"])

    result = MajorTrendEvaluator().evaluate(df, asset_class="fx")

    assert result.asset_class == "fx"
    # V2: trend_score 范围 -100 ~ +100
    assert -100 <= result.trend_score <= 100
    assert result.metadata["input"].get("missing_optional") == ["volume"]


def test_cross_section_context_adds_relative_momentum_metadata() -> None:
    """Cross-sectional context annotates relative momentum while absolute-only still works."""
    df = make_ohlcv(step=0.45)
    single_asset = MajorTrendEvaluator().evaluate(df, asset_class="etf")
    with_context = MajorTrendEvaluator().evaluate(
        df,
        asset_class="etf",
        cross_section_context={
            "asset_id": "SPY",
            "returns_252": {"SPY": 0.25, "QQQ": 0.35, "TLT": -0.08, "GLD": 0.12},
        },
    )

    assert single_asset.metadata["momentum"]["relative_status"] == "not_provided"
    assert "relative_rank" not in single_asset.metadata["momentum"]
    assert with_context.metadata["momentum"]["relative_status"] == "applied"
    assert 0 <= with_context.metadata["momentum"]["relative_rank"] <= 1
    assert with_context.raw_scores["momentum"] != single_asset.raw_scores["momentum"]


def test_structure_metadata_reports_breakout_and_swing_evidence() -> None:
    """Structure exposes both breakout/range and swing evidence."""
    result = MajorTrendEvaluator().evaluate(make_ohlcv(step=0.7), asset_class="stock")

    structure_meta = result.metadata["structure"]
    assert "range_position" in structure_meta
    assert "breakout_state" in structure_meta
    assert "swing_structure" in structure_meta


def test_choppy_regime_scores_lower_than_smooth_directional_regime() -> None:
    """Low efficiency/chop is the primary regime penalty."""
    smooth = MajorTrendEvaluator().evaluate(make_ohlcv(step=0.5, noise=0.0), asset_class="futures")
    choppy = MajorTrendEvaluator().evaluate(make_ohlcv(step=0.05, noise=12.0), asset_class="futures")

    assert choppy.raw_scores["volatility_regime"] < smooth.raw_scores["volatility_regime"]
    assert "choppy" in choppy.regime_flags
    assert choppy.metadata["volatility_regime"]["trend_efficiency"] < smooth.metadata["volatility_regime"]["trend_efficiency"]


def test_extreme_volatility_is_flagged_as_secondary_metadata() -> None:
    """ATR/HV extremes appear as flags without replacing efficiency/chop logic."""
    result = MajorTrendEvaluator().evaluate(make_ohlcv(step=0.25, noise=25.0), asset_class="crypto")

    assert any(flag in result.regime_flags for flag in {"extreme_volatility", "high_atr"})
    assert "atr_pct" in result.metadata["volatility_regime"]
    assert "historical_volatility" in result.metadata["volatility_regime"]


def test_mtf_alignment_uses_completed_higher_timeframe_bars() -> None:
    """MTF scoring must route through MTFAligner with a completed-bar lag."""
    base = make_ohlcv(length=260, step=0.5)
    higher = make_ohlcv(length=80, step=2.0).resample("W").last().dropna()

    result = MajorTrendEvaluator().evaluate(
        base,
        asset_class="futures",
        higher_timeframe=higher,
        base_timeframe="1d",
        higher_timeframe_name="1w",
    )

    assert result.metadata["mtf"]["method"] == "backward_lag"
    assert result.metadata["mtf"]["aligner"] == "MTFAligner"
    assert result.metadata["mtf"]["lag_bars"] == 1
    assert result.raw_scores["mtf"] in {25.0, 90.0}


def test_mtf_conflict_reduces_mtf_only_without_hard_veto() -> None:
    """Base/higher conflicts reduce MTF score and surface metadata without zeroing total."""
    base = make_ohlcv(length=320, step=0.5)
    higher = make_ohlcv(length=100, start=250, step=-1.5).resample("W").last().dropna()

    result = MajorTrendEvaluator().evaluate(
        base,
        asset_class="futures",
        higher_timeframe=higher,
        base_timeframe="1d",
        higher_timeframe_name="1w",
    )

    assert result.direction == "BULL"
    assert result.raw_scores["mtf"] == 25.0
    assert result.sub_scores["mtf"] < result.weights["mtf"] * 0.5
    assert result.trend_score > 0.0
    assert result.metadata["mtf"]["timeframe_conflict"] is True
    assert "timeframe_conflict" in result.regime_flags or any(
        driver.get("name") == "timeframe_conflict" for driver in result.top_drivers
    )


def test_watchlist_contract_fields_remain_machine_readable(tmp_path: Path) -> None:
    """The evaluator dict exposes the watchlist-compatible machine contract."""
    result = MajorTrendEvaluator().evaluate(make_ohlcv(), asset_class="stock").to_dict()

    assert tmp_path.exists()
    assert {
        "asset_class",
        "trend_score",
        "trend_state",
        "direction",
        "confidence",
        "regime",
        "sub_scores",
        "raw_scores",
        "weights",
        "top_drivers",
        "regime_flags",
        "explanation",
        "metadata",
    } <= set(result)
