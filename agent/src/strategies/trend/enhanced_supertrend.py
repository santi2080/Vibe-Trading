"""Enhanced SuperTrend trend strategy adapter."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.analysis.enhanced_supertrend import EnhancedSuperTrend, TrendSignal

from .base import TrendResult, TrendStrategyBase, TrendStrategyConfig, clamp_confidence, clamp_signed_score


@dataclass(frozen=True)
class EnhancedSuperTrendStrategyConfig:
    """Configuration for the Enhanced SuperTrend trend adapter."""

    st_period: int = 10
    st_multiplier: float = 3.0
    adx_period: int = 14
    adx_threshold: float = 25.0
    tm_cci_period: int = 20
    tm_atr_period: int = 10
    tm_atr_mult: float = 1.0


class EnhancedSuperTrendStrategy(TrendStrategyBase):
    """Adapter around the packaged Enhanced SuperTrend indicator."""

    name = "enhanced_supertrend"

    def __init__(
        self,
        config: EnhancedSuperTrendStrategyConfig | None = None,
        indicator: EnhancedSuperTrend | None = None,
        strategy_config: TrendStrategyConfig | None = None,
    ) -> None:
        super().__init__(strategy_config=strategy_config)
        self.config = config or EnhancedSuperTrendStrategyConfig()
        self.indicator = indicator or EnhancedSuperTrend(
            st_period=self.config.st_period,
            st_multiplier=self.config.st_multiplier,
            adx_period=self.config.adx_period,
            adx_threshold=self.config.adx_threshold,
            tm_cci_period=self.config.tm_cci_period,
            tm_atr_period=self.config.tm_atr_period,
            tm_atr_mult=self.config.tm_atr_mult,
        )

    def _analyze_raw(self, df: pd.DataFrame) -> TrendSignal:
        return self.indicator.get_signal(df)

    def _normalize(self, raw: TrendSignal, df: pd.DataFrame) -> TrendResult:
        direction = self._direction(raw)
        confidence = clamp_confidence(float(raw.confidence))
        signed_score = clamp_signed_score(float(raw.direction) * confidence * 100.0)
        strength_rating = self._strength_rating(direction, confidence, float(raw.adx))
        readiness = self._readiness(direction, confidence, strength_rating)
        regime = "CHOPPY" if direction == "NEUTRAL" else "TRENDING"

        return TrendResult(
            direction=direction,
            confidence=confidence,
            signed_score=signed_score,
            strength_rating=strength_rating,
            readiness=readiness,
            regime=regime,
            passed_prefilter=None,
            components={
                "confidence": confidence * 100.0,
                "adx": float(raw.adx),
                "persistence": float(raw.bars_since_flip),
                "supertrend_direction": float(raw.supertrend_direction) * 100.0,
                "trend_magic_direction": float(raw.trend_magic_direction) * 100.0,
            },
            metadata={
                "source": "enhanced_supertrend",
                "trend": raw.trend,
                "adx": raw.adx,
                "supertrend_direction": raw.supertrend_direction,
                "trend_magic_direction": raw.trend_magic_direction,
                "bars_since_flip": raw.bars_since_flip,
            },
        )

    def get_required_bars(self) -> int:
        return max(
            self.config.st_period + 1,
            self.config.adx_period * 2,
            self.config.tm_cci_period,
            self.config.tm_atr_period,
        ) + 1

    @staticmethod
    def _direction(raw: TrendSignal):
        if raw.direction == 1 or raw.trend == "上涨":
            return "BULL"
        if raw.direction == -1 or raw.trend == "下跌":
            return "BEAR"
        return "NEUTRAL"

    @staticmethod
    def _strength_rating(direction: str, confidence: float, adx: float):
        if adx >= 30.0 and confidence >= 0.70:
            return "STRONG"
        if adx >= 25.0 and confidence >= 0.50:
            return "READY"
        if direction == "NEUTRAL" or confidence < 0.50:
            return "WEAK"
        return "UNKNOWN"

    @staticmethod
    def _readiness(direction: str, confidence: float, strength_rating: str):
        if direction != "NEUTRAL" and strength_rating in {"STRONG", "READY"} and confidence >= 0.50:
            return "READY"
        return "NOT_READY"
