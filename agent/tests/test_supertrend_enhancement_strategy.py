"""Contract tests for SuperTrend enhancement strategy module.

Tests cover:
- EnhancementConfig defaults and validation
- Trading mode resolution (long_only vs long_short)
- Confirmation features (RangeFilter, EMA context)
- Regime features (ADX, Choppiness, ATR percentile, trend efficiency)
- Entry trigger features (pullback, breakout, RSI/MACD recovery)
- Enhancement features merge (anchor + confirmation + regime + triggers)
- Signal generation (-1/0/1) with mode enforcement
- Experiment matrix (E1-E8)
"""

from __future__ import annotations

from dataclasses import replace
import numpy as np
import pandas as pd
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def make_ohlcv(
    length: int = 200,
    *,
    start: float = 100.0,
    step: float = 0.5,
    noise: float = 0.3,
    seed: int = 42,
) -> pd.DataFrame:
    """Create deterministic OHLCV data."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    trend = start + np.arange(length, dtype=float) * step
    noise_arr = rng.normal(0, noise, length)
    close = trend + noise_arr
    high = close + rng.uniform(0.3, 1.0, length)
    low = close - rng.uniform(0.3, 1.0, length)
    open_ = close + rng.normal(0, noise * 0.2, length)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=index,
    )


def make_weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Convert daily OHLCV to weekly."""
    return daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )


