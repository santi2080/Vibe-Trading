"""
Ichimoku Cloud - 一目均衡表实现

一目均衡表是一种综合趋势分析系统：
- 转换线 (Tenkan-sen): 短期趋势
- 基准线 (Kijun-sen): 中期趋势
- 先行跨带 A/B (Senkou Span A/B): 云带
- 延迟线 (Chikou Span): 趋势确认
"""
import pandas as pd
import numpy as np
from typing import Literal
from dataclasses import dataclass


@dataclass
class IchimokuSignal:
    """Ichimoku 信号"""
    trend: Literal["BULL", "BEAR", "NEUTRAL"]
    price_above_cloud: bool
    tenkan_above_kijun: bool
    cloud_bullish: bool  # Span A > Span B
    chikou_above_price: bool  # 延迟线确认
    cloud_thickness: float  # 云带厚度
    confidence: float


class IchimokuCloud:
    """Ichimoku 云图"""

    def __init__(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        displacement: int = 26
    ):
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.displacement = displacement

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= self.senkou_b_period + self.displacement + 2

    def calculate_tenkan(self, df: pd.DataFrame) -> pd.Series:
        """转换线: (9期最高价 + 9期最低价) / 2"""
        high = df['high'].rolling(self.tenkan_period).max()
        low = df['low'].rolling(self.tenkan_period).min()
        return (high + low) / 2

    def calculate_kijun(self, df: pd.DataFrame) -> pd.Series:
        """基准线: (26期最高价 + 26期最低价) / 2"""
        high = df['high'].rolling(self.kijun_period).max()
        low = df['low'].rolling(self.kijun_period).min()
        return (high + low) / 2

    def calculate_senkou_a(self, df: pd.DataFrame) -> pd.Series:
        """先行跨带 A: (转换线 + 基准线) / 2，向前位移 26 期"""
        tenkan = self.calculate_tenkan(df)
        kijun = self.calculate_kijun(df)
        senkou_a = (tenkan + kijun) / 2
        return senkou_a.shift(self.displacement)

    def calculate_senkou_b(self, df: pd.DataFrame) -> pd.Series:
        """先行跨带 B: (52期最高价 + 52期最低价) / 2，向前位移 26 期"""
        high = df['high'].rolling(self.senkou_b_period).max()
        low = df['low'].rolling(self.senkou_b_period).min()
        senkou_b = (high + low) / 2
        return senkou_b.shift(self.displacement)

    def calculate_chikou(self, df: pd.DataFrame) -> pd.Series:
        """延迟线: 当前收盘价向后移 26 期（用于绘图）"""
        return df['close'].shift(-self.displacement)

    def calculate_chikou_comparison(self, df: pd.DataFrame) -> pd.Series:
        """Chikou 比较值: 当前价格 vs 26 期前价格

        正确理解 Chikou Span:
        - 将当前收盘价与 26 期前的价格比较
        - Chikou > 26期前价格 = 多头确认
        - Chikou < 26期前价格 = 空头确认
        """
        if len(df) <= self.displacement:
            return pd.Series([False] * len(df), index=df.index)

        current_close = df['close']
        past_close = df['close'].shift(self.displacement)
        return current_close > past_close

    def analyze(self, df: pd.DataFrame) -> IchimokuSignal:
        """完整 Ichimoku 分析"""
        if not self.validate(df):
            return IchimokuSignal(
                trend="NEUTRAL",
                price_above_cloud=False,
                tenkan_above_kijun=False,
                cloud_bullish=False,
                chikou_above_price=False,
                cloud_thickness=0.0,
                confidence=0.0
            )

        # 计算各线
        tenkan = self.calculate_tenkan(df)
        kijun = self.calculate_kijun(df)
        senkou_a = self.calculate_senkou_a(df)
        senkou_b = self.calculate_senkou_b(df)
        chikou_comparison = self.calculate_chikou_comparison(df)

        # 当前值
        current_close = df['close'].iloc[-1]
        current_tenkan = tenkan.iloc[-1]
        current_kijun = kijun.iloc[-1]
        current_senkou_a = senkou_a.iloc[-1]
        current_senkou_b = senkou_b.iloc[-1]
        current_chikou_above = chikou_comparison.iloc[-1]

        # 云带当前值
        cloud_top = max(current_senkou_a, current_senkou_b)
        cloud_bottom = min(current_senkou_a, current_senkou_b)
        cloud_thickness = cloud_top - cloud_bottom

        # 各条件判断
        price_above_cloud = current_close > cloud_top
        price_below_cloud = current_close < cloud_bottom
        tenkan_above_kijun = current_tenkan > current_kijun
        tenkan_below_kijun = current_tenkan < current_kijun
        cloud_bullish = current_senkou_a > current_senkou_b
        cloud_bearish = current_senkou_a < current_senkou_b
        chikou_above_price = current_chikou_above

        # 计算置信度（修复后）
        confidence = 0.2  # 基础置信度

        # 价格在云上/下（最重要，占 0.25）
        if price_above_cloud:
            confidence += 0.25
        elif price_below_cloud:
            confidence += 0.25

        # TK 交叉（次重要，占 0.20）
        if tenkan_above_kijun:
            confidence += 0.20
        elif tenkan_below_kijun:
            confidence += 0.20

        # 云的颜色（次重要，占 0.15）
        if cloud_bullish:
            confidence += 0.15
        elif cloud_bearish:
            confidence += 0.15

        # 延迟线确认（确认信号，占 0.20）
        if chikou_above_price:
            confidence += 0.20

        # 综合判断趋势
        bullish_signals = sum([
            price_above_cloud,
            tenkan_above_kijun,
            cloud_bullish,
            chikou_above_price
        ])

        bearish_signals = sum([
            price_below_cloud,
            tenkan_below_kijun,
            cloud_bearish,
            not chikou_above_price
        ])

        if bullish_signals >= 3:
            trend = "BULL"
        elif bearish_signals >= 3:
            trend = "BEAR"
        else:
            trend = "NEUTRAL"

        return IchimokuSignal(
            trend=trend,
            price_above_cloud=price_above_cloud,
            tenkan_above_kijun=tenkan_above_kijun,
            cloud_bullish=cloud_bullish,
            chikou_above_price=chikou_above_price,
            cloud_thickness=cloud_thickness,
            confidence=min(confidence, 1.0)
        )
