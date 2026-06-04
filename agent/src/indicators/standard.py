"""标准指标函数 - 策略层对外接口

所有策略只 import 这个文件，不直接依赖 ta 库实现。
用法：
    from agent.src.indicators.standard import ema, adx, rsi, atr, supertrend

标准输入：OHLCV DataFrame 或 Series
标准输出：pd.Series 或 Dict[str, pd.Series]
"""

from __future__ import annotations

import pandas as pd
from typing import Dict

from .adapter import (
    ema as _ema,
    sma as _sma,
    adx as _adx,
    macd as _macd,
    rsi as _rsi,
    stochastic as _stochastic,
    atr as _atr,
    bollinger_bands as _bollinger_bands,
    tr as _tr,
)
from .supertrend import supertrend as _supertrend, supertrend_signal


# ============================================================================
# 趋势指标
# ============================================================================


def ema(df: pd.DataFrame, length: int = 12) -> pd.Series:
    """指数移动平均 (EMA)

    Args:
        df: OHLCV DataFrame
        length: 周期（默认 12）

    Returns:
        EMA Series
    """
    return _ema(df["close"], length=length)


def sma(df: pd.DataFrame, length: int = 20) -> pd.Series:
    """简单移动平均 (SMA)

    Args:
        df: OHLCV DataFrame
        length: 周期（默认 20）

    Returns:
        SMA Series
    """
    return _sma(df["close"], length=length)


def adx(df: pd.DataFrame, length: int = 14) -> Dict[str, pd.Series]:
    """平均趋向指数 (ADX)

    Args:
        df: OHLCV DataFrame
        length: 周期（默认 14）

    Returns:
        Dict with keys: adx, plus_di, minus_di
    """
    return _adx(df["high"], df["low"], df["close"], length=length)


def macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, pd.Series]:
    """MACD

    Args:
        df: OHLCV DataFrame
        fast: 快线周期（默认 12）
        slow: 慢线周期（默认 26）
        signal: 信号线周期（默认 9）

    Returns:
        Dict with keys: macd, signal, histogram
    """
    return _macd(df["close"], fast=fast, slow=slow, signal=signal)


# ============================================================================
# 动量指标
# ============================================================================


def rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """相对强弱指数 (RSI)

    Args:
        df: OHLCV DataFrame
        length: 周期（默认 14）

    Returns:
        RSI Series (0-100)
    """
    return _rsi(df["close"], length=length)


def stochastic(
    df: pd.DataFrame, k: int = 14, d: int = 3
) -> Dict[str, pd.Series]:
    """随机指标 (Stochastic)

    Args:
        df: OHLCV DataFrame
        k: %K 周期（默认 14）
        d: %D 周期（默认 3）

    Returns:
        Dict with keys: k, d
    """
    return _stochastic(df["high"], df["low"], df["close"], k=k, d=d)


# ============================================================================
# 波动率指标
# ============================================================================


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """平均真实波幅 (ATR)

    Args:
        df: OHLCV DataFrame
        length: 周期（默认 14）

    Returns:
        ATR Series
    """
    return _atr(df["high"], df["low"], df["close"], length=length)


def bollinger_bands(
    df: pd.DataFrame, length: int = 20, num_std: float = 2.0
) -> Dict[str, pd.Series]:
    """布林带 (Bollinger Bands)

    Args:
        df: OHLCV DataFrame
        length: 周期（默认 20）
        num_std: 标准差倍数（默认 2.0）

    Returns:
        Dict with keys: upper, middle, lower, bandwidth, percent
    """
    return _bollinger_bands(df["close"], length=length, num_std=num_std)


def tr(df: pd.DataFrame) -> pd.Series:
    """True Range

    Args:
        df: OHLCV DataFrame

    Returns:
        True Range Series
    """
    return _tr(df["high"], df["low"], df["close"])


# ============================================================================
# 组合指标
# ============================================================================


def supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pd.DataFrame:
    """SuperTrend

    Args:
        df: OHLCV DataFrame
        period: ATR 周期（默认 10）
        multiplier: ATR 倍数（默认 3.0）

    Returns:
        DataFrame with columns: supertrend, direction, atr
    """
    return _supertrend(
        df["high"], df["low"], df["close"], period=period, multiplier=multiplier
    )


__all__ = [
    "ema",
    "sma",
    "adx",
    "macd",
    "rsi",
    "stochastic",
    "atr",
    "bollinger_bands",
    "tr",
    "supertrend",
    "supertrend_signal",
]
