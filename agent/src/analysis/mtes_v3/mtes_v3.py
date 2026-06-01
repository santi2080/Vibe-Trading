"""MTES v3 - Main Entry Point.

This module provides the main MTESv3 class that orchestrates all layers
for multi-timeframe evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal

import pandas as pd

from .base import (
    TrendBias,
    StrengthRatingResult,
    EntrySignal,
    MTESv3Result,
)
from .preprocessor import Preprocessor, PreprocessorConfig
from .layer1 import Layer1Integrator
from .layer2 import ADXStrengthFilter, MomentumDivergenceDetector
from .layer3 import EntryTiming


@dataclass
class MTESv3Config:
    """MTES v3 配置"""
    adx_prefilter_threshold: float = 20.0
    adx_strong_threshold: float = 30.0
    adx_ready_threshold: float = 25.0
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0


class MTESv3:
    """MTES v3 分层递进趋势系统

    架构:
    - Layer 0: 预过滤器 (ADX)
    - Layer 1: 大周期趋势锁定 (SMC + Elder + Ichimoku)
    - Layer 2: 趋势强度确认 (ADX + 背离)
    - Layer 3: 入场时机 (RSI + FVG + Range Filter)
    """

    def __init__(self, config: Optional[MTESv3Config] = None):
        """初始化 MTES v3"""
        self.config = config or MTESv3Config()

        # 初始化预过滤器
        self.preprocessor = Preprocessor(PreprocessorConfig(
            adx_threshold=self.config.adx_prefilter_threshold
        ))

        # Layer 1: 大周期趋势锁定
        self.layer1 = Layer1Integrator()

        # Layer 2: 趋势强度确认
        self.strength_filter = ADXStrengthFilter(
            adx_strong=self.config.adx_strong_threshold,
            adx_weak=self.config.adx_ready_threshold
        )
        self.divergence_detector = MomentumDivergenceDetector()

        # Layer 3: 入场时机
        self.entry_timing = EntryTiming(
            rsi_oversold=self.config.rsi_oversold,
            rsi_overbought=self.config.rsi_overbought
        )

    def analyze(self, df: pd.DataFrame, **kwargs) -> MTESv3Result:
        """完整 MTES v3 分析

        Args:
            df: OHLCV DataFrame
            **kwargs: 额外参数

        Returns:
            MTESv3Result
        """
        # ===== Layer 0: 预处理 =====
        prefilter_result = self.preprocessor.analyze(df)

        if not prefilter_result.passed:
            return self._create_insufficient_result(prefilter_result)

        adx_value = prefilter_result.adx_value

        # ===== Layer 1: 大周期趋势锁定 =====
        mtf_trend = self.layer1.analyze(df)

        # ===== Layer 2: 趋势强度确认 =====
        strength = self.strength_filter.filter(df, mtf_trend.direction)

        # 动量背离检测
        divergence = self.divergence_detector.analyze(df)

        # ===== Layer 3: 入场时机 =====
        entry = self.entry_timing.find_entry(
            df,
            mtf_trend.direction,
            strength.rating
        )

        # ===== 综合评分 =====
        final_score = self._calculate_final_score(mtf_trend, strength)
        final_confidence = self._calculate_final_confidence(
            mtf_trend, strength, adx_value, divergence
        )

        return MTESv3Result(
            passed_prefilter=True,
            mtf_trend=mtf_trend,
            strength=StrengthRatingResult(
                rating=strength.rating,
                adx_value=strength.adx_value,
                divergence=divergence.detected,
                regime=strength.regime
            ),
            entry=entry,
            final_score=final_score,
            final_confidence=final_confidence,
        )

    def _create_insufficient_result(self, prefilter_result) -> MTESv3Result:
        """创建预过滤失败的结果"""
        return MTESv3Result(
            passed_prefilter=False,
            mtf_trend=TrendBias(
                direction="NEUTRAL",
                confidence=0.0,
                signals={"prefilter_reason": prefilter_result.reason}
            ),
            strength=StrengthRatingResult(
                rating="EXHAUSTED",
                adx_value=prefilter_result.adx_value,
                divergence=False,
                regime="RANGE"
            ),
            entry=EntrySignal(signal="WAIT", reason="prefilter_failed"),
            final_score=0.0,
            final_confidence=0.0,
        )

    def _calculate_final_score(self, trend: TrendBias, strength) -> float:
        """计算最终评分 (-100 ~ +100)"""
        if trend.direction == "BULL":
            direction_score = 100
        elif trend.direction == "BEAR":
            direction_score = -100
        else:
            direction_score = 0

        strength_mult = {
            "STRONG": 1.0,
            "READY": 0.8,
            "WEAK": 0.5,
            "EXHAUSTED": 0.2
        }.get(strength.rating, 0.5)

        final_score = direction_score * strength_mult * trend.confidence
        return round(final_score, 2)

    def _calculate_final_confidence(self, trend: TrendBias, strength, adx_value: float, divergence) -> float:
        """计算最终置信度 (0-1)"""
        adx_factor = min(adx_value / 40.0, 1.0)
        trend_factor = trend.confidence
        strength_factor = {
            "STRONG": 1.0,
            "READY": 0.8,
            "WEAK": 0.5,
            "EXHAUSTED": 0.2
        }.get(strength.rating, 0.3)
        divergence_bonus = 0.1 if divergence.detected else 0

        confidence = (adx_factor * 0.25 + trend_factor * 0.35 +
                     strength_factor * 0.30 + divergence_bonus)

        return round(min(confidence, 1.0), 3)

    def analyze_batch(self, data_dict: dict[str, pd.DataFrame]) -> dict[str, MTESv3Result]:
        """批量分析多个品种"""
        results = {}
        for symbol, df in data_dict.items():
            results[symbol] = self.analyze(df)
        return results
