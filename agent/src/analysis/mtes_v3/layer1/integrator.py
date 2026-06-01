"""
Layer 1 Integrator - Layer 1 整合器

整合 SMC、Elder 三重滤网、Ichimoku 三个子系统的信号。
"""
from typing import Optional
import pandas as pd

from ..base import TrendBias
from .smc_analyzer import SMCAnalyzer, MarketStructureResult
from .elder_screen import ElderTripleScreen, ElderSignal
from .ichimoku import IchimokuCloud, IchimokuSignal


class Layer1Integrator:
    """Layer 1 整合器"""

    def __init__(self):
        self.smc = SMCAnalyzer()
        self.elder = ElderTripleScreen()
        self.ichimoku = IchimokuCloud()

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= 60  # 需要足够的数据进行分析

    def analyze(self, df: pd.DataFrame) -> TrendBias:
        """整合 Layer 1 所有信号"""
        if not self.validate(df):
            return TrendBias(direction="NEUTRAL", confidence=0.0, signals={})

        # SMC 分析
        smc_result = self.smc.analyze(df)

        # Elder 三重滤网
        elder_result = self.elder.analyze(df)

        # Ichimoku
        ichimoku_result = self.ichimoku.analyze(df)

        # 综合判断
        direction_votes = {
            "BULL": 0,
            "BEAR": 0,
            "NEUTRAL": 0
        }
        total_confidence = 0.0

        # SMC 投票
        direction_votes[smc_result.trend] += 1
        total_confidence += 0.5 if smc_result.trend != "NEUTRAL" else 0.3

        # Elder 投票（基于第一滤网）
        elder_trend = elder_result.layer1_trend
        direction_votes[elder_trend] += 1
        total_confidence += 0.5 if elder_trend != "NEUTRAL" else 0.3

        # Ichimoku 投票
        direction_votes[ichimoku_result.trend] += 1
        total_confidence += ichimoku_result.confidence

        # 简单多数投票
        final_direction = max(direction_votes, key=direction_votes.get)
        avg_confidence = total_confidence / 3

        signals = {
            "smc": {
                "direction": smc_result.trend,
                "confidence": 0.5 if smc_result.trend != "NEUTRAL" else 0.3,
                "bos_confirmed": smc_result.bos_confirmed
            },
            "elder": {
                "direction": elder_trend,
                "confidence": 0.5 if elder_trend != "NEUTRAL" else 0.3,
                "layer2_pullback": elder_result.layer2_pullback,
                "layer3_trigger": elder_result.layer3_trigger,
                "rsi": elder_result.rsi_value
            },
            "ichimoku": {
                "direction": ichimoku_result.trend,
                "confidence": ichimoku_result.confidence,
                "price_above_cloud": ichimoku_result.price_above_cloud,
                "tenkan_above_kijun": ichimoku_result.tenkan_above_kijun,
                "chikou_above_price": ichimoku_result.chikou_above_price
            },
            "votes": direction_votes
        }

        return TrendBias(
            direction=final_direction,
            confidence=min(avg_confidence, 1.0),
            signals=signals
        )
