"""
Momentum Divergence Detector - 动量背离检测器

检测价格与 MACD 之间的背离信号。
"""
import pandas as pd
import numpy as np
from typing import Literal, Optional
from dataclasses import dataclass


@dataclass
class DivergenceResult:
    """背离检测结果"""
    detected: bool
    divergence_type: Optional[Literal["BULLISH", "BEARISH", "HIDDEN_BULL", "HIDDEN_BEAR"]]
    strength: float  # 0-1
    price_swing_high: Optional[float]
    price_swing_low: Optional[float]


class MomentumDivergenceDetector:
    """动量背离检测器"""

    def __init__(
        self,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        lookback: int = 50
    ):
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.lookback = lookback

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= self.lookback

    def _calculate_macd(self, df: pd.DataFrame) -> pd.Series:
        """计算 MACD 直方图"""
        close = df['close']
        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        return macd_line - signal_line

    def _find_local_extrema(self, series: pd.Series, window: int = 5) -> list:
        """识别局部极值点 - 向量化优化版本"""
        values = series.values
        n = len(values)

        # 向量化计算 rolling max/min
        rolling_max = pd.Series(values).rolling(window * 2 + 1, center=True).max()
        rolling_min = pd.Series(values).rolling(window * 2 + 1, center=True).min()

        extrema = []
        for i in range(window, n - window):
            # 检查是否是局部最高点
            if values[i] >= rolling_max.iloc[i]:
                extrema.append(('high', i, values[i]))
            # 检查是否是局部最低点
            elif values[i] <= rolling_min.iloc[i]:
                extrema.append(('low', i, values[i]))

        return extrema

    def analyze(self, df: pd.DataFrame) -> DivergenceResult:
        """检测背离"""
        if not self.validate(df):
            return DivergenceResult(
                detected=False,
                divergence_type=None,
                strength=0.0,
                price_swing_high=None,
                price_swing_low=None
            )

        # 使用最近 lookback 根数据
        df_subset = df.tail(self.lookback).copy()
        close = df_subset['close']
        macd_hist = self._calculate_macd(df_subset)

        # 找价格和 MACD 的极值点
        price_extrema = self._find_local_extrema(close)
        macd_extrema = self._find_local_extrema(macd_hist)

        if len(price_extrema) < 2 or len(macd_extrema) < 2:
            return DivergenceResult(
                detected=False,
                divergence_type=None,
                strength=0.0,
                price_swing_high=None,
                price_swing_low=None
            )

        # 获取最近两个极值点
        price_highs = [(i, p) for t, i, p in price_extrema if t == 'high'][-2:]
        price_lows = [(i, p) for t, i, p in price_extrema if t == 'low'][-2:]
        macd_highs = [(i, p) for t, i, p in macd_extrema if t == 'high'][-2:]
        macd_lows = [(i, p) for t, i, p in macd_extrema if t == 'low'][-2:]

        if len(price_highs) < 2 or len(macd_highs) < 2:
            return DivergenceResult(
                detected=False,
                divergence_type=None,
                strength=0.0,
                price_swing_high=None,
                price_swing_low=None
            )

        # 顶背离：价格更高但 MACD 更低
        if len(price_highs) >= 2:
            price_high_1, price_high_2 = price_highs[0][1], price_highs[1][1]
            macd_high_1, macd_high_2 = macd_highs[0][1], macd_highs[1][1]

            if price_high_2 > price_high_1 and macd_high_2 < macd_high_1:
                strength = min(abs(macd_high_1 - macd_high_2) / abs(macd_high_1 + 1e-10), 1.0)
                return DivergenceResult(
                    detected=True,
                    divergence_type="BEARISH",
                    strength=strength,
                    price_swing_high=price_high_2,
                    price_swing_low=None
                )

        # 底背离：价格更低但 MACD 更高
        if len(price_lows) >= 2:
            price_low_1, price_low_2 = price_lows[0][1], price_lows[1][1]
            macd_low_1, macd_low_2 = macd_lows[0][1], macd_lows[1][1]

            if price_low_2 < price_low_1 and macd_low_2 > macd_low_1:
                strength = min(abs(macd_low_2 - macd_low_1) / abs(macd_low_1 + 1e-10), 1.0)
                return DivergenceResult(
                    detected=True,
                    divergence_type="BULLISH",
                    strength=strength,
                    price_swing_high=None,
                    price_swing_low=price_low_2
                )

        return DivergenceResult(
            detected=False,
            divergence_type=None,
            strength=0.0,
            price_swing_high=None,
            price_swing_low=None
        )
