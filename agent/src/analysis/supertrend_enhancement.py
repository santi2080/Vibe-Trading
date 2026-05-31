"""SuperTrend Enhancement Strategy Module.

Phase 03 feature and signal logic combining:
- Completed weekly SuperTrend anchor (from 03-01)
- Daily RangeFilter confirmation
- ADX/Choppiness/ATR percentile regime filters
- EMA pullback / Donchian breakout / RSI/MACD recovery entry triggers
- MTES conflict-frame filtering (conflict/interpretability filter)
- Long-only (ETF/stock) and long-short (futures) trading modes

Key design decisions (locked in 03-RESEARCH):
- Weekly ST is the PRIMARY trend source; daily RF is first confirmation candidate.
- MTES is a conflict/interpretability filter, NOT the primary trend indicator.
- Trading mode is configurable with defaults: long_only for stock/ETF, long_short for futures.
- All triggers are separate boolean columns; signals are generated separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

from agent.src.analysis.supertrend import (
    SuperTrendConfig,
    calculate_supertrend,
    align_completed_weekly_supertrend,
)


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EnhancementConfig:
    """Configuration for SuperTrend enhancement strategy.

    Parameters
    ----------
    trading_mode : str
        "auto" (default), "long_only", or "long_short".  When "auto",
        resolve_trading_mode() infers from market.
    transaction_cost_bps : float
        Round-trip transaction cost in basis points.  Default 5 bps.
    slippage_bps : float
        Slippage assumption in basis points.  Default 5 bps.

    SuperTrend parameters
    ---------------------
    st_period : int
        ATR lookback period for SuperTrend.  Default 10.
    st_multiplier : float
        Band width multiplier.  Default 3.0.
    st_warmup_extra : int
        Extra warmup bars.  Default 100.
    st_atr_method : str
        "wilder" or "ema".  Default "wilder".

    RangeFilter parameters
    ----------------------
    rf_period : int
        RangeFilter period.  Default 14.
    rf_smooth : int
        Smoothing period.  Default 3.

    Regime parameters
    ----------------
    adx_period : int
        ADX calculation period.  Default 14.
    adx_threshold : float
        Minimum ADX for trending regime.  Default 25.0.
    chop_period : int
        Choppiness Index period.  Default 14.
    atr_percentile_window : int
        Rolling window for ATR percentile.  Default 252.

    EMA parameters
    ---------------
    ema_fast : int
        Fast EMA period.  Default 20.
    ema_slow : int
        Slow EMA period.  Default 50.
    ema_pullback_threshold : float
        Max pullback from EMA to permit entry (fraction of ATR).  Default 0.5.

    RSI / MACD parameters
    ---------------------
    rsi_period : int
        RSI period.  Default 14.
    rsi_recovery_threshold : float
        RSI must be above this to trigger recovery.  Default 40.0.
    macd_fast : int
        MACD fast period.  Default 12.
    macd_slow : int
        MACD slow period.  Default 26.
    macd_signal : int
        MACD signal period.  Default 9.
    macd_recovery_threshold : float
        MACD histogram must exceed this to trigger recovery.  Default 0.0.

    Breakout parameters
    -------------------
    breakout_period : int
        Donchian lookback period.  Default 20.

    Filter toggles
    ---------------
    use_range_filter : bool
        Require daily RangeFilter confirmation.  Default True.
    use_regime_filter : bool
        Apply ADX/Chop/ATR regime gates.  Default True.
    use_mtes_conflict_filter : bool
        Apply MTES conflict veto.  Default False.
    """

    # Mode / cost
    trading_mode: str = "auto"
    transaction_cost_bps: float = 5.0
    slippage_bps: float = 5.0

    # SuperTrend
    st_period: int = 10
    st_multiplier: float = 3.0
    st_warmup_extra: int = 100
    st_atr_method: str = "wilder"

    # RangeFilter
    rf_period: int = 14
    rf_smooth: int = 3

    # Regime
    adx_period: int = 14
    adx_threshold: float = 25.0
    chop_period: int = 14
    atr_percentile_window: int = 252

    # EMA
    ema_fast: int = 20
    ema_slow: int = 50
    ema_pullback_threshold: float = 0.5

    # RSI / MACD
    rsi_period: int = 14
    rsi_recovery_threshold: float = 40.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_recovery_threshold: float = 0.0

    # Breakout
    breakout_period: int = 20

    # Filters
    use_range_filter: bool = True
    use_regime_filter: bool = True
    use_mtes_conflict_filter: bool = False

    @property
    def st_config(self) -> SuperTrendConfig:
        return SuperTrendConfig(
            period=self.st_period,
            multiplier=self.st_multiplier,
            warmup_extra=self.st_warmup_extra,
            atr_method=self.st_atr_method,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Trading mode resolution
# ─────────────────────────────────────────────────────────────────────────────


def resolve_trading_mode(market: str, config: EnhancementConfig) -> str:
    """Resolve effective trading mode from market type and config.

    Parameters
    ----------
    market : str
        Market identifier (e.g., "stock", "etf", "futures", "cn_futures").
    config : EnhancementConfig
        Strategy configuration.

    Returns
    -------
    str
        "long_only" or "long_short".
    """
    if config.trading_mode != "auto":
        return config.trading_mode

    futures_keywords = ("futures", "future")
    stock_keywords = ("stock", "etf", "share", "a-share", "us-stock")

    market_lower = market.lower()
    if any(kw in market_lower for kw in futures_keywords):
        return "long_short"
    if any(kw in market_lower for kw in stock_keywords):
        return "long_only"
    # Default for unknown markets
    return "long_only"


# ─────────────────────────────────────────────────────────────────────────────
# RangeFilter (daily confirmation)
# ─────────────────────────────────────────────────────────────────────────────


def _compute_rangefilter_direction(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
    smooth: int,
) -> pd.Series:
    """Compute RangeFilter direction: 1 (bull), -1 (bear), 0 (neutral).

    RangeFilter = smoothed highest high and lowest low over period.
    Direction: bull when close > filter high, bear when close < filter low,
    neutral otherwise.
    """
    # Highest high and lowest low
    hh = high.rolling(window=period, min_periods=period).max()
    ll = low.rolling(window=period, min_periods=period).min()

    # Smoothed mid-point
    filt_high = hh.rolling(window=smooth, min_periods=smooth).mean()
    filt_low = ll.rolling(window=smooth, min_periods=smooth).mean()
    filt_mid = (filt_high + filt_low) / 2.0

    direction = pd.Series(0.0, index=close.index)
    direction = direction.where(close <= filt_low, other=0.0)
    direction = direction.where(close > filt_low, other=1.0)
    direction = direction.where(close < filt_high, other=0.0)
    direction = direction.where(close >= filt_high, other=-1.0)
    return direction


# ─────────────────────────────────────────────────────────────────────────────
# EMA helpers
# ─────────────────────────────────────────────────────────────────────────────


def _ema_pullback(
    close: pd.Series,
    ema_fast: pd.Series,
    ema_slow: pd.Series,
    atr: pd.Series,
    threshold: float,
) -> pd.Series:
    """Detect EMA pullback entries.

    Long pullback: price pulled back to within `threshold` ATR of EMA
    while still in uptrend (ema_fast > ema_slow).
    """
    pullback_depth = (ema_fast - close).abs() / atr.replace(0, np.nan)
    in_uptrend = ema_fast > ema_slow
    is_pullback = (pullback_depth <= threshold) & in_uptrend
    return is_pullback


# ─────────────────────────────────────────────────────────────────────────────
# ADX
# ─────────────────────────────────────────────────────────────────────────────


def _compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute ADX, +DI, -DI series."""
    tr = _true_range(high, low, close)
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_smooth = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * plus_dm_smooth / atr_smooth.replace(0, np.nan)
    minus_di = 100 * minus_dm_smooth / atr_smooth.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    return adx, plus_di, minus_di


