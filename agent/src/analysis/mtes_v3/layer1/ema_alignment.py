"""Layer 1: EMA Alignment Analyzer - EMA 排列分析

EMA 排列是趋势判断的重要指标，与 Ichimoku 互补：
- Ichimoku: 结构视角（云的位置）
- EMA: 动量视角（价格与均线的位置）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import numpy as np


@dataclass
class EMASignal:
    """EMA 信号"""
    trend: Literal["BULL", "BEAR", "NEUTRAL"]
    price_above_ema: bool  # 价格在 EMA 上方
    ema_bullish: bool      # EMA 多头排列 (short > mid > long)
    ema_bearish: bool      # EMA 空头排列 (short < mid < long)
    slope: Literal["UP", "DOWN", "FLAT"]  # EMA 斜率
    confidence: float


class EMAAnalyzer:
    """EMA 排列分析器

    使用三个周期的 EMA：
    - 短期: 9 期 (快速)
    - 中期: 21 期
    - 长期: 55 期 (标准)
    """

    def __init__(
        self,
        fast_period: int = 9,
        mid_period: int = 21,
        slow_period: int = 55
    ):
        self.fast_period = fast_period
        self.mid_period = mid_period
        self.slow_period = slow_period

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= self.slow_period

    def calculate(self, df: pd.DataFrame) -> dict:
        """计算 EMA 值"""
        close = df['close']

        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_mid = close.ewm(span=self.mid_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()

        return {
            "ema_fast": ema_fast,
            "ema_mid": ema_mid,
            "ema_slow": ema_slow
        }

    def analyze(self, df: pd.DataFrame) -> EMASignal:
        """完整 EMA 分析"""
        if not self.validate(df):
            return EMASignal(
                trend="NEUTRAL",
                price_above_ema=False,
                ema_bullish=False,
                ema_bearish=False,
                slope="FLAT",
                confidence=0.0
            )

        ema_values = self.calculate(df)
        ema_fast = ema_values["ema_fast"]
        ema_mid = ema_values["ema_mid"]
        ema_slow = ema_values["ema_slow"]

        current_close = df['close'].iloc[-1]
        current_fast = ema_fast.iloc[-1]
        current_mid = ema_mid.iloc[-1]
        current_slow = ema_slow.iloc[-1]

        # 判断 EMA 排列
        ema_bullish = (current_fast > current_mid > current_slow)
        ema_bearish = (current_fast < current_mid < current_slow)

        # 价格是否在 EMA 上方
        price_above_ema = current_close > current_mid

        # EMA 斜率（基于最近 5 根 bar）
        ema_slope = self._calculate_slope(ema_mid, lookback=5)

        # 计算置信度
        confidence = self._calculate_confidence(
            ema_bullish, ema_bearish,
            price_above_ema, ema_slope
        )

        # 综合趋势判断
        if ema_bullish and price_above_ema:
            trend = "BULL"
        elif ema_bearish and not price_above_ema:
            trend = "BEAR"
        elif ema_bullish or price_above_ema:
            trend = "BULL"
        elif ema_bearish or not price_above_ema:
            trend = "BEAR"
        else:
            trend = "NEUTRAL"

        return EMASignal(
            trend=trend,
            price_above_ema=price_above_ema,
            ema_bullish=ema_bullish,
            ema_bearish=ema_bearish,
            slope=ema_slope,
            confidence=confidence
        )

    def _calculate_slope(self, ema: pd.Series, lookback: int = 5) -> str:
        """计算 EMA 斜率"""
        if len(ema) < lookback:
            return "FLAT"

        recent = ema.iloc[-lookback:]
        first = recent.iloc[0]
        last = recent.iloc[-1]

        # 斜率计算
        pct_change = (last - first) / first * 100

        if pct_change > 0.5:
            return "UP"
        elif pct_change < -0.5:
            return "DOWN"
        else:
            return "FLAT"

    def _calculate_confidence(
        self,
        ema_bullish: bool,
        ema_bearish: bool,
        price_above_ema: bool,
        slope: str
    ) -> float:
        """计算置信度"""
        confidence = 0.3  # 基础置信度

        # 完整的 EMA 多头排列
        if ema_bullish:
            confidence += 0.25

        # 价格在 EMA 上方
        if price_above_ema:
            confidence += 0.20

        # EMA 上升斜率
        if slope == "UP":
            confidence += 0.15
        elif slope == "DOWN":
            confidence += 0.15  # 也加一点，用于下跌趋势

        return min(confidence, 1.0)
