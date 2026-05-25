"""ADX Trend Strategy - Trend strength using Average Directional Index."""

import pandas as pd
import numpy as np
from typing import Literal


def calculate_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calculate True Range.

    Args:
        high: High prices.
        low: Low prices.
        close: Close prices.

    Returns:
        True Range series.
    """
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def adx_trend(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ADX indicator.

    Args:
        data: OHLCV DataFrame with DatetimeIndex.
        period: ADX calculation period (default: 14).

    Returns:
        DataFrame with ADX columns added.
    """
    df = data.copy()
    n = len(df)

    if n < period * 2:
        df["adx"] = np.nan
        df["adx_pos"] = np.nan
        df["adx_neg"] = np.nan
        return df

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    # True Range
    tr = calculate_true_range(df["high"], df["low"], df["close"])

    # Directional Movement
    high_diff = np.diff(high, prepend=high[0])
    low_diff = -np.diff(low, prepend=low[0])

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)

    # Wilder's Smoothing
    alpha = 1.0 / period
    plus_dm_smooth = np.zeros(n)
    minus_dm_smooth = np.zeros(n)
    tr_smooth = np.zeros(n)

    # Initialize with sum
    plus_dm_smooth[period - 1] = np.nansum(plus_dm[:period])
    minus_dm_smooth[period - 1] = np.nansum(minus_dm[:period])
    tr_smooth[period - 1] = np.nansum(tr.iloc[:period].values)

    # Apply Wilder's smoothing
    for i in range(period, n):
        plus_dm_smooth[i] = plus_dm_smooth[i - 1] * (1 - alpha) + plus_dm[i] * alpha
        minus_dm_smooth[i] = minus_dm_smooth[i - 1] * (1 - alpha) + minus_dm[i] * alpha
        tr_smooth[i] = tr_smooth[i - 1] * (1 - alpha) + tr.iloc[i] * alpha

    # +DI and -DI
    df["adx_pos"] = 100 * plus_dm_smooth / np.maximum(tr_smooth, 1e-10)
    df["adx_neg"] = 100 * minus_dm_smooth / np.maximum(tr_smooth, 1e-10)

    # DX
    dx = 100 * np.abs(df["adx_pos"] - df["adx_neg"]) / (df["adx_pos"] + df["adx_neg"] + 1e-10)

    # ADX (Wilder's smoothing of DX)
    df["adx"] = dx.rolling(period).mean()
    for i in range(period * 2, n):
        if pd.notna(df["adx"].iloc[i - 1]) and pd.notna(dx.iloc[i]):
            df["adx"].iloc[i] = df["adx"].iloc[i - 1] * (1 - alpha) + dx.iloc[i] * alpha

    return df


def get_adx_signal(df: pd.DataFrame, threshold: float = 25.0) -> dict:
    """Get current ADX trend signal.

    Args:
        df: DataFrame with ADX columns from adx_trend().
        threshold: ADX threshold for trending market (default: 25).

    Returns:
        Dict with trend signal information.
    """
    last = df.iloc[-1]

    adx = last["adx"] if pd.notna(last["adx"]) else 0
    pos = last["adx_pos"] if pd.notna(last["adx_pos"]) else 0
    neg = last["adx_neg"] if pd.notna(last["adx_neg"]) else 0

    if adx > threshold:
        if pos > neg:
            signal = "LONG"
            trend = "UP"
        else:
            signal = "SHORT"
            trend = "DOWN"
    else:
        signal = "NEUTRAL"
        trend = "SIDEWAYS"

    if adx < 20:
        strength = "WEAK"
    elif adx < 40:
        strength = "MODERATE"
    else:
        strength = "STRONG"

    return {
        "trend": trend,
        "adx": float(adx),
        "adx_pos": float(pos),
        "adx_neg": float(neg),
        "signal": signal,
        "strength": strength,
        "is_trending": bool(adx > threshold),
    }


def detect_adx_entry(df: pd.DataFrame, threshold: float = 25.0) -> dict:
    """Detect ADX-based entry signals.

    Args:
        df: DataFrame with ADX columns from adx_trend().
        threshold: ADX threshold for trending market.

    Returns:
        Dict with entry signal information.
    """
    if len(df) < 2:
        return {"entry": False, "direction": "NEUTRAL", "adx": 0, "reason": "Insufficient data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    adx = last["adx"] if pd.notna(last["adx"]) else 0
    prev_adx = prev["adx"] if pd.notna(prev["adx"]) else 0

    # Trend starting: ADX crosses above threshold
    if prev_adx < threshold <= adx:
        pos = last["adx_pos"]
        neg = last["adx_neg"]
        direction = "LONG" if pos > neg else "SHORT"
        return {
            "entry": True,
            "direction": direction,
            "price": float(last["close"]),
            "adx": float(adx),
            "reason": f"ADX crossed above {threshold} (trend started)",
        }

    # Strong trend continuation
    if adx > threshold:
        pos = last["adx_pos"]
        neg = last["adx_neg"]
        if pos > neg:
            return {
                "entry": False,
                "direction": "LONG",
                "adx": float(adx),
                "reason": f"Strong uptrend (ADX={adx:.1f})",
            }
        else:
            return {
                "entry": False,
                "direction": "SHORT",
                "adx": float(adx),
                "reason": f"Strong downtrend (ADX={adx:.1f})",
            }

    return {"entry": False, "direction": "NEUTRAL", "adx": float(adx), "reason": f"ADX < {threshold}"}


class ADXTrend:
    """ADX Trend Strategy Class."""

    def __init__(self, period: int = 14, threshold: float = 25.0):
        self.period = period
        self.threshold = threshold

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate ADX indicator."""
        return adx_trend(data, period=self.period)

    def get_signal(self, data: pd.DataFrame) -> dict:
        """Get current signal."""
        df = self.calculate(data)
        return get_adx_signal(df, self.threshold)

    def get_entry(self, data: pd.DataFrame) -> dict:
        """Get entry signal."""
        df = self.calculate(data)
        return detect_adx_entry(df, self.threshold)
