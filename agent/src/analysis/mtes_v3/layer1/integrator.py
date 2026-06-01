"""
Layer 1 Integrator - Layer 1 整合器

重构后的架构:
- Ichimoku (权重 0.5): 主要趋势判断，量化友好
- EMA 排列 (权重 0.3): 动量确认
- SMC Swing (权重 0.2): 辅助参考，仅提供价位信息

设计原则:
1. Ichimoku 主导：最可靠的量化指标
2. EMA 辅助：动量确认
3. SMC 次要：仅作为价位参考，不主导方向
"""

from __future__ import annotations

from typing import Optional
import pandas as pd

from ..base import TrendBias
from .smc_analyzer import SMCAnalyzer, MarketStructureResult
from .elder_screen import ElderTripleScreen
from .ichimoku import IchimokuCloud, IchimokuSignal
from .ema_alignment import EMAAnalyzer, EMASignal


class Layer1Integrator:
    """Layer 1 整合器 - Ichimoku 主导架构"""

    # 权重配置
    ICHIMOKU_WEIGHT = 0.50  # Ichimoku 主导
    EMA_WEIGHT = 0.30       # EMA 次要
    SMC_WEIGHT = 0.20       # SMC 辅助（仅价位）

    def __init__(self):
        # 核心指标
        self.ichimoku = IchimokuCloud()
        self.ema = EMAAnalyzer()

        # 辅助指标（不再主导方向）
        self.smc = SMCAnalyzer()
        self.elder = ElderTripleScreen()

    def validate(self, df: pd.DataFrame) -> bool:
        """验证数据是否足够"""
        return len(df) >= 60

    def analyze(self, df: pd.DataFrame) -> TrendBias:
        """整合 Layer 1 所有信号 - Ichimoku 主导架构"""
        if not self.validate(df):
            return TrendBias(direction="NEUTRAL", confidence=0.0, signals={})

        # ===== 主要指标分析 =====
        ichimoku_result = self.ichimoku.analyze(df)
        ema_result = self.ema.analyze(df)

        # ===== 辅助指标分析（仅作为参考） =====
        smc_result = self.smc.analyze(df)
        elder_result = self.elder.analyze(df)

        # ===== 加权投票 =====
        weighted_score = self._calculate_weighted_score(
            ichimoku_result,
            ema_result,
            smc_result
        )

        # ===== 最终方向判断 =====
        direction = self._determine_direction(weighted_score)
        confidence = self._calculate_confidence(
            ichimoku_result, ema_result, weighted_score
        )

        # ===== 构建信号字典 =====
        signals = self._build_signals(
            ichimoku_result, ema_result, smc_result, elder_result, weighted_score
        )

        return TrendBias(
            direction=direction,
            confidence=confidence,
            signals=signals
        )

    def _calculate_weighted_score(
        self,
        ichimoku: IchimokuSignal,
        ema: EMASignal,
        smc: MarketStructureResult
    ) -> dict:
        """计算加权分数

        Returns:
            dict with 'bull_score', 'bear_score', 'neutral_score'
        """
        # Ichimoku 分数
        if ichimoku.trend == "BULL":
            ichimoku_bull = ichimoku.confidence
            ichimoku_bear = 0.0
        elif ichimoku.trend == "BEAR":
            ichimoku_bull = 0.0
            ichimoku_bear = ichimoku.confidence
        else:
            ichimoku_bull = 0.3
            ichimoku_bear = 0.3

        # EMA 分数
        if ema.trend == "BULL":
            ema_bull = ema.confidence
            ema_bear = 0.0
        elif ema.trend == "BEAR":
            ema_bull = 0.0
            ema_bear = ema.confidence
        else:
            ema_bull = 0.3
            ema_bear = 0.3

        # SMC 分数（SMC 不主导方向，降低权重）
        if smc.trend == "BULL":
            smc_bull = smc.confidence * 0.5  # 降低 SMC 影响
            smc_bear = 0.0
        elif smc.trend == "BEAR":
            smc_bull = 0.0
            smc_bear = smc.confidence * 0.5
        else:
            smc_bull = 0.2
            smc_bear = 0.2

        # 加权计算
        bull_score = (
            ichimoku_bull * self.ICHIMOKU_WEIGHT +
            ema_bull * self.EMA_WEIGHT +
            smc_bull * self.SMC_WEIGHT
        )

        bear_score = (
            ichimoku_bear * self.ICHIMOKU_WEIGHT +
            ema_bear * self.EMA_WEIGHT +
            smc_bear * self.SMC_WEIGHT
        )

        return {
            "bull_score": bull_score,
            "bear_score": bear_score,
            "ichimoku": {
                "bull": ichimoku_bull,
                "bear": ichimoku_bear
            },
            "ema": {
                "bull": ema_bull,
                "bear": ema_bear
            },
            "smc": {
                "bull": smc_bull,
                "bear": smc_bear
            }
        }

    def _determine_direction(self, weighted_score: dict) -> str:
        """基于加权分数确定方向"""
        bull = weighted_score["bull_score"]
        bear = weighted_score["bear_score"]

        # 阈值判断
        STRONG_THRESHOLD = 0.6
        WEAK_THRESHOLD = 0.4

        if bull > STRONG_THRESHOLD and bull > bear:
            return "BULL"
        elif bear > STRONG_THRESHOLD and bear > bull:
            return "BEAR"
        elif bull > WEAK_THRESHOLD and bull > bear:
            return "BULL"
        elif bear > WEAK_THRESHOLD and bear > bull:
            return "BEAR"
        else:
            return "NEUTRAL"

    def _calculate_confidence(
        self,
        ichimoku: IchimokuSignal,
        ema: EMASignal,
        weighted_score: dict
    ) -> float:
        """计算综合置信度"""
        # 加权分数
        max_score = max(weighted_score["bull_score"], weighted_score["bear_score"])

        # Ichimoku 置信度加成（主导指标）
        ichimoku_bonus = ichimoku.confidence * 0.2

        # EMA 一致性加成
        ema_consistency = 0.1 if (
            (ichimoku.trend == "BULL" and ema.trend == "BULL") or
            (ichimoku.trend == "BEAR" and ema.trend == "BEAR")
        ) else 0.0

        confidence = max_score + ichimoku_bonus + ema_consistency

        return min(round(confidence, 3), 1.0)

    def _build_signals(
        self,
        ichimoku: IchimokuSignal,
        ema: EMASignal,
        smc: MarketStructureResult,
        elder: ElderTripleScreen,
        weighted_score: dict
    ) -> dict:
        """构建信号字典"""
        return {
            # === Ichimoku (主导) ===
            "ichimoku": {
                "direction": ichimoku.trend,
                "confidence": ichimoku.confidence,
                "price_above_cloud": ichimoku.price_above_cloud,
                "tenkan_above_kijun": ichimoku.tenkan_above_kijun,
                "cloud_bullish": ichimoku.cloud_bullish,
                "chikou_above_price": ichimoku.chikou_above_price,
                "weight": self.ICHIMOKU_WEIGHT,
                "weighted_score": {
                    "bull": weighted_score["ichimoku"]["bull"],
                    "bear": weighted_score["ichimoku"]["bear"]
                }
            },
            # === EMA (次要) ===
            "ema": {
                "direction": ema.trend,
                "confidence": ema.confidence,
                "price_above_ema": ema.price_above_ema,
                "ema_bullish": ema.ema_bullish,
                "slope": ema.slope,
                "weight": self.EMA_WEIGHT,
                "weighted_score": {
                    "bull": weighted_score["ema"]["bull"],
                    "bear": weighted_score["ema"]["bear"]
                }
            },
            # === SMC (辅助 - 仅价位参考) ===
            "smc": {
                "direction": smc.trend,  # 不主导
                "confidence": smc.confidence * 0.5,  # 降低影响力
                "bos_confirmed": smc.bos_confirmed,
                "mss_confirmed": smc.mss_confirmed,
                "last_swing_high": smc.last_swing_high,
                "last_swing_low": smc.last_swing_low,
                "weight": self.SMC_WEIGHT,
                "note": "SMC 仅提供价位参考，不主导方向判断"
            },
            # === Elder (参考) ===
            "elder": {
                "direction": elder.layer1_trend,
                "rsi": elder.rsi_value,
                "layer2_pullback": elder.layer2_pullback,
                "layer3_trigger": elder.layer3_trigger
            },
            # === 加权投票汇总 ===
            "votes": {
                "BULL": round(weighted_score["bull_score"], 3),
                "BEAR": round(weighted_score["bear_score"], 3),
                "ICHIMOKU_WEIGHT": self.ICHIMOKU_WEIGHT,
                "EMA_WEIGHT": self.EMA_WEIGHT,
                "SMC_WEIGHT": self.SMC_WEIGHT
            }
        }
