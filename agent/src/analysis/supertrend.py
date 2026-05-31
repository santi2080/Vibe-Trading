"""Canonical SuperTrend calculation module.

This module provides:
- SuperTrendConfig: configuration dataclass
- calculate_supertrend(): full SuperTrend indicator on OHLCV DataFrame
- remove_supertrend_warmup(): trim convergence/warmup bars
- align_completed_weekly_supertrend(): no-lookahead weekly anchor on daily bars

Key truths
----------
- Final bands carry FORWARD statefully (not recomputed from scratch each bar).
- Trend flips only when close crosses the RELEVANT final band.
- Weekly anchor uses ONLY completed weekly bars (no same-week lookahead).
- supertrend = final_lower when bullish, final_upper when bearish.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SuperTrendConfig:
    """Configuration for SuperTrend calculation.

    Attributes
    ----------
    period : int
        ATR lookback period.  Default 10.
    multiplier : float
        ATR multiplier for band width.  Default 3.0.
    warmup_extra : int
        Extra warmup bars beyond the internal ATR convergence period.
        Default 100.
    atr_method : str
        "wilder" (default) uses ewm(alpha=1/period) — the canonical approach.
        "ema" uses ewm(span=period).
    """

    period: int = 10
    multiplier: float = 3.0
    warmup_extra: int = 100
    atr_method: str = "wilder"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Classic True Range: max of three deltas."""
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def _wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Wilder-style smoothed ATR (default SuperTrend method)."""
    tr = _true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _ema_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """EMA-based ATR (alternative)."""
    tr = _true_range(high, low, close)
    return tr.ewm(span=period, adjust=False, min_periods=period).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int, method: str) -> pd.Series:
    if method == "wilder":
        return _wilder_atr(high, low, close, period)
    if method == "ema":
        return _ema_atr(high, low, close, period)
    raise ValueError(f"Unknown atr_method={method!r}. Use 'wilder' or 'ema'.")


def _basic_bands(
    high: pd.Series, low: pd.Series, close: pd.Series, atr: pd.Series, multiplier: float
) -> tuple[pd.Series, pd.Series]:
    """Basic (non-stateful) SuperTrend bands.

    basic_upper = (high + low) / 2 + multiplier * ATR
    basic_lower = (high + low) / 2 - multiplier * ATR
    """
    mid = (high + low) / 2.0
    basic_upper = mid + multiplier * atr
    basic_lower = mid - multiplier * atr
    return basic_upper, basic_lower


# ---------------------------------------------------------------------------
# Stateful final bands
# ---------------------------------------------------------------------------

def _finalize_bands(
    basic_upper: pd.Series,
    basic_lower: pd.Series,
    close: pd.Series,
    atr: pd.Series,
    multiplier: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute stateful final upper/lower bands and trend state.

    State machine
    -------------
    - BULL (trend=1):  price is above final lower band
      • final_upper  = max(basic_upper, prev_final_upper)   [only moves up]
      • final_lower  = max(basic_lower, prev_final_lower)   [only moves up]

    - BEAR (trend=-1): price is below final upper band
      • final_upper  = min(basic_upper, prev_final_upper)   [only moves down]
      • final_lower  = min(basic_lower, prev_final_lower)   [only moves down]

    Trend flips
    -----------
    - Bull→Bear : close drops below final_lower
    - Bear→Bull : close rises above final_upper
    """
    n = len(basic_upper)
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    trend = np.full(n, np.nan)

    # Initialise first valid bar as BULL
    # We must wait until ATR is available, so scan from `period`
    started = False

    for i in range(n):
        if i < len(atr) and (atr.iloc[i] != atr.iloc[i] or atr.iloc[i] <= 0):
            # ATR not yet valid — leave NaN
            continue

        if not started:
            # First valid ATR bar: start in BULL state
            trend[i] = 1.0
            final_upper[i] = basic_upper.iloc[i]
            final_lower[i] = basic_lower.iloc[i]
            started = True
            continue

        prev_trend = trend[i - 1]
        prev_fu = final_upper[i - 1]
        prev_fl = final_lower[i - 1]

        bu = basic_upper.iloc[i]
        bl = basic_lower.iloc[i]
        c = close.iloc[i]

        if prev_trend == 1.0:
            # ── Bull state ──────────────────────────────────────────────
            # Final bands only move up
            fu = max(bu, prev_fu)
            fl = max(bl, prev_fl)

            # Flip to bear if close drops below final_lower
            if c < fl:
                trend[i] = -1.0
                fu = bu
                fl = bl
            else:
                trend[i] = 1.0
        else:
            # ── Bear state ─────────────────────────────────────────────
            # Final bands only move down
            fu = min(bu, prev_fu)
            fl = min(bl, prev_fl)

            # Flip to bull if close rises above final_upper
            if c > fu:
                trend[i] = 1.0
                fu = bu
                fl = bl
            else:
                trend[i] = -1.0

        final_upper[i] = fu
        final_lower[i] = fl

    fu_series = pd.Series(final_upper, index=basic_upper.index)
    fl_series = pd.Series(final_lower, index=basic_lower.index)
    trend_series = pd.Series(trend, index=close.index)

    return fu_series, fl_series, trend_series


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_supertrend(df: pd.DataFrame, config: SuperTrendConfig) -> pd.DataFrame:
    """Calculate SuperTrend on an OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must have DatetimeIndex and columns: open, high, low, close (volume optional).
    config : SuperTrendConfig
        period, multiplier, warmup_extra, atr_method.

    Returns
    -------
    pd.DataFrame
        Same index as ``df`` with columns:
        - st_atr
        - st_basic_upper
        - st_basic_lower
        - st_final_upper
        - st_final_lower
        - st_trend  (1.0 = bull, -1.0 = bear)
        - supertrend (final_lower when bull, final_upper when bear)
    """
    # ── Validate ──────────────────────────────────────────────────────────
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have a DatetimeIndex (timestamp index)")

    warmup = config.period * 3 + config.warmup_extra
    if len(df) < warmup + 1:
        raise ValueError(
            f"warmup period ({warmup}) exceeds available data ({len(df)} rows). "
            "Need at least warmup+1 bars."
        )

    # ── ATR ────────────────────────────────────────────────────────────────
    atr = _atr(
        df["high"].copy(),
        df["low"].copy(),
        df["close"].copy(),
        config.period,
        config.atr_method,
    ).rename("st_atr")

    # ── Basic bands ───────────────────────────────────────────────────────
    bu, bl = _basic_bands(
        df["high"], df["low"], df["close"], atr, config.multiplier
    )

    # ── Stateful final bands & trend ───────────────────────────────────────
    fu, fl, trend = _finalize_bands(bu, bl, df["close"], atr, config.multiplier)

    # ── SuperTrend line ────────────────────────────────────────────────────
    supertrend = pd.Series(np.nan, index=df.index)
    bull = trend == 1.0
    bear = trend == -1.0
    supertrend.loc[bull] = fl.loc[bull]
    supertrend.loc[bear] = fu.loc[bear]

    # ── Assemble result — preserve original OHLCV columns ──────────────────
    result = df.copy()
    result["st_atr"] = atr
    result["st_basic_upper"] = bu
    result["st_basic_lower"] = bl
    result["st_final_upper"] = fu
    result["st_final_lower"] = fl
    result["st_trend"] = trend
    result["supertrend"] = supertrend

    return result


