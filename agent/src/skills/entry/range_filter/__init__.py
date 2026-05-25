"""Range Filter Entry Strategy - Dynamic range filter for entry signals."""

import pandas as pd
import numpy as np
from typing import Literal


def range_filter(
    data: pd.DataFrame,
    length: int = 14,
    mult: float = 2.618,
    use_wicks: bool = True,
) -> pd.DataFrame:
    """Calculate Range Filter indicator.

    Args:
        data: OHLCV DataFrame with DatetimeIndex.
        length: Range smoothing period (default: 14).
        mult: Range multiplier (default: 2.618, Fibonacci).
        use_wicks: Use high/low for range calculation (default: True).

    Returns:
        DataFrame with Range Filter columns added.
    """
    df = data.copy()

    # True Range calculation
    if use_wicks:
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift()).abs()
        tr3 = (df["low"] - df["close"].shift()).abs()
        rf_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    else:
        rf_range = df["close"] - df["open"]

    # Smoothed range
    rf_smooth_range = rf_range.rolling(length).mean()

    # Final range with multiplier
    rf_range_final = rf_smooth_range * mult

    # Smoothed source price
    rf_smooth_src = df["close"].rolling(length).mean()

    # Upper/Lower bands
    rf_upper = rf_smooth_src + rf_range_final
    rf_lower = rf_smooth_src - rf_range_final
    rf_filter = (rf_upper + rf_lower) / 2  # Center line

    # Direction detection
    rf_dir = pd.Series(0, index=df.index)  # 0: SIDEWAYS
    rf_dir[df["close"] > rf_upper] = 1  # 1: UP
    rf_dir[df["close"] < rf_lower] = -1  # -1: DOWN

    # Buffer (distance from mid as ratio 0-1)
    dist_from_mid = (df["close"] - rf_smooth_src).abs()
    band_half = rf_range_final / 2.0
    band_half = band_half.replace(0, np.nan)
    rf_buffer = (dist_from_mid / band_half).clip(0, 1).fillna(0)

    # Direction change detection
    rf_dir_change = rf_dir.diff().fillna(0).astype(int)

    # Direction turned bullish/bearish
    rf_turn_bull = (rf_dir_change == 1) & (rf_dir == 1)
    rf_turn_bear = (rf_dir_change == -1) & (rf_dir == -1)

    # Distance to bands
    rf_upper_dist = (rf_upper - df["close"]).abs()
    rf_lower_dist = (df["close"] - rf_lower).abs()

    df["rf_upper"] = rf_upper
    df["rf_lower"] = rf_lower
    df["rf_filter"] = rf_filter
    df["rf_smooth_src"] = rf_smooth_src
    df["rf_dir"] = rf_dir
    df["rf_buffer"] = rf_buffer
    df["rf_dir_change"] = rf_dir_change
    df["rf_turn_bull"] = rf_turn_bull
    df["rf_turn_bear"] = rf_turn_bear
    df["rf_range"] = rf_range_final
    df["rf_upper_dist"] = rf_upper_dist
    df["rf_lower_dist"] = rf_lower_dist

    return df


def get_rf_signal(df: pd.DataFrame) -> dict:
    """Get current Range Filter signal.

    Args:
        df: DataFrame with Range Filter columns from range_filter().

    Returns:
        Dict with current signal information.
    """
    last = df.iloc[-1]

    direction_map = {1: "UP", -1: "DOWN", 0: "SIDEWAYS"}

    if last["rf_dir"] == 1:
        signal = "LONG"
    elif last["rf_dir"] == -1:
        signal = "SHORT"
    else:
        signal = "NEUTRAL"

    return {
        "direction": direction_map.get(int(last["rf_dir"]), "SIDEWAYS"),
        "filter": float(last["rf_filter"]),
        "upper_band": float(last["rf_upper"]),
        "lower_band": float(last["rf_lower"]),
        "buffer": float(last["rf_buffer"]),
        "signal": signal,
        "turn_bull": bool(last["rf_turn_bull"]),
        "turn_bear": bool(last["rf_turn_bear"]),
    }


def detect_entry(df: pd.DataFrame) -> dict:
    """Detect Range Filter entry signals.

    Args:
        df: DataFrame with Range Filter columns from range_filter().

    Returns:
        Dict with entry signal information.
    """
    if len(df) < 2:
        return {
            "entry": False,
            "direction": "NEUTRAL",
            "price": None,
            "reason": "Insufficient data",
        }

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Long entry: direction turns bullish
    if last["rf_turn_bull"]:
        return {
            "entry": True,
            "direction": "LONG",
            "price": float(last["close"]),
            "stop": float(last["rf_lower"]),
            "reason": "Range Filter turned bullish",
        }

    # Short entry: direction turns bearish
    if last["rf_turn_bear"]:
        return {
            "entry": True,
            "direction": "SHORT",
            "price": float(last["close"]),
            "stop": float(last["rf_upper"]),
            "reason": "Range Filter turned bearish",
        }

    # Continue in trend
    if last["rf_dir"] == 1:
        return {
            "entry": False,
            "direction": "LONG",
            "price": float(last["close"]),
            "reason": "In uptrend",
        }
    elif last["rf_dir"] == -1:
        return {
            "entry": False,
            "direction": "SHORT",
            "price": float(last["close"]),
            "reason": "In downtrend",
        }

    return {
        "entry": False,
        "direction": "NEUTRAL",
        "price": float(last["close"]),
        "reason": "In range",
    }


def calculate_stop_loss(df: pd.DataFrame, atr_multiplier: float = 1.5) -> dict:
    """Calculate stop loss based on ATR.

    Args:
        df: DataFrame with RF columns and ATR.
        atr_multiplier: ATR multiplier for stop distance.

    Returns:
        Dict with stop loss levels.
    """
    last = df.iloc[-1]
    close = float(last["close"])

    # ATR-based stop
    atr = float(last.get("atr", last.get("rf_range", close * 0.01)))
    stop_dist = atr * atr_multiplier

    if last["rf_dir"] == 1:  # Long
        return {
            "stop_loss": close - stop_dist,
            "take_profit_1": close + stop_dist,
            "take_profit_2": close + stop_dist * 2,
            "risk_reward_1": 1.0,
            "risk_reward_2": 2.0,
        }
    elif last["rf_dir"] == -1:  # Short
        return {
            "stop_loss": close + stop_dist,
            "take_profit_1": close - stop_dist,
            "take_profit_2": close - stop_dist * 2,
            "risk_reward_1": 1.0,
            "risk_reward_2": 2.0,
        }

    return {"stop_loss": None, "take_profit_1": None, "take_profit_2": None}


class RangeFilter:
    """Range Filter Entry Strategy Class."""

    def __init__(
        self,
        length: int = 14,
        mult: float = 2.618,
        use_wicks: bool = True,
    ):
        self.length = length
        self.mult = mult
        self.use_wicks = use_wicks

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate Range Filter indicator."""
        return range_filter(
            data, length=self.length, mult=self.mult, use_wicks=self.use_wicks
        )

    def get_signal(self, data: pd.DataFrame) -> dict:
        """Get current signal."""
        df = self.calculate(data)
        return get_rf_signal(df)

    def get_entry(self, data: pd.DataFrame) -> dict:
        """Get entry signal."""
        df = self.calculate(data)
        entry = detect_entry(df)
        entry["stops"] = calculate_stop_loss(df)
        return entry
