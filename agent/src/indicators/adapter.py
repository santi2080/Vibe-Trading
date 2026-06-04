"""pandas-ta / ta 库适配层

thin wrapper：将 ta 库的输出转换为标准 Series/Dict，
策略层只看到这个文件，不直接依赖 ta 库实现。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Literal

from ta.trend import EMAIndicator, ADXIndicator, SMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import AverageTrueRange, BollingerBands

# ============================================================================
# 趋势指标
# ============================================================================


def ema(close: pd.Series, length: int = 12) -> pd.Series:
    """指数移动平均"""
    return EMAIndicator(close=close, window=length).ema_indicator()


def sma(close: pd.Series, length: int = 20) -> pd.Series:
    """简单移动平均"""
    return SMAIndicator(close=close, window=length).sma_indicator()


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
) -> dict[str, pd.Series]:
    """平均趋向指数 + 方向指标

    Returns:
        dict with keys: adx, plus_di, minus_di
    """
    ind = ADXIndicator(high=high, low=low, close=close, window=length)
    return {
        "adx": ind.adx(),
        "plus_di": ind.adx_pos(),
        "minus_di": ind.adx_neg(),
    }


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """MACD

    Returns:
        dict with keys: macd, signal, histogram
    """
    ind = MACD(close=close, window_fast=fast, window_slow=slow, window_sign=signal)
    return {
        "macd": ind.macd(),
        "signal": ind.macd_signal(),
        "histogram": ind.macd_diff(),
    }


# ============================================================================
# 动量指标
# ============================================================================


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """相对强弱指数"""
    return RSIIndicator(close=close, window=length).rsi()


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k: int = 14,
    d: int = 3,
) -> dict[str, pd.Series]:
    """随机指标

    Returns:
        dict with keys: k, d
    """
    ind = StochasticOscillator(
        high=high, low=low, close=close, window=k, smooth_k=d
    )
    return {
        "k": ind.stoch(),
        "d": ind.stoch_signal(),
    }


# ============================================================================
# 波动率指标
# ============================================================================


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
) -> pd.Series:
    """平均真实波幅"""
    return AverageTrueRange(
        high=high, low=low, close=close, window=length
    ).average_true_range()


def bollinger_bands(
    close: pd.Series,
    length: int = 20,
    num_std: float = 2.0,
) -> dict[str, pd.Series]:
    """布林带

    Returns:
        dict with keys: upper, middle, lower, bandwidth, percent
    """
    ind = BollingerBands(close=close, window=length, window_dev=num_std)
    return {
        "upper": ind.bollinger_hband(),
        "middle": ind.bollinger_mavg(),
        "lower": ind.bollinger_lband(),
        "bandwidth": ind.bollinger_wband(),
        "percent": ind.bollinger_pband(),
    }


# ============================================================================
# 辅助
# ============================================================================


def tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