def remove_supertrend_warmup(result: pd.DataFrame, config: SuperTrendConfig) -> pd.DataFrame:
    """Remove SuperTrend warmup/convergence bars from a result DataFrame.

    Parameters
    ----------
    result : pd.DataFrame
        Output of ``calculate_supertrend``.
    config : SuperTrendConfig
        Must match the config used to produce ``result``.

    Returns
    -------
    pd.DataFrame
        Trimmed to bars after the warmup period.
    """
    warmup = config.period * 3 + config.warmup_extra
    return result.iloc[warmup:].reset_index(drop=True)


def align_completed_weekly_supertrend(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    config: SuperTrendConfig,
) -> pd.DataFrame:
    """Align weekly SuperTrend to daily bars without lookahead.

    Implementation
    -------------
    1. Calculate weekly SuperTrend on ``weekly_df``.
    2. Lag weekly by 1 bar (completed bar, not the open bar).
    3. Merge weekly→daily backward (each daily bar gets the most-recent
       closed weekly bar that ended at or before it).
    4. Forward-fill aligned weekly values for continuity.

    This ensures a daily bar at any point in time uses only the SuperTrend
    value from the last COMPLETED weekly bar — no same-week lookahead.

    Parameters
    ----------
    daily_df : pd.DataFrame
        Daily OHLCV data (DatetimeIndex).
    weekly_df : pd.DataFrame
        Weekly OHLCV data resampled from daily (DatetimeIndex).
    config : SuperTrendConfig
        Passed to ``calculate_supertrend`` for weekly.

    Returns
    -------
    pd.DataFrame
        ``daily_df`` with additional columns prefixed ``w_`` containing
        weekly SuperTrend values.
    """
    if not isinstance(weekly_df.index, pd.DatetimeIndex):
        raise ValueError("weekly_df must have a DatetimeIndex")

    # Step 1: weekly SuperTrend
    weekly_st = calculate_supertrend(weekly_df, config)

    # Step 2: lag by 1 bar (use previous completed weekly bar)
    weekly_lagged = weekly_st.shift(1)

    # Step 3: backward merge onto daily
    result = daily_df.copy()
    for col in weekly_lagged.columns:
        result[f"w_{col}"] = np.nan

    for i, daily_ts in enumerate(daily_df.index):
        # Find all weekly bars that closed at or before this daily bar
        closed = weekly_lagged[weekly_lagged.index <= daily_ts]
        if len(closed) > 0:
            last = closed.iloc[-1]
            for col in weekly_lagged.columns:
                result.at[daily_ts, f"w_{col}"] = last[col]

    # Step 4: forward-fill for continuity within open weekly bars
    w_cols = [c for c in result.columns if c.startswith("w_")]
    result[w_cols] = result[w_cols].ffill()

    return result
