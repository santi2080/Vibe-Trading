"""EMA Trend Strategy - Trend detection using dual EMA crossover."""

import pandas as pd
import numpy as np
from typing import Literal


def ema_trend(
    data: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
    confirm_period: int = 5,
) -> pd.DataFrame:
    """Calculate EMA trend indicators.

    Args:
        data: OHLCV DataFrame with DatetimeIndex.
        fast_period: Fast EMA period (default: 20).
        slow_period: Slow EMA period (default: 50).
        confirm_period: Bars to confirm trend.

    Returns:
        DataFrame with EMA columns added.
    """
    df = data.copy()

    # Calculate EMAs
    df["ema_fast"] = df["close"].ewm(span=fast_period, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=slow_period, adjust=False).mean()

    # EMA crossover signal
    df["ema_diff"] = df["ema_fast"] - df["ema_slow"]
    df["ema_cross"] = np.where(df["ema_diff"] > 0, 1, -1)
    df["ema_cross_change"] = df["ema_cross"].diff().fillna(0).astype(int)

    # Golden cross / Death cross
    df["golden_cross"] = df["ema_cross_change"] == 2
    df["death_cross"] = df["ema_cross_change"] == -2

    # Trend direction
    df["trend_up"] = (df["close"] > df["ema_fast"]) & (df["ema_fast"] > df["ema_slow"])
    df["trend_down"] = (df["close"] < df["ema_fast"]) & (df["ema_fast"] < df["ema_slow"])

    # EMA slope (momentum)
    df["ema_fast_slope"] = df["ema_fast"].diff()
    df["ema_slow_slope"] = df["ema_slow"].diff()

    # Trend strength (bars in current direction)
    df["trend_bars"] = 0
    for i in range(1, len(df)):
        if df["trend_up"].iloc[i]:
            df.iloc[i, df.columns.get_loc("trend_bars")] = (
                df["trend_bars"].iloc[i - 1] + 1 if df["trend_up"].iloc[i - 1] else 1
            )
        elif df["trend_down"].iloc[i]:
            df.iloc[i, df.columns.get_loc("trend_bars")] = (
                df["trend_bars"].iloc[i - 1] + 1 if df["trend_down"].iloc[i - 1] else 1
            )

    return df


def get_ema_signal(
    df: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
) -> dict:
    """Get current EMA trend signal.

    Args:
        df: DataFrame with EMA columns from ema_trend().
        fast_period: Fast EMA period (for reference).
        slow_period: Slow EMA period (for reference).

    Returns:
        Dict with trend signal information.
    """
    last = df.iloc[-1]

    if last["trend_up"]:
        direction = "UP"
        signal = "LONG"
        # Confidence based on EMA diff and trend consistency
        confidence = min(
            1.0, abs(last["ema_diff"]) / last["close"] * 10 + last["trend_bars"] / 20
        )
    elif last["trend_down"]:
        direction = "DOWN"
        signal = "SHORT"
        confidence = min(
            1.0, abs(last["ema_diff"]) / last["close"] * 10 + last["trend_bars"] / 20
        )
    else:
        direction = "SIDEWAYS"
        signal = "NEUTRAL"
        confidence = 0.3

    return {
        "trend": direction,
        "confidence": float(confidence),
        "ema_fast": float(last["ema_fast"]),
        "ema_slow": float(last["ema_slow"]),
        "ema_diff": float(last["ema_diff"]),
        "signal": signal,
        "golden_cross": bool(last["golden_cross"]),
        "death_cross": bool(last["death_cross"]),
        "trend_bars": int(last["trend_bars"]),
        "ema_fast_slope": float(last["ema_fast_slope"]),
    }


def detect_ema_entry(df: pd.DataFrame) -> dict:
    """Detect EMA crossover entry signals.

    Args:
        df: DataFrame with EMA columns from ema_trend().

    Returns:
        Dict with entry signal information.
    """
    if len(df) < 2:
        return {"entry": False, "direction": "NEUTRAL", "price": None, "reason": "Insufficient data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Golden cross entry
    if last["golden_cross"]:
        return {
            "entry": True,
            "direction": "LONG",
            "price": float(last["close"]),
            "reason": "Golden cross (EMA{} > EMA{})".format(
                int(prev.get("ema_fast", 0) / 0), int(prev.get("ema_slow", 0) / 0)
            ),
        }

    # Death cross entry
    if last["death_cross"]:
        return {
            "entry": True,
            "direction": "SHORT",
            "price": float(last["close"]),
            "reason": "Death cross (EMA{} < EMA{})".format(
                int(prev.get("ema_fast", 0) / 0), int(prev.get("ema_slow", 0) / 0)
            ),
        }

    return {"entry": False, "direction": "NEUTRAL", "price": None, "reason": "No crossover"}


class EMATrend:
    """EMA Trend Strategy Class."""

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        confirm_period: int = 5,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.confirm_period = confirm_period

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMA trend."""
        return ema_trend(
            data,
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            confirm_period=self.confirm_period,
        )

    def get_signal(self, data: pd.DataFrame) -> dict:
        """Get current signal."""
        df = self.calculate(data)
        return get_ema_signal(df, self.fast_period, self.slow_period)

    def get_entry(self, data: pd.DataFrame) -> dict:
        """Get entry signal."""
        df = self.calculate(data)
        return detect_ema_entry(df)
