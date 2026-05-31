"""
增强版 SuperTrend 趋势指示器

输出:
- trend: "上涨" | "下跌" | "震荡"
- confidence: 0.0 ~ 1.0

算法:
1. SuperTrend 判断方向
2. ADX >= 25 判断趋势强度
3. TrendMagic CCI 方向作为确认
4. 三者一致时确认趋势，否则震荡
5. 置信度 = ADX强度 * TrendMagic一致性 * 持续性
"""

from dataclasses import dataclass
from typing import Literal, Tuple

import pandas as pd
import numpy as np


TrendDirection = Literal[1, -1, 0]
TrendState = Literal["上涨", "下跌", "震荡"]


@dataclass
class TrendSignal:
    """趋势信号"""
    trend: TrendState
    direction: TrendDirection  # +1=上涨, -1=下跌, 0=震荡
    confidence: float  # 0.0 ~ 1.0

    # 详细指标
    adx: float = 0.0
    supertrend_direction: TrendDirection = 0
    trend_magic_direction: TrendDirection = 0
    bars_since_flip: int = 0


class EnhancedSuperTrend:
    """增强版 SuperTrend

    使用 SuperTrend + ADX + TrendMagic(CCI)：
    - SuperTrend 判断方向
    - ADX 判断趋势强度 (阈值 25)
    - TrendMagic CCI 方向作为确认
    - 三者综合输出趋势状态和置信度
    """

    def __init__(
        self,
        st_period: int = 10,
        st_multiplier: float = 3.0,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        # TrendMagic 参数
        tm_cci_period: int = 20,
        tm_atr_period: int = 10,
        tm_atr_mult: float = 1.0,
    ):
        self.st_period = st_period
        self.st_multiplier = st_multiplier
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.tm_cci_period = tm_cci_period
        self.tm_atr_period = tm_atr_period
        self.tm_atr_mult = tm_atr_mult

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算增强版 SuperTrend"""
        result = df.copy()

        # 1. 计算 SuperTrend 方向
        st_direction = self._calc_supertrend(df)
        result["st_direction"] = st_direction

        # 2. 计算 ADX
        adx, plus_di, minus_di = self._calc_adx(df)
        result["adx"] = adx
        result["plus_di"] = plus_di
        result["minus_di"] = minus_di

        # 3. 计算 TrendMagic CCI 方向
        tm_direction = self._calc_trend_magic(df)
        result["tm_direction"] = tm_direction

        # 4. 计算持续性（方向保持的K线数）
        persistence = self._calc_persistence(st_direction)
        result["persistence"] = persistence

        # 5. 计算置信度
        confidence = self._calc_confidence(adx, tm_direction, st_direction, persistence)
        result["confidence"] = confidence

        # 6. 最终趋势状态
        trend = self._calc_trend_state(st_direction, adx, tm_direction)
        result["trend"] = trend
        result["trend_code"] = trend.map({"上涨": 1, "下跌": -1, "震荡": 0})

        return result

    def get_signal(self, df: pd.DataFrame) -> TrendSignal:
        """获取当前趋势信号（最后一行）"""
        result = self.calculate(df)
        last = result.iloc[-1]

        return TrendSignal(
            trend=last["trend"],
            direction=int(last["trend_code"]),
            confidence=float(last["confidence"]),
            adx=float(last["adx"]),
            supertrend_direction=int(last["st_direction"]),
            trend_magic_direction=int(last["tm_direction"]),
            bars_since_flip=int(last["persistence"]),
        )

    def _calc_supertrend(self, df: pd.DataFrame) -> pd.Series:
        """计算 SuperTrend 方向"""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        # ATR
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr1[0], tr2[0], tr3[0] = 0, 0, 0
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = pd.Series(tr).rolling(window=self.st_period).mean().values

        # 基础带
        hl_avg = (high + low) / 2
        basic_ub = hl_avg + self.st_multiplier * atr
        basic_lb = hl_avg - self.st_multiplier * atr

        # 最终带
        final_ub = basic_ub.copy()
        final_lb = basic_lb.copy()
        direction = np.zeros(n)

        # 初始化：假设多头
        direction[self.st_period] = 1

        for i in range(self.st_period + 1, n):
            if basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]:
                final_ub[i] = basic_ub[i]
            else:
                final_ub[i] = final_ub[i-1]

            if basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]:
                final_lb[i] = basic_lb[i]
            else:
                final_lb[i] = final_lb[i-1]

            if direction[i-1] == 1:
                direction[i] = -1 if close[i] < final_ub[i] else 1
            else:
                direction[i] = 1 if close[i] > final_lb[i] else -1

        return pd.Series(direction, index=df.index)

    def _calc_adx(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算 ADX, +DI, -DI"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.adx_period).mean()

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        smooth_plus_dm = plus_dm.rolling(window=self.adx_period).mean()
        smooth_minus_dm = minus_dm.rolling(window=self.adx_period).mean()

        plus_di = 100 * (smooth_plus_dm / atr)
        minus_di = 100 * (smooth_minus_dm / atr)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(window=self.adx_period).mean()

        return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)

    def _calc_trend_magic(self, df: pd.DataFrame) -> pd.Series:
        """计算 TrendMagic CCI 方向

        CCI >= 0 → 上涨 (+1)
        CCI < 0  → 下跌 (-1)
        """
        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(window=self.tm_cci_period).mean()
        mad = tp.rolling(window=self.tm_cci_period).apply(
            lambda x: np.abs(x - x.mean()).mean(), raw=True
        )
        cci = (tp - sma_tp) / (0.015 * mad + 1e-10)

        direction = np.where(cci >= 0, 1, -1)
        return pd.Series(direction, index=df.index)

    def _calc_persistence(self, direction: pd.Series) -> pd.Series:
        """计算方向持续性（同一方向保持的K线数）"""
        n = len(direction)
        persistence = np.zeros(n)
        current_dir = 0
        current_count = 0

        for i in range(n):
            if direction.iloc[i] == current_dir:
                current_count += 1
            else:
                current_dir = direction.iloc[i]
                current_count = 1
            persistence[i] = current_count

        return pd.Series(persistence, index=direction.index)

    def _calc_confidence(
        self,
        adx: pd.Series,
        tm_direction: pd.Series,
        st_direction: pd.Series,
        persistence: pd.Series,
    ) -> pd.Series:
        """计算置信度

        - ADX 强度 (权重 40%)
        - TrendMagic 方向一致性 (权重 30%)
        - 持续性 (权重 30%)
        """
        # ADX 强度得分 (0 ~ 1)
        adx_score = ((adx - self.adx_threshold) / (40 - self.adx_threshold)).clip(0, 1)

        # TrendMagic 与 SuperTrend 方向一致性
        tm_alignment = (tm_direction == st_direction).astype(float)

        # 持续性得分 (0 ~ 1)
        persistence_score = (persistence / 5).clip(0, 0.8)

        # 加权平均
        confidence = 0.4 * adx_score + 0.3 * tm_alignment + 0.3 * persistence_score

        return confidence.clip(0, 1)

    def _calc_trend_state(
        self,
        st_direction: pd.Series,
        adx: pd.Series,
        tm_direction: pd.Series,
    ) -> pd.Series:
        """计算趋势状态

        规则：
        - ADX >= 25 且 SuperTrend 与 TrendMagic 方向一致 → 输出该方向
        - 否则 → 震荡
        """
        trend = pd.Series(index=st_direction.index, dtype=object)

        # 趋势条件：ADX >= 25 且 SuperTrend 与 TrendMagic 方向一致
        bull_mask = (adx >= self.adx_threshold) & (st_direction == 1) & (tm_direction == 1)
        bear_mask = (adx >= self.adx_threshold) & (st_direction == -1) & (tm_direction == -1)

        trend[bull_mask] = "上涨"
        trend[bear_mask] = "下跌"

        # 其他情况 → 震荡
        churn_mask = ~(bull_mask | bear_mask)
        trend[churn_mask] = "震荡"

        return trend


def quick_signal(df: pd.DataFrame) -> TrendSignal:
    """快速获取趋势信号（使用默认参数）"""
    indicator = EnhancedSuperTrend()
    return indicator.get_signal(df)