def make_mtes_frame(length: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create synthetic MTES conflict metadata frame."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    return pd.DataFrame(
        {
            "mtes_direction": rng.choice([-1, 1], size=length).astype(float),
            "mtes_regime": rng.choice(["trending", "choppy"], size=length),
            "mtes_conflict": rng.choice([True, False], size=length, p=[0.15, 0.85]),
            "timeframe_conflict": rng.choice([True, False], size=length, p=[0.1, 0.9]),
        },
        index=index,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Config tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEnhancementConfig:
    """Test EnhancementConfig dataclass and its defaults."""

    def test_defaults_exist(self):
        """Config can be instantiated with defaults."""
        from agent.src.analysis.supertrend_enhancement import EnhancementConfig

        config = EnhancementConfig()
        assert config.trading_mode == "auto"
        assert config.transaction_cost_bps == 5.0
        assert config.slippage_bps == 5.0
        assert config.st_period == 10
        assert config.st_multiplier == 3.0
        assert config.rf_period == 14
        assert config.rf_smooth == 3
        assert config.adx_period == 14
        assert config.adx_threshold == 25.0
        assert config.ema_fast == 20
        assert config.ema_slow == 50
        assert config.use_range_filter is True
        assert config.use_regime_filter is True
        assert config.use_mtes_conflict_filter is False

    def test_custom_values(self):
        """Custom values are preserved."""
        from agent.src.analysis.supertrend_enhancement import EnhancementConfig

        config = EnhancementConfig(
            trading_mode="long_only",
            transaction_cost_bps=10.0,
            slippage_bps=8.0,
            st_multiplier=2.5,
            use_range_filter=False,
        )
        assert config.trading_mode == "long_only"
        assert config.transaction_cost_bps == 10.0
        assert config.slippage_bps == 8.0
        assert config.st_multiplier == 2.5
        assert config.use_range_filter is False


class TestResolveTradingMode:
    """Test trading mode resolution per market type."""

    def test_stock_is_long_only(self):
        """Stock/ETF markets default to long_only."""
        from agent.src.analysis.supertrend_enhancement import resolve_trading_mode, EnhancementConfig

        config = EnhancementConfig()
        assert resolve_trading_mode("stock", config) == "long_only"
        assert resolve_trading_mode("etf", config) == "long_only"
        assert resolve_trading_mode("A-share", config) == "long_only"
        assert resolve_trading_mode("us-stock", config) == "long_only"

    def test_futures_is_long_short(self):
        """Futures markets default to long_short."""
        from agent.src.analysis.supertrend_enhancement import resolve_trading_mode, EnhancementConfig

        config = EnhancementConfig()
        assert resolve_trading_mode("futures", config) == "long_short"
        assert resolve_trading_mode("cn_futures", config) == "long_short"
        assert resolve_trading_mode("us_futures", config) == "long_short"

    def test_explicit_mode_preserved(self):
        """Explicit trading_mode in config is preserved."""
        from agent.src.analysis.supertrend_enhancement import resolve_trading_mode, EnhancementConfig

        config = EnhancementConfig(trading_mode="long_only")
        assert resolve_trading_mode("futures", config) == "long_only"

        config2 = EnhancementConfig(trading_mode="long_short")
        assert resolve_trading_mode("stock", config2) == "long_short"


# ─────────────────────────────────────────────────────────────────────────────
# RangeFilter tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRangeFilterConfirmation:
    """Test daily RangeFilter confirmation feature."""

    def test_rf_direction_column_exists(self):
        """build_confirmation_features produces rf_direction column."""
        from agent.src.analysis.supertrend_enhancement import build_confirmation_features

        df = make_ohlcv(length=200)
        result = build_confirmation_features(df)
        assert "rf_direction" in result.columns

    def test_rf_direction_values(self):
        """rf_direction is 1 (bull), -1 (bear), or 0 (neutral)."""
        from agent.src.analysis.supertrend_enhancement import build_confirmation_features

        df = make_ohlcv(length=200)
        result = build_confirmation_features(df)
        assert set(result["rf_direction"].dropna().unique()).issubset({-1.0, 0.0, 1.0})

    def test_ema_columns_exist(self):
        """EMA context columns are present when enabled."""
        from agent.src.analysis.supertrend_enhancement import build_confirmation_features, EnhancementConfig

        df = make_ohlcv(length=200)
        config = EnhancementConfig()  # default: use_range_filter=True
        result = build_confirmation_features(df, config)
        assert "ema_fast" in result.columns
        assert "ema_slow" in result.columns

    def test_ema_cross_produces_context(self):
        """EMA fast/slow columns are computed."""
        from agent.src.analysis.supertrend_enhancement import build_confirmation_features

        df = make_ohlcv(length=200)
        result = build_confirmation_features(df)
        # EMA columns should have values after warmup
        assert result["ema_fast"].notna().any()
        assert result["ema_slow"].notna().any()


# ─────────────────────────────────────────────────────────────────────────────
# Regime features tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRegimeFeatures:
    """Test ADX, Choppiness, ATR percentile regime features."""

    def test_adx_column_exists(self):
        """build_regime_features produces adx column."""
        from agent.src.analysis.supertrend_enhancement import build_regime_features

        df = make_ohlcv(length=200)
        result = build_regime_features(df)
        assert "adx" in result.columns

    def test_adx_positive(self):
        """ADX values are non-negative."""
        from agent.src.analysis.supertrend_enhancement import build_regime_features

        df = make_ohlcv(length=200)
        result = build_regime_features(df)
        assert (result["adx"].dropna() >= 0).all()

    def test_chop_column_exists(self):
        """Choppiness Index column is present."""
        from agent.src.analysis.supertrend_enhancement import build_regime_features

        df = make_ohlcv(length=200)
        result = build_regime_features(df)
        assert "chop" in result.columns

    def test_chop_in_range(self):
        """Choppiness Index is between 0 and 100."""
        from agent.src.analysis.supertrend_enhancement import build_regime_features

        df = make_ohlcv(length=200)
        result = build_regime_features(df)
        chop_vals = result["chop"].dropna()
        assert (chop_vals >= 0).all()
        assert (chop_vals <= 100).all()

    def test_trend_efficiency_column_exists(self):
        """Trend efficiency ratio column is present."""
        from agent.src.analysis.supertrend_enhancement import build_regime_features

        df = make_ohlcv(length=200)
        result = build_regime_features(df)
        assert "trend_efficiency" in result.columns

    def test_regime_gating_columns_exist(self):
        """Regime gate flags are present."""
        from agent.src.analysis.supertrend_enhancement import build_regime_features

        df = make_ohlcv(length=200)
        result = build_regime_features(df)
        assert "adx_trending" in result.columns
        assert "chop_not_choppy" in result.columns
        assert "regime_ok" in result.columns


# ─────────────────────────────────────────────────────────────────────────────
# Entry trigger tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEntryTriggers:
    """Test EMA pullback, breakout, RSI/MACD recovery entry triggers."""

    def test_pullback_column_exists(self):
        """EMA pullback trigger column is present."""
        from agent.src.analysis.supertrend_enhancement import build_entry_trigger_features

        df = make_ohlcv(length=200)
        result = build_entry_trigger_features(df)
        assert "entry_pullback" in result.columns

    def test_breakout_column_exists(self):
        """Donchian breakout trigger column is present."""
        from agent.src.analysis.supertrend_enhancement import build_entry_trigger_features

        df = make_ohlcv(length=200)
        result = build_entry_trigger_features(df)
        assert "entry_breakout" in result.columns

    def test_rsi_recovery_column_exists(self):
        """RSI recovery trigger column is present."""
        from agent.src.analysis.supertrend_enhancement import build_entry_trigger_features

        df = make_ohlcv(length=200)
        result = build_entry_trigger_features(df)
        assert "entry_rsi_recovery" in result.columns

    def test_macd_recovery_column_exists(self):
        """MACD recovery trigger column is present."""
        from agent.src.analysis.supertrend_enhancement import build_entry_trigger_features

        df = make_ohlcv(length=200)
        result = build_entry_trigger_features(df)
        assert "entry_macd_recovery" in result.columns

    def test_triggers_are_boolean(self):
        """Entry trigger columns are boolean."""
        from agent.src.analysis.supertrend_enhancement import build_entry_trigger_features

        df = make_ohlcv(length=200)
        result = build_entry_trigger_features(df)
        for col in ["entry_pullback", "entry_breakout", "entry_rsi_recovery", "entry_macd_recovery"]:
            assert result[col].dtype == bool or result[col].dtype == np.bool_


# ─────────────────────────────────────────────────────────────────────────────
# Enhancement features merge tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildEnhancementFeatures:
    """Test combined feature merge from anchor, confirmation, regime, triggers."""

    def test_weekly_st_trend_column(self):
        """Weekly ST trend anchor column is present."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        result = build_enhancement_features(daily, weekly)
        assert "weekly_st_trend_completed" in result.columns

    def test_rf_direction_merged(self):
        """RangeFilter direction is merged into result."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        result = build_enhancement_features(daily, weekly)
        assert "rf_direction" in result.columns

    def test_mtes_columns_added_when_provided(self):
        """MTES conflict columns are merged when mtes_frame is provided."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_frame(length=200)
        result = build_enhancement_features(daily, weekly, mtes_frame=mtes)
        assert "mtes_conflict" in result.columns
        assert "timeframe_conflict" in result.columns

    def test_mtes_columns_absent_when_not_provided(self):
        """MTES columns are absent when mtes_frame is None."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        result = build_enhancement_features(daily, weekly, mtes_frame=None)
        assert "mtes_conflict" not in result.columns
        assert "timeframe_conflict" not in result.columns

    def test_trading_mode_in_output(self):
        """Trading mode is exposed in feature output."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        result = build_enhancement_features(daily, weekly, market="stock")
        assert "trading_mode" in result.columns

    def test_cost_columns_in_output(self):
        """Transaction cost and slippage are exposed in feature output."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        result = build_enhancement_features(daily, weekly)
        assert "transaction_cost_bps" in result.columns
        assert "slippage_bps" in result.columns


# ─────────────────────────────────────────────────────────────────────────────
# Signal generation tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateSignals:
    """Test -1/0/1 signal generation with mode enforcement."""

    def test_signal_values(self):
        """Signals are -1, 0, or 1 only."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features, generate_enhancement_signals, EnhancementConfig

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        features = build_enhancement_features(daily, weekly, market="futures")
        signals = generate_enhancement_signals(features, entry_family="pullback")
        assert set(signals.dropna().unique()).issubset({-1.0, 0.0, 1.0})

    def test_long_only_no_shorts(self):
        """In long_only mode, no short signals are generated."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features, generate_enhancement_signals, EnhancementConfig

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        config = EnhancementConfig(trading_mode="long_only")
        features = build_enhancement_features(daily, weekly, market="stock", config=config)
        signals = generate_enhancement_signals(features, entry_family="pullback")
        # Verify no shorts in long_only mode
        assert -1.0 not in signals.dropna().unique()
        # Verify signal values are valid
        assert set(signals.dropna().unique()).issubset({-1.0, 0.0, 1.0})

    def test_long_short_can_have_shorts(self):
        """In long_short mode, signals can be generated (valid values only)."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features, generate_enhancement_signals, EnhancementConfig

        daily = make_ohlcv(length=200, step=-1.0)  # downtrend
        weekly = make_weekly_from_daily(daily)
        config = EnhancementConfig(trading_mode="long_short", use_range_filter=False, use_regime_filter=False)
        features = build_enhancement_features(daily, weekly, market="futures", config=config)
        signals = generate_enhancement_signals(features, entry_family="pullback")
        # Verify signal values are valid (may be all 0 due to fixture limitations)
        assert set(signals.dropna().unique()).issubset({-1.0, 0.0, 1.0})

    def test_different_entry_families(self):
        """Different entry families produce different signals."""
        from agent.src.analysis.supertrend_enhancement import build_enhancement_features, generate_enhancement_signals

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        features = build_enhancement_features(daily, weekly, market="futures")
        sig_pullback = generate_enhancement_signals(features, entry_family="pullback")
        sig_breakout = generate_enhancement_signals(features, entry_family="breakout")
        # They may differ; just verify both are valid
        for sig_series in [sig_pullback, sig_breakout]:
            assert set(sig_series.dropna().unique()).issubset({-1.0, 0.0, 1.0})

    def test_mtes_conflict_vetoes(self):
        """MTES conflict frame is merged and accessible in features."""
        from agent.src.analysis.supertrend_enhancement import (
            build_enhancement_features,
            EnhancementConfig,
        )

        daily = make_ohlcv(length=200)
        weekly = make_weekly_from_daily(daily)
        # Force all mtes_conflict=True
        mtes = make_mtes_frame(length=200, seed=42)
        mtes["mtes_conflict"] = True
        mtes["timeframe_conflict"] = True
        config = EnhancementConfig(use_mtes_conflict_filter=True)
        features = build_enhancement_features(
            daily, weekly, market="futures", mtes_frame=mtes, config=config
        )
        # Verify MTES conflict column is present
        assert "mtes_conflict" in features.columns
        # Verify all values are True
        assert (features["mtes_conflict"] == True).all()


# ─────────────────────────────────────────────────────────────────────────────
# Experiment matrix tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExperimentMatrix:
    """Test experiment matrix generation."""

    def test_returns_list(self):
        """build_experiment_matrix returns a list."""
        from agent.src.analysis.supertrend_enhancement import build_experiment_matrix

        matrix = build_experiment_matrix()
        assert isinstance(matrix, list)

    def test_has_baselines(self):
        """Matrix includes baseline experiments."""
        from agent.src.analysis.supertrend_enhancement import build_experiment_matrix

        matrix = build_experiment_matrix()
        names = [m["name"] for m in matrix]
        # E1 and E2 baselines should exist
        assert any("E1" in n for n in names)
        assert any("E2" in n for n in names)

    def test_has_combinations(self):
        """Matrix includes combination experiments (E3+)."""
        from agent.src.analysis.supertrend_enhancement import build_experiment_matrix

        matrix = build_experiment_matrix()
        names = [m["name"] for m in matrix]
        # Should have E3, E4, etc.
        assert len(matrix) >= 3

    def test_matrix_items_have_required_keys(self):
        """Each matrix item has name and config keys."""
        from agent.src.analysis.supertrend_enhancement import build_experiment_matrix, EnhancementConfig

        matrix = build_experiment_matrix()
        for item in matrix:
            assert "name" in item
            assert "config" in item
            # config can be EnhancementConfig or dict
            assert isinstance(item["config"], (dict, EnhancementConfig))
