"""SuperTrend 指标计算

基于 ATR 的 SuperTrend 实现，ta 库没有直接提供。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Literal

from .adapter import tr as true_range, atr


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """SuperTrend 指标

    Args:
        high: 最高价
        low: 最低价
        close: 收盘价
        period: ATR 周期（默认 10）
        multiplier: ATR 倍数（默认 3.0）

    Returns:
        DataFrame with columns:
            - supertrend: SuperTrend 值
            - direction: 方向 (1=多头, -1=空头)
            - atr: ATR 值
    """
    atr_val = atr(high, low, close, length=period)

    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(1, index=close.index, dtype=int)

    # 初始值
    supertrend.iloc[period] = lower_band.iloc[period]
    direction.iloc[period] = 1

    for i in range(period + 1, len(close)):
        prev_st = supertrend.iloc[i - 1]
        prev_dir = direction.iloc[i - 1]

        curr_upper = upper_band.iloc[i]
        curr_lower = lower_band.iloc[i]
        curr_close = close.iloc[i]

        if curr_close > prev_st:
            # 向上突破
            supertrend.iloc[i] = curr_lower
            direction.iloc[i] = 1
        else:
            # 向下突破
            supertrend.iloc[i] = curr_upper
            direction.iloc[i] = -1

    result = pd.DataFrame(
        {
            "supertrend": supertrend,
            "direction": direction,
            "atr": atr_val,
        },
        index=close.index,
    )
    return result


def supertrend_signal(df: pd.DataFrame) -> Literal["LONG", "SHORT", "NEUTRAL"]:
    """从 SuperTrend 方向列判断信号

    Args:
        df: supertrend() 返回的 DataFrame

    Returns:
        "LONG" / "SHORT" / "NEUTRAL"
    """
    if "direction" not in df.columns:
        return "NEUTRAL"
    direction = df["direction"].iloc[-1]
    if pd.isna(direction):
        return "NEUTRAL"
    if direction == 1:
        return "LONG"
    elif direction == -1:
        return "SHORT"
    return "NEUTRAL"
