"""
Elder Triple Screen - Elder 三重滤网实现

Elder 三重滤网是一种多时间框架趋势确认系统：
- 第一滤网: MACD 柱状图斜率（周线级别趋势）
- 第二滤网: RSI 极值（回撤到极值区域）
- 第三滤网: Buy Stop 突破（入场触发）
"""
import pandas as pd
import numpy as np
from typing import Literal, Optional
from dataclasses import dataclass


@dataclass
class ElderSignal:
    """Elder 三重滤网信号"""
    layer1_trend: Literal["BULL", "BEAR", "NEUTRAL"]
    layer2_pullback: bool
    layer3_trigger: Literal["READY", "WAIT"]
    macd_histogram_slope: float
    rsi_value: float
    macd_histogram_values: list


class ElderTripleScreen:
    """Elder 三重滤网"""

    def __init__(
        self,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70
    ):
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= max(self.macd_slow, self.rsi_period) + 2

    def calculate_macd(self, df: pd.DataFrame) -> tuple:
        """计算 MACD"""
        close = df['close']
        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def calculate_macd_histogram_slope(self, histogram: pd.Series, lookback: int = 2) -> float:
        """计算 MACD 柱状图斜率"""
        if len(histogram) < lookback + 1:
            return 0.0
        recent = histogram.iloc[-lookback:]
        x = np.arange(len(recent))
        if len(recent) < 2:
            return 0.0
        slope = np.polyfit(x, recent.values, 1)[0]
        return slope

    def calculate_rsi(self, df: pd.DataFrame) -> float:
        """计算 RSI"""
        close = df['close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(span=self.rsi_period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=self.rsi_period, adjust=False).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def layer1_mtf_trend(self, df: pd.DataFrame) -> str:
        """第一滤网: MACD 柱状图斜率判断趋势方向"""
        _, _, histogram = self.calculate_macd(df)
        slope = self.calculate_macd_histogram_slope(histogram)

        if slope > 0:
            return "BULL"
        elif slope < 0:
            return "BEAR"
        return "NEUTRAL"

    def layer2_pullback_extremity(self, df: pd.DataFrame, mtf_trend: str) -> bool:
        """第二滤网: RSI 超卖超买检测"""
        rsi = self.calculate_rsi(df)

        if mtf_trend == "BULL" and rsi < self.rsi_oversold:
            return True
        elif mtf_trend == "BEAR" and rsi > self.rsi_overbought:
            return True
        return False

    def layer3_trigger(self, df: pd.DataFrame, pullback_low: float = None) -> str:
        """第三滤网: Buy Stop 突破执行"""
        if pullback_low is None:
            pullback_low = df['low'].iloc[-2] if len(df) >= 2 else df['low'].iloc[-1]

        current_high = df['high'].iloc[-1]
        trigger_price = pullback_low + (df['close'].iloc[-1] * 0.001)  # 0.1% above

        if current_high > trigger_price:
            return "READY"
        return "WAIT"

    def analyze(self, df: pd.DataFrame) -> ElderSignal:
        """完整三重滤网分析"""
        if not self.validate(df):
            return ElderSignal(
                layer1_trend="NEUTRAL",
                layer2_pullback=False,
                layer3_trigger="WAIT",
                macd_histogram_slope=0.0,
                rsi_value=50.0,
                macd_histogram_values=[]
            )

        # Layer 1
        layer1_trend = self.layer1_mtf_trend(df)

        # Layer 2
        layer2_pullback = self.layer2_pullback_extremity(df, layer1_trend)

        # Layer 3
        layer3_trigger = self.layer3_trigger(df)

        # 计算指标值
        _, _, histogram = self.calculate_macd(df)
        macd_histogram_slope = self.calculate_macd_histogram_slope(histogram)
        rsi_value = self.calculate_rsi(df)

        return ElderSignal(
            layer1_trend=layer1_trend,
            layer2_pullback=layer2_pullback,
            layer3_trigger=layer3_trigger,
            macd_histogram_slope=macd_histogram_slope,
            rsi_value=rsi_value,
            macd_histogram_values=histogram.tail(5).tolist()
        )