def _true_range(high, low, close):
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# Choppiness Index
# ─────────────────────────────────────────────────────────────────────────────


def _compute_choppiness(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
) -> pd.Series:
    """Compute Choppiness Index (Ehler).

    Values > 61.8 indicate choppy market; values < 38.2 indicate trending.
    """
    tr = _true_range(high, low, close)
    atr_sum = tr.rolling(window=period, min_periods=period).sum()
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    range_sum = highest - lowest
    ratio = atr_sum / range_sum.replace(0, np.nan)
    # Clamp ratio to positive before log
    ratio = ratio.clip(lower=1e-10)
    chop = 100 * np.log10(ratio)
    chop = 100 * chop / np.log10(period)
    return chop.clip(0, 100)


# ─────────────────────────────────────────────────────────────────────────────
# Trend efficiency ratio
# ─────────────────────────────────────────────────────────────────────────────


def _compute_trend_efficiency(
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Trend efficiency ratio: directional movement / total movement.

    Close to 1.0 = efficient trending; close to 0 = choppy.
    """
    net = close.diff(period).abs()
    total = close.diff().abs().rolling(window=period).sum()
    return (net / total.replace(0, np.nan)).clip(-1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# RSI
# ─────────────────────────────────────────────────────────────────────────────


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """Compute RSI."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


# ─────────────────────────────────────────────────────────────────────────────
# MACD
# ─────────────────────────────────────────────────────────────────────────────


def _compute_macd(
    close: pd.Series,
    fast: int,
    slow: int,
    signal: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD line, signal, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ─────────────────────────────────────────────────────────────────────────────
# ATR (plain)
# ─────────────────────────────────────────────────────────────────────────────


def _compute_atr(high, low, close, period: int) -> pd.Series:
    tr = _true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


# ─────────────────────────────────────────────────────────────────────────────
# Feature builders
# ─────────────────────────────────────────────────────────────────────────────


def build_confirmation_features(
    df: pd.DataFrame,
    config: Optional[EnhancementConfig] = None,
) -> pd.DataFrame:
    """Add daily RangeFilter confirmation and EMA context columns.

    Adds columns:
    - rf_direction : 1 / -1 / 0
    - ema_fast, ema_slow
    """
    if config is None:
        config = EnhancementConfig()

    result = df.copy()
    close = result["close"]
    high = result["high"]
    low = result["low"]

    # RangeFilter direction
    result["rf_direction"] = _compute_rangefilter_direction(
        high, low, close, config.rf_period, config.rf_smooth
    )

    # EMA context — always compute
    result["ema_fast"] = close.ewm(
        span=config.ema_fast, adjust=False, min_periods=config.ema_fast
    ).mean()
    result["ema_slow"] = close.ewm(
        span=config.ema_slow, adjust=False, min_periods=config.ema_slow
    ).mean()

    return result


def build_regime_features(
    df: pd.DataFrame,
    config: Optional[EnhancementConfig] = None,
) -> pd.DataFrame:
    """Add ADX, Choppiness, ATR percentile, and regime gate columns.

    Adds columns:
    - adx, plus_di, minus_di
    - chop (Choppiness Index)
    - atr_percentile (rolling percentile of ATR)
    - trend_efficiency
    - adx_trending : ADX > threshold
    - chop_not_choppy : Choppiness < 61.8
    - regime_ok : combined regime gate
    """
    if config is None:
        config = EnhancementConfig()

    result = df.copy()
    high = result["high"]
    low = result["low"]
    close = result["close"]

    # ADX
    adx, plus_di, minus_di = _compute_adx(high, low, close, config.adx_period)
    result["adx"] = adx
    result["plus_di"] = plus_di
    result["minus_di"] = minus_di

    # Choppiness
    result["chop"] = _compute_choppiness(high, low, close, config.chop_period)

    # ATR percentile
    atr_raw = _compute_atr(high, low, close, config.adx_period)
    window = min(config.atr_percentile_window, len(atr_raw) - 1)
    if window > 20:
        atr_rank = atr_raw.rolling(window=window, min_periods=20).apply(
            lambda x: float((x < x[-1]).sum()) / len(x) if len(x) > 0 else np.nan,
            raw=True,
        )
        result["atr_percentile"] = atr_rank * 100
    else:
        result["atr_percentile"] = 50.0

    # Trend efficiency
    result["trend_efficiency"] = _compute_trend_efficiency(close)

    # Regime gate flags
    result["adx_trending"] = result["adx"] > config.adx_threshold
    result["chop_not_choppy"] = result["chop"] < 61.8

    # Combined regime: require ADX trending + not choppy
    result["regime_ok"] = result["adx_trending"] & result["chop_not_choppy"]

    return result


def build_entry_trigger_features(
    df: pd.DataFrame,
    config: Optional[EnhancementConfig] = None,
) -> pd.DataFrame:
    """Add entry trigger feature columns.

    Adds boolean columns:
    - entry_pullback : EMA pullback trigger
    - entry_breakout : Donchian breakout trigger
    - entry_rsi_recovery : RSI recovering from oversold
    - entry_macd_recovery : MACD histogram positive and recovering
    """
    if config is None:
        config = EnhancementConfig()

    result = df.copy()
    close = result["close"]
    high = result["high"]
    low = result["low"]

    # ATR for normalisation
    atr = _compute_atr(high, low, close, config.adx_period)

    # EMA pullback
    ema_fast = result.get("ema_fast")
    ema_slow = result.get("ema_fast")  # placeholder
    if ema_fast is None:
        ema_fast = close.ewm(
            span=config.ema_fast, adjust=False, min_periods=config.ema_fast
        ).mean()
    if ema_slow is None:
        ema_slow = close.ewm(
            span=config.ema_slow, adjust=False, min_periods=config.ema_slow
        ).mean()
    result["ema_fast"] = ema_fast
    result["ema_slow"] = ema_slow

    pullback = (ema_fast - close).abs() / atr.replace(0, np.nan)
    in_uptrend = ema_fast > ema_slow
    result["entry_pullback"] = (pullback <= config.ema_pullback_threshold) & in_uptrend

    # Donchian breakout
    highest = high.rolling(window=config.breakout_period, min_periods=config.breakout_period).max()
    result["entry_breakout"] = close > highest.shift(1)

    # RSI recovery
    rsi = _compute_rsi(close, config.rsi_period)
    result["rsi"] = rsi
    result["entry_rsi_recovery"] = rsi > config.rsi_recovery_threshold

    # MACD recovery
    macd_line, signal_line, histogram = _compute_macd(
        close, config.macd_fast, config.macd_slow, config.macd_signal
    )
    result["macd_histogram"] = histogram
    result["entry_macd_recovery"] = histogram > config.macd_recovery_threshold

    return result


def build_enhancement_features(
    daily_df: pd.DataFrame,
    weekly_df: Optional[pd.DataFrame] = None,
    market: str = "stock",
    mtes_frame: Optional[pd.DataFrame] = None,
    config: Optional[EnhancementConfig] = None,
) -> pd.DataFrame:
    """Combine all feature layers into a single DataFrame.

    Feature layers applied in order:
    1. Weekly SuperTrend anchor (completed bars, no lookahead)
    2. Daily confirmation (RangeFilter + EMA)
    3. Regime features (ADX, Choppiness, ATR percentile, efficiency)
    4. Entry triggers (pullback, breakout, RSI/MACD recovery)
    5. MTES conflict columns (if mtes_frame provided)

    Adds meta columns:
    - trading_mode, transaction_cost_bps, slippage_bps
    """
    if config is None:
        config = EnhancementConfig()

    # Resolve effective trading mode
    mode = resolve_trading_mode(market, config)

    # Step 1: Weekly SuperTrend anchor
    result = daily_df.copy()
    weekly_usable = False
    if weekly_df is not None and len(weekly_df) > 0:
        # Check if weekly data has enough rows for ST warmup
        min_required = config.st_period * 3 + config.st_warmup_extra + 1
        if len(weekly_df) >= min_required:
            try:
                aligned = align_completed_weekly_supertrend(daily_df, weekly_df, config.st_config)
                result["weekly_st_trend_completed"] = aligned["st_trend"]
                result["weekly_supertrend"] = aligned["supertrend"]
                weekly_usable = True
            except (ValueError, KeyError):
                pass

    if not weekly_usable:
        # Fallback: compute daily ST as anchor (no weekly)
        try:
            st_result = calculate_supertrend(daily_df, config.st_config)
            result["weekly_st_trend_completed"] = st_result["st_trend"]
            result["weekly_supertrend"] = st_result["supertrend"]
        except ValueError:
            # Not enough data for ST warmup — use EMA trend
            ema_fast = daily_df["close"].ewm(
                span=config.ema_fast, adjust=False, min_periods=config.ema_fast
            ).mean()
            ema_slow = daily_df["close"].ewm(
                span=config.ema_slow, adjust=False, min_periods=config.ema_slow
            ).mean()
            result["weekly_st_trend_completed"] = (ema_fast > ema_slow).astype(float).where(
                ema_fast.notna(), 0.0
            )
            result["weekly_supertrend"] = daily_df["close"]

    # Step 2: Daily confirmation
    result = build_confirmation_features(result, config)

    # Step 3: Regime features
    result = build_regime_features(result, config)

    # Step 4: Entry triggers
    result = build_entry_trigger_features(result, config)

    # Step 5: MTES conflict columns
    if mtes_frame is not None and len(mtes_frame) > 0:
        for col in ["mtes_direction", "mtes_regime", "mtes_conflict", "timeframe_conflict"]:
            if col in mtes_frame.columns and col not in result.columns:
                # Align MTES to daily index
                mtes_aligned = mtes_frame[col].reindex(daily_df.index)
                result[col] = mtes_aligned.values

    # Meta columns
    result["trading_mode"] = mode
    result["transaction_cost_bps"] = config.transaction_cost_bps
    result["slippage_bps"] = config.slippage_bps

    return result


def generate_enhancement_signals(
    features: pd.DataFrame,
    entry_family: Literal["pullback", "breakout", "rsi_recovery", "macd_recovery"] = "pullback",
    config: Optional[EnhancementConfig] = None,
) -> pd.Series:
    """Generate -1/0/1 trading signals from enhancement features.

    Signal generation logic:
    1. Weekly ST anchor must agree (bull for longs, bear for shorts).
    2. Daily RangeFilter must confirm (if use_range_filter=True).
    3. Entry trigger must fire (pullback/breakout/RSI/MACD recovery).
    4. Regime filter must pass (if use_regime_filter=True).
    5. MTES conflict must not veto (if use_mtes_conflict_filter=True).
    6. Trading mode enforcement: no shorts in long_only mode.

    Parameters
    ----------
    features : pd.DataFrame
        Output from build_enhancement_features().
    entry_family : str
        Entry trigger family: "pullback", "breakout", "rsi_recovery", "macd_recovery".
    config : EnhancementConfig, optional
        Strategy configuration.

    Returns
    -------
    pd.Series
        Signal series: 1 (long), -1 (short), 0 (neutral).
    """
    if config is None:
        config = EnhancementConfig()

    st_trend = features["weekly_st_trend_completed"]
    rf_dir = features["rf_direction"]

    # Entry trigger
    trigger_map = {
        "pullback": "entry_pullback",
        "breakout": "entry_breakout",
        "rsi_recovery": "entry_rsi_recovery",
        "macd_recovery": "entry_macd_recovery",
    }
    trigger_col = trigger_map.get(entry_family, "entry_pullback")
    entry_trigger = features.get(trigger_col, False)

    # Regime filter
    if config.use_regime_filter and "regime_ok" in features.columns:
        regime_pass = features["regime_ok"]
    else:
        regime_pass = True

    # MTES conflict filter
    if config.use_mtes_conflict_filter:
        mtes_conflict = features.get("mtes_conflict", False)
        tf_conflict = features.get("timeframe_conflict", False)
        no_conflict = ~(mtes_conflict | tf_conflict)
    else:
        no_conflict = True

    # RangeFilter filter
    if config.use_range_filter:
        rf_agree = rf_dir != 0
    else:
        rf_agree = True

    # Bull conditions: ST bull + RF confirm + trigger + regime + no conflict
    bull = (st_trend > 0) & rf_agree & entry_trigger & regime_pass & no_conflict
    # Bear conditions: ST bear + RF confirm + trigger + regime + no conflict
    bear = (st_trend < 0) & rf_agree & entry_trigger & regime_pass & no_conflict

    # Trading mode enforcement
    mode_series = features.get("trading_mode")
    if mode_series is not None and not isinstance(mode_series, str):
        mode = str(mode_series.iloc[0]) if len(mode_series) > 0 else "long_only"
    else:
        mode = str(mode_series) if mode_series is not None else "long_only"
    if mode == "long_only":
        bear = pd.Series(False, index=features.index)

    # Build signal: 1=long, -1=short, 0=neutral
    signal_arr = np.zeros(len(features), dtype=np.float64)
    signal_arr[bull.values] = 1.0
    signal_arr[bear.values] = -1.0
    signal = pd.Series(signal_arr, index=features.index)

    return signal


# ─────────────────────────────────────────────────────────────────────────────
# Experiment matrix
# ─────────────────────────────────────────────────────────────────────────────


def build_experiment_matrix() -> list[dict]:
    """Build the Phase 03 experiment matrix.

    Experiments cover:
    - E1: Weekly ST only (baseline)
    - E2: Weekly ST + daily RF confirmation (baseline)
    - E3: E2 + regime filters
    - E4: E3 + EMA pullback entry
    - E5: E3 + breakout entry
    - E6: E3 + RSI recovery entry
    - E7: E3 + MACD recovery entry
    - E8: E4 + MTES conflict filter

    Returns
    -------
    list[dict]
        List of experiment configs with name, description, and config dict.
    """
    matrix = [
        {
            "name": "E1: Weekly ST only",
            "description": "Weekly SuperTrend anchor without confirmation",
            "config": EnhancementConfig(
                use_range_filter=False,
                use_regime_filter=False,
                use_mtes_conflict_filter=False,
            ),
        },
        {
            "name": "E2: Weekly ST + RF",
            "description": "Weekly ST + daily RangeFilter confirmation",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=False,
                use_mtes_conflict_filter=False,
            ),
        },
        {
            "name": "E3: ST + RF + Regime",
            "description": "E2 + ADX/Choppiness regime filters",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=True,
                use_mtes_conflict_filter=False,
            ),
        },
        {
            "name": "E4: ST + RF + Regime + Pullback",
            "description": "E3 + EMA pullback entry trigger",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=True,
                use_mtes_conflict_filter=False,
            ),
        },
        {
            "name": "E5: ST + RF + Regime + Breakout",
            "description": "E3 + Donchian breakout entry trigger",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=True,
                use_mtes_conflict_filter=False,
                ema_pullback_threshold=999,
            ),
        },
        {
            "name": "E6: ST + RF + Regime + RSI",
            "description": "E3 + RSI recovery entry trigger",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=True,
                use_mtes_conflict_filter=False,
                ema_pullback_threshold=999,
            ),
        },
        {
            "name": "E7: ST + RF + Regime + MACD",
            "description": "E3 + MACD recovery entry trigger",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=True,
                use_mtes_conflict_filter=False,
                ema_pullback_threshold=999,
            ),
        },
        {
            "name": "E8: ST + RF + Regime + Pullback + MTES",
            "description": "E4 + MTES conflict filter",
            "config": EnhancementConfig(
                use_range_filter=True,
                use_regime_filter=True,
                use_mtes_conflict_filter=True,
            ),
        },
    ]
    return matrix
