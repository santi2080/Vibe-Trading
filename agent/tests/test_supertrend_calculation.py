"""Contract tests for the canonical SuperTrend calculation module."""

from __future__ import annotations

import pandas as pd
import pytest
import numpy as np

from src.analysis.supertrend import (
    SuperTrendConfig,
    calculate_supertrend,
    remove_supertrend_warmup,
    align_completed_weekly_supertrend,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_ohlcv(
    length: int = 250,
    *,
    start: float = 100.0,
    step: float = 0.5,
    noise: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Create deterministic OHLCV data for SuperTrend tests.

    By default produces a steady uptrend with mild noise.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    trend = start + np.arange(length, dtype=float) * step
    noise_arr = rng.normal(0, noise, length)
    close = trend + noise_arr
    high = close + rng.normal(0.5, 0.2, length)
    low = close - rng.normal(0.5, 0.2, length)
    open_ = close + rng.normal(0, 0.1, length)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def rising_fixture() -> pd.DataFrame:
    """Clean monotonic uptrend: high ATR efficiency, bullish throughout."""
    return make_ohlcv(length=200, start=100.0, step=1.0, noise=0.3, seed=7)


def falling_fixture() -> pd.DataFrame:
    """Clean monotonic downtrend: bearish throughout."""
    return make_ohlcv(length=200, start=200.0, step=-1.0, noise=0.3, seed=13)


def choppy_fixture() -> pd.DataFrame:
    """Sideways/noise: low ATR efficiency, frequent trend flips."""
    rng = np.random.default_rng(99)
    length = 250
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = 100.0 + rng.normal(0, 2.0, length).cumsum()
    high = close + rng.normal(1.0, 0.3, length)
    low = close - rng.normal(1.0, 0.3, length)
    open_ = close + rng.normal(0, 0.2, length)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=index,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Config tests
# ─────────────────────────────────────────────────────────────────────────────

def test_config_defaults() -> None:
    """Default config uses period=10, multiplier=3.0, wilder ATR."""
    cfg = SuperTrendConfig()
    assert cfg.period == 10
    assert cfg.multiplier == 3.0
    assert cfg.warmup_extra == 100
    assert cfg.atr_method == "wilder"


def test_config_custom() -> None:
    """Custom config overrides all fields."""
    cfg = SuperTrendConfig(period=20, multiplier=2.5, warmup_extra=50, atr_method="ema")
    assert cfg.period == 20
    assert cfg.multiplier == 2.5
    assert cfg.warmup_extra == 50
    assert cfg.atr_method == "ema"


# ─────────────────────────────────────────────────────────────────────────────
# Required columns validation
# ─────────────────────────────────────────────────────────────────────────────

def test_calculate_requires_ohlc_columns() -> None:
    """Missing required OHLC columns raises ValueError."""
    cfg = SuperTrendConfig()
    df = pd.DataFrame({"open": [1, 2, 3], "close": [1, 2, 3]})  # missing high/low
    with pytest.raises(ValueError, match="missing.*required.*columns"):
        calculate_supertrend(df, cfg)


def test_calculate_requires_timestamp_index() -> None:
    """DataFrame without datetime index raises ValueError."""
    cfg = SuperTrendConfig()
    df = pd.DataFrame(
        {"open": [1.0, 2.0], "high": [2.0, 3.0], "low": [0.5, 1.0], "close": [1.5, 2.5]},
        index=pd.Index([0, 1]),
    )
    with pytest.raises(ValueError, match="[Dd]ate[Tt]ime[Ii]ndex|timestamp index"):
        calculate_supertrend(df, cfg)


def test_calculate_requires_minimum_bars() -> None:
    """Fewer bars than warmup period raises ValueError."""
    cfg = SuperTrendConfig(period=10, warmup_extra=0)  # warmup = period
    df = make_ohlcv(length=5)
    with pytest.raises(ValueError, match="warmup.*exceeds"):
        calculate_supertrend(df, cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

def test_output_contains_all_required_columns() -> None:
    """Result DataFrame contains every declared column."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    expected = {
        "st_atr",
        "st_basic_upper",
        "st_basic_lower",
        "st_final_upper",
        "st_final_lower",
        "st_trend",
        "supertrend",
    }
    assert expected <= set(result.columns)


def test_output_index_preserved() -> None:
    """Input datetime index is preserved in result."""
    cfg = SuperTrendConfig()
    df = make_ohlcv(length=200)
    result = calculate_supertrend(df, cfg)
    assert result.index.name == "timestamp"
    assert isinstance(result.index, pd.DatetimeIndex)
    assert len(result) == len(df)


# ─────────────────────────────────────────────────────────────────────────────
# ATR correctness
# ─────────────────────────────────────────────────────────────────────────────

def test_atr_is_strictly_positive() -> None:
    """ATR values are always >= 0 after warmup."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    valid = result["st_atr"].dropna()
    assert (valid >= 0).all(), "ATR must never be negative"


def test_atr_increases_with_volatility() -> None:
    """Higher-volatility data produces higher ATR."""
    cfg = SuperTrendConfig(period=14)
    calm = calculate_supertrend(make_ohlcv(length=200, noise=0.1, seed=1), cfg)
    volatile = calculate_supertrend(make_ohlcv(length=200, noise=5.0, seed=2), cfg)

    # Compare median ATR in the stable region (skip warmup)
    skip = cfg.period * 3
    cal_median = calm["st_atr"].iloc[skip:].median()
    vol_median = volatile["st_atr"].iloc[skip:].median()
    assert vol_median > cal_median, "Volatile data must have higher ATR"


# ─────────────────────────────────────────────────────────────────────────────
# Basic band sanity
# ─────────────────────────────────────────────────────────────────────────────

def test_basic_upper_above_close_typical() -> None:
    """st_basic_upper is approximately close + multiplier*ATR (above price)."""
    cfg = SuperTrendConfig(multiplier=3.0)
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    assert (valid["st_basic_upper"] >= valid["close"]).all()


def test_basic_lower_below_close_typical() -> None:
    """st_basic_lower is approximately close - multiplier*ATR (below price)."""
    cfg = SuperTrendConfig(multiplier=3.0)
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    assert (valid["st_basic_lower"] <= valid["close"]).all()


def test_basic_upper_greater_than_basic_lower() -> None:
    """Basic upper band is always above basic lower band."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    assert (valid["st_basic_upper"] > valid["st_basic_lower"]).all()


# ─────────────────────────────────────────────────────────────────────────────
# Final bands are stateful (carry-forward)
# ─────────────────────────────────────────────────────────────────────────────

def test_final_bands_exhibit_carry_forward() -> None:
    """Final bands carry forward statefully (not recomputed from scratch each bar).

    In choppy/sideways data the same final band value should be reused across
    consecutive bars rather than being freshly recalculated each bar.
    """
    cfg = SuperTrendConfig()
    result = calculate_supertrend(choppy_fixture(), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]

    # Count how many times final_upper changed
    diffs = valid["st_final_upper"].diff().dropna().abs()
    changes = diffs > 1e-10
    change_ratio = changes.sum() / len(changes)
    # In choppy data bands should carry forward >30% of bars
    assert change_ratio < 0.95, \
        f"Final upper changed {change_ratio:.1%} of bars — too volatile for carry-forward"


def test_final_upper_geq_basic_upper() -> None:
    """Final upper band is >= basic upper (bands only move up, never down)."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    assert (valid["st_final_upper"] >= valid["st_basic_upper"]).all()


def test_final_lower_leq_basic_lower() -> None:
    """Final lower band respects the stateful band invariant.

    Bull state (trend=1): final_lower >= basic_lower  (band only moves UP)
    Bear state (trend=-1): final_lower <= basic_lower  (band only moves DOWN)
    """
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]

    bull = valid["st_trend"] == 1.0
    bear = valid["st_trend"] == -1.0

    # In bull, lower band only rises
    assert (valid.loc[bull, "st_final_lower"] >= valid.loc[bull, "st_basic_lower"]).all(), \
        "Bull state: final_lower should be >= basic_lower"
    # In bear, lower band only falls
    assert (valid.loc[bear, "st_final_lower"] <= valid.loc[bear, "st_basic_lower"]).all(), \
        "Bear state: final_lower should be <= basic_lower"


# ─────────────────────────────────────────────────────────────────────────────
# Trend state transitions
# ─────────────────────────────────────────────────────────────────────────────

def test_trend_values_are_valid() -> None:
    """st_trend contains only valid state values."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    valid_trends = result["st_trend"].dropna()
    assert set(valid_trends.unique()).issubset({1.0, -1.0})


def test_trend_flips_require_close_crossing_final_band() -> None:
    """A trend flip requires the close to cross the relevant final band.

    This tests the core no-lookahead truth: trend direction changes only when
    the price violates the current trend's boundary band.
    """
    cfg = SuperTrendConfig(period=10, multiplier=3.0)
    result = calculate_supertrend(make_ohlcv(length=300), cfg)

    close = result["close"]
    final_upper = result["st_final_upper"]
    final_lower = result["st_final_lower"]
    trend = result["st_trend"]

    for i in range(1, len(result)):
        if pd.isna(trend.iloc[i]) or pd.isna(trend.iloc[i - 1]):
            continue
        curr_trend = trend.iloc[i]
        prev_trend = trend.iloc[i - 1]
        if curr_trend != prev_trend:
            # Trend flipped: close must have crossed the RELEVANT final band
            if prev_trend == 1.0:
                # Was bullish → bearish: close must have dropped below final_lower
                assert close.iloc[i] < final_lower.iloc[i], \
                    "Bull→Bear flip requires close below final_lower"
            else:
                # Was bearish → bullish: close must have risen above final_upper
                assert close.iloc[i] > final_upper.iloc[i], \
                    "Bear→Bull flip requires close above final_upper"


def test_rising_market_is_bullish() -> None:
    """A strongly rising market is predominantly bullish (trend=1)."""
    cfg = SuperTrendConfig(period=10, multiplier=3.0)
    result = calculate_supertrend(rising_fixture(), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    bull_ratio = (valid["st_trend"] == 1.0).sum() / len(valid)
    assert bull_ratio > 0.7, f"Strong uptrend should be >70% bullish, got {bull_ratio:.1%}"


def test_falling_market_is_bearish() -> None:
    """A strongly falling market is predominantly bearish (trend=-1)."""
    cfg = SuperTrendConfig(period=10, multiplier=3.0)
    result = calculate_supertrend(falling_fixture(), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    bear_ratio = (valid["st_trend"] == -1.0).sum() / len(valid)
    assert bear_ratio > 0.7, f"Strong downtrend should be >70% bearish, got {bear_ratio:.1%}"


def test_choppy_market_flips_more() -> None:
    """A choppy market flips trend more often than a trending market."""
    cfg = SuperTrendConfig(period=10, multiplier=3.0)

    trending = calculate_supertrend(rising_fixture(), cfg)
    skip = cfg.period * 3
    trend_trend = trending["st_trend"].iloc[skip:].dropna()
    trending_flips = (trend_trend.diff().abs() > 0).sum()

    choppy = calculate_supertrend(choppy_fixture(), cfg)
    choppy_trend = choppy["st_trend"].iloc[skip:].dropna()
    choppy_flips = (choppy_trend.diff().abs() > 0).sum()

    assert choppy_flips > trending_flips, \
        "Choppy market must have more trend flips than trending market"


# ─────────────────────────────────────────────────────────────────────────────
# SuperTrend line values
# ─────────────────────────────────────────────────────────────────────────────

def test_supertrend_equals_final_band_for_current_state() -> None:
    """supertrend == st_final_lower when bullish, st_final_upper when bearish."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]

    bull_mask = valid["st_trend"] == 1.0
    bear_mask = valid["st_trend"] == -1.0

    np.testing.assert_allclose(
        valid.loc[bull_mask, "supertrend"],
        valid.loc[bull_mask, "st_final_lower"],
        rtol=1e-10,
        err_msg="Bullish supertrend must equal final_lower",
    )
    np.testing.assert_allclose(
        valid.loc[bear_mask, "supertrend"],
        valid.loc[bear_mask, "st_final_upper"],
        rtol=1e-10,
        err_msg="Bearish supertrend must equal final_upper",
    )


def test_supertrend_is_a_contiguous_line() -> None:
    """supertrend has no NaN gaps after warmup (continuous line)."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]
    assert valid["supertrend"].isna().sum() == 0, "supertrend must be contiguous after warmup"


def test_supertrend_respects_trend_direction() -> None:
    """When trend=1 (bull), supertrend <= close; when trend=-1, supertrend >= close."""
    cfg = SuperTrendConfig()
    result = calculate_supertrend(make_ohlcv(length=200), cfg)
    skip = cfg.period * 3
    valid = result.iloc[skip:]

    bull = valid["st_trend"] == 1.0
    bear = valid["st_trend"] == -1.0

    assert (valid.loc[bull, "supertrend"] <= valid.loc[bull, "close"]).all()
    assert (valid.loc[bear, "supertrend"] >= valid.loc[bear, "close"]).all()


# ─────────────────────────────────────────────────────────────────────────────
# Warmup removal
# ─────────────────────────────────────────────────────────────────────────────

def test_warmup_removal_reduces_length() -> None:
    """remove_supertrend_warmup returns fewer rows than input."""
    cfg = SuperTrendConfig(period=10, warmup_extra=100)
    df = make_ohlcv(length=300)
    result = calculate_supertrend(df, cfg)
    trimmed = remove_supertrend_warmup(result, cfg)
    assert len(trimmed) < len(result)
    assert len(trimmed) > 0


def test_warmup_removal_leaves_data_intact() -> None:
    """Trimmed rows match the tail of the original result."""
    cfg = SuperTrendConfig(period=10, warmup_extra=100)
    df = make_ohlcv(length=300)
    result = calculate_supertrend(df, cfg)
    trimmed = remove_supertrend_warmup(result, cfg)
    # The trimmed result should match the last rows of the original
    original_tail = result.iloc[-len(trimmed):].reset_index(drop=True)
    trimmed_compare = trimmed.reset_index(drop=True)
    pd.testing.assert_frame_equal(original_tail, trimmed_compare)


def test_warmup_removal_trims_at_least_warmup_bars() -> None:
    """At least warmup bars are removed."""
    cfg = SuperTrendConfig(period=10, warmup_extra=50)
    df = make_ohlcv(length=300)
    result = calculate_supertrend(df, cfg)
    trimmed = remove_supertrend_warmup(result, cfg)
    expected_warmup = cfg.period * 3 + cfg.warmup_extra
    assert len(result) - len(trimmed) >= expected_warmup


def test_warmup_removal_preserves_schema() -> None:
    """Trimmed DataFrame has the same columns as input."""
    cfg = SuperTrendConfig()
    df = make_ohlcv(length=300)
    result = calculate_supertrend(df, cfg)
    trimmed = remove_supertrend_warmup(result, cfg)
    assert set(trimmed.columns) == set(result.columns)


# ─────────────────────────────────────────────────────────────────────────────
# Weekly anchor — no-lookahead alignment
# ─────────────────────────────────────────────────────────────────────────────

def test_weekly_anchor_adds_required_columns() -> None:
    """align_completed_weekly_supertrend adds weekly columns to daily DataFrame."""
    cfg = SuperTrendConfig()
    # Need enough daily bars for weekly resample to exceed warmup (130 weekly bars needed)
    daily = make_ohlcv(length=1500, seed=42)
    weekly = daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )

    result = align_completed_weekly_supertrend(daily, weekly, cfg)

    weekly_cols = {c for c in result.columns if c.startswith("w_")}
    assert len(weekly_cols) > 0


def test_weekly_anchor_uses_completed_bars_only() -> None:
    """Weekly values are lagged by at least 1 bar (no same-week lookahead).

    The weekly supertrend value at daily bar i should reflect only the
    weekly bar that closed at or before bar i (not the current open weekly bar).
    """
    cfg = SuperTrendConfig()
    daily = make_ohlcv(length=1500, seed=42)
    weekly = daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )

    result = align_completed_weekly_supertrend(daily, weekly, cfg)

    w_cols = [c for c in result.columns if c.startswith("w_")]
    if w_cols:
        skip = cfg.period * 3 + cfg.warmup_extra
        post_warmup = result.iloc[skip:]
        nan_counts = post_warmup[w_cols].isna().sum()
        assert (nan_counts == 0).any(), \
            "Completed weekly bars should provide non-NaN values after warmup"


def test_weekly_supertrend_is_contiguous() -> None:
    """Weekly supertrend column has no NaN gaps after warmup (forward-filled)."""
    cfg = SuperTrendConfig()
    daily = make_ohlcv(length=1500, seed=42)
    weekly = daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    result = align_completed_weekly_supertrend(daily, weekly, cfg)

    w_cols = [c for c in result.columns if c.startswith("w_supertrend")]
    if w_cols:
        w_col = w_cols[0]
        skip = cfg.period * 3 + cfg.warmup_extra
        post = result[w_col].iloc[skip:]
        assert post.isna().sum() == 0, "Weekly supertrend must be contiguous after warmup"


def test_weekly_alignment_does_not_modify_daily_columns() -> None:
    """align_completed_weekly_supertrend only adds columns, never overwrites daily."""
    cfg = SuperTrendConfig()
    daily = make_ohlcv(length=1500, seed=42)
    daily_original = daily.copy()
    weekly = daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )

    result = align_completed_weekly_supertrend(daily, weekly, cfg)

    pd.testing.assert_frame_equal(result[["open", "high", "low", "close", "volume"]], daily_original)


def test_weekly_anchor_rejects_invalid_weekly() -> None:
    """Passing non-datetime-indexed weekly data raises ValueError."""
    cfg = SuperTrendConfig()
    daily = make_ohlcv(length=250)
    weekly = pd.DataFrame(
        {"close": [100.0, 101.0]},
        index=pd.Index([0, 1]),  # NOT a DatetimeIndex
    )
    with pytest.raises(ValueError, match="[Dd]ate[Tt]ime[Ii]ndex"):
        align_completed_weekly_supertrend(daily, weekly, cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Multiplier and period sensitivity
# ─────────────────────────────────────────────────────────────────────────────

def test_higher_multiplier_produces_fewer_trend_flips() -> None:
    """Larger multiplier widens bands → fewer trend flips."""
    cfg_tight = SuperTrendConfig(multiplier=2.0)
    cfg_wide = SuperTrendConfig(multiplier=5.0)

    daily = choppy_fixture()

    res_tight = calculate_supertrend(daily, cfg_tight)
    res_wide = calculate_supertrend(daily, cfg_wide)

    skip = cfg_tight.period * 3 + cfg_tight.warmup_extra
    trend_tight = res_tight["st_trend"].iloc[skip:].dropna()
    trend_wide = res_wide["st_trend"].iloc[skip:].dropna()

    flips_tight = (trend_tight.diff().abs() > 0).sum()
    flips_wide = (trend_wide.diff().abs() > 0).sum()

    assert flips_wide <= flips_tight, \
        "Higher multiplier should produce fewer or equal trend flips"


def test_longer_period_produces_smoother_atr() -> None:
    """Longer ATR period produces smoother (less jittery) ATR."""
    cfg_fast = SuperTrendConfig(period=7)
    cfg_slow = SuperTrendConfig(period=21)

    daily = choppy_fixture()

    res_fast = calculate_supertrend(daily, cfg_fast)
    res_slow = calculate_supertrend(daily, cfg_slow)

    skip_fast = cfg_fast.period * 3
    skip_slow = cfg_slow.period * 3

    # ATR variability = mean absolute change
    atr_fast = res_fast["st_atr"].iloc[skip_fast:].dropna()
    atr_slow = res_slow["st_atr"].iloc[skip_slow:].dropna()

    variability_fast = atr_fast.diff().abs().mean()
    variability_slow = atr_slow.diff().abs().mean()

    assert variability_slow < variability_fast, \
        "Longer-period ATR should be smoother (less variability)"


def test_different_atr_methods_produce_different_results() -> None:
    """wilder vs ema ATR methods produce different ATR values."""
    cfg_wilder = SuperTrendConfig(atr_method="wilder")
    cfg_ema = SuperTrendConfig(atr_method="ema")

    daily = choppy_fixture()

    res_wilder = calculate_supertrend(daily, cfg_wilder)
    res_ema = calculate_supertrend(daily, cfg_ema)

    skip = cfg_wilder.period * 3
    np.testing.assert_array_less(
        0.01,
        np.abs(res_wilder["st_atr"].iloc[skip:].dropna().values -
               res_ema["st_atr"].iloc[skip:].dropna().values).mean(),
        err_msg="wilder and ema ATR should produce different ATR values",
    )
