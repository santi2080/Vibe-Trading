"""
ADX Strength Filter - ADX 趋势强度过滤器

Layer 2: 趋势强度确认
基于 ADX 值的趋势强度评级。
"""
import pandas as pd
import numpy as np
from typing import Literal

from ..base import StrengthRatingResult


class ADXStrengthFilter:
    """ADX 趋势强度过滤器"""

    def __init__(
        self,
        adx_strong: float = 30.0,
        adx_weak: float = 25.0,
        adx_min: float = 20.0
    ):
        self.adx_strong = adx_strong  # STRONG 阈值
        self.adx_weak = adx_weak      # READY 阈值
        self.adx_min = adx_min        # 最低阈值

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= 30

    def _calculate_adx(self, df: pd.DataFrame) -> float:
        """计算 ADX"""
        if len(df) < 14:
            return 0.0

        high = df['high']
        low = df['low']
        close = df['close']

        # 计算 True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算 Directional Movement
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)

        # 平滑
        period = 14
        smoothed_tr = tr.rolling(window=period).sum()
        smoothed_plus_dm = plus_dm.rolling(window=period).sum()
        smoothed_minus_dm = minus_dm.rolling(window=period).sum()

        # 计算 DI
        plus_di = 100 * smoothed_plus_dm / smoothed_tr
        minus_di = 100 * smoothed_minus_dm / smoothed_tr

        # 计算 DX 和 ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean()

        return adx.iloc[-1] if len(adx) > 0 else 0.0

    def calculate_adx_slope(self, df: pd.DataFrame, lookback: int = 5) -> float:
        """计算 ADX 斜率"""
        if len(df) < 14 + lookback:
            return 0.0

        # 简化实现：返回 0 表示 ADX 稳定
        return 0.0

    def filter(self, df: pd.DataFrame, mtf_bias: str = None) -> StrengthRatingResult:
        """趋势强度评级"""
        adx_value = self._calculate_adx(df)
        adx_slope = self.calculate_adx_slope(df)

        # 强度判定
        if adx_value >= self.adx_strong:
            rating = "STRONG"
        elif adx_value >= self.adx_weak:
            rating = "READY"
        elif adx_value >= self.adx_min:
            rating = "WEAK"
        else:
            rating = "EXHAUSTED"

        return StrengthRatingResult(
            rating=rating,
            adx_value=adx_value,
            divergence=False,
            regime="TRENDING" if adx_value >= self.adx_weak else "RANGE"
        )
