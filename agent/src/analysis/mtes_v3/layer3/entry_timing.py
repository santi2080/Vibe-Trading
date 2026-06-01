"""
Entry Timing - 入场时机检测

Layer 3: 入场时机
基于 RSI 极值、FVG 回踩、Range Filter 信号入场。
"""
import pandas as pd
import numpy as np
from typing import Literal, Optional
from dataclasses import dataclass

from ..base import EntrySignal


class EntryTiming:
    """入场时机检测"""

    def __init__(
        self,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 65.0,
        rsi_period: int = 14
    ):
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.rsi_period = rsi_period

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= self.rsi_period + 5

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """计算 RSI"""
        close = df['close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(span=self.rsi_period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=self.rsi_period, adjust=False).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _detect_fvg(self, df: pd.DataFrame) -> Optional[dict]:
        """检测 Fair Value Gap (FVG)"""
        if len(df) < 3:
            return None

        # 检查最近 3 根 K 线
        for i in range(len(df) - 3):
            # 第一根 K 线
            high_1 = df['high'].iloc[i]
            low_1 = df['low'].iloc[i]
            # 第二根 K 线（缺口）
            high_2 = df['high'].iloc[i + 1]
            low_2 = df['low'].iloc[i + 1]
            # 第三根 K 线
            low_3 = df['low'].iloc[i + 2]
            high_3 = df['high'].iloc[i + 2]

            # 看涨 FVG：第三根 K 线与第一根 K 线之间有缺口
            if low_3 > high_1:
                return {
                    "type": "BULL",
                    "top": low_3,
                    "bottom": high_1,
                    "mid": (low_3 + high_1) / 2
                }
            # 看跌 FVG
            elif high_3 < low_1:
                return {
                    "type": "BEAR",
                    "top": low_1,
                    "bottom": high_3,
                    "mid": (low_1 + high_3) / 2
                }

        return None

    def _calculate_range_filter(self, df: pd.DataFrame, period: int = 20) -> dict:
        """计算 Range Filter 信号"""
        if len(df) < period:
            return {"direction": "NEUTRAL", "filter_value": 0}

        close = df['close']
        rolling_min = close.rolling(period).min()
        rolling_max = close.rolling(period).max()

        # Range Filter 公式
        range_ratio = (close - rolling_min) / (rolling_max - rolling_min + 1e-10)
        filter_value = rolling_min + range_ratio * (rolling_max - rolling_min)

        current = close.iloc[-1]
        current_filter = filter_value.iloc[-1]

        if current > current_filter:
            direction = "BULL"
        elif current < current_filter:
            direction = "BEAR"
        else:
            direction = "NEUTRAL"

        return {"direction": direction, "filter_value": current_filter}

    def find_entry(
        self,
        df: pd.DataFrame,
        trend_direction: str,
        strength_rating: str
    ) -> EntrySignal:
        """寻找入场时机"""
        rsi = self._calculate_rsi(df)
        rsi_value = rsi.iloc[-1]

        fvg = self._detect_fvg(df)
        range_filter = self._calculate_range_filter(df)

        signal = "WAIT"
        entry_price = None
        stop_loss = None
        reason = []

        atr = (df['high'].iloc[-14:].max() - df['low'].iloc[-14:].min()) / 14 if len(df) >= 14 else df['close'].iloc[-1] * 0.02

        if trend_direction == "BULL" and strength_rating in ["STRONG", "READY"]:
            # 做多条件
            if rsi_value < self.rsi_oversold:
                signal = "LONG"
                entry_price = df['close'].iloc[-1]
                stop_loss = df['low'].iloc[-5:].min() - atr
                reason.append("RSI oversold")
            elif fvg and fvg["type"] == "BULL":
                signal = "LONG"
                entry_price = fvg["mid"]
                stop_loss = fvg["bottom"] - atr
                reason.append("FVG bullish")

        elif trend_direction == "BEAR" and strength_rating in ["STRONG", "READY"]:
            # 做空条件
            if rsi_value > self.rsi_overbought:
                signal = "SHORT"
                entry_price = df['close'].iloc[-1]
                stop_loss = df['high'].iloc[-5:].max() + atr
                reason.append("RSI overbought")
            elif fvg and fvg["type"] == "BEAR":
                signal = "SHORT"
                entry_price = fvg["mid"]
                stop_loss = fvg["top"] + atr
                reason.append("FVG bearish")

        return EntrySignal(
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            reason=" | ".join(reason) if reason else None
        )
