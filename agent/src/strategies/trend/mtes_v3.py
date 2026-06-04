"""MTES v3 trend strategy adapter."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.analysis.mtes_v3 import MTESv3, MTESv3Config, MTESv3Result

from .base import TrendResult, TrendStrategyBase, TrendStrategyConfig, clamp_confidence, clamp_signed_score


@dataclass(frozen=True)
class MTESv3TrendStrategyConfig:
    """Configuration for the MTES v3 trend adapter."""

    required_bars: int = 200


class MTESv3TrendStrategy(TrendStrategyBase):
    """Adapter around the layered MTES v3 analyzer."""

    name = "mtes_v3_trend"

    def __init__(
        self,
        config: MTESv3TrendStrategyConfig | None = None,
        mtes_config: MTESv3Config | None = None,
        evaluator: MTESv3 | None = None,
        strategy_config: TrendStrategyConfig | None = None,
    ) -> None:
        super().__init__(strategy_config=strategy_config)
        self.config = config or MTESv3TrendStrategyConfig()
        self.evaluator = evaluator or MTESv3(mtes_config)

    def _analyze_raw(self, df: pd.DataFrame) -> MTESv3Result:
        return self.evaluator.analyze(df)

    def _normalize(self, raw: MTESv3Result, df: pd.DataFrame) -> TrendResult:
        direction = self._direction(raw.mtf_trend.direction)
        confidence = clamp_confidence(float(raw.final_confidence))
        signed_score = clamp_signed_score(float(raw.final_score))
        strength_rating = self._strength_rating(raw.strength.rating)
        readiness = self._readiness(raw.passed_prefilter, direction, strength_rating)
        status = "NO_SIGNAL" if raw.passed_prefilter is False else "VALID"

        return TrendResult(
            direction=direction,
            confidence=confidence,
            signed_score=signed_score,
            status=status,
            strength_rating=strength_rating,
            readiness=readiness,
            regime=str(raw.strength.regime),
            passed_prefilter=raw.passed_prefilter,
            components={
                "final_score": signed_score,
                "trend_confidence": clamp_confidence(float(raw.mtf_trend.confidence)) * 100.0,
                "final_confidence": confidence * 100.0,
                "adx": float(raw.strength.adx_value),
                "divergence_penalty": -20.0 if raw.strength.divergence else 0.0,
            },
            metadata={
                "source": "mtes_v3",
                "mtf_trend": raw.mtf_trend.to_dict(),
                "strength": raw.strength.to_dict(),
                "entry": raw.entry.to_dict(),
                "passed_prefilter": raw.passed_prefilter,
            },
        )

    def get_required_bars(self) -> int:
        return self.config.required_bars

    @staticmethod
    def _direction(direction: str):
        return direction if direction in {"BULL", "BEAR", "NEUTRAL"} else "NEUTRAL"

    @staticmethod
    def _strength_rating(rating: str):
        return rating if rating in {"STRONG", "READY", "WEAK", "EXHAUSTED"} else "UNKNOWN"

    @staticmethod
    def _readiness(passed_prefilter: bool, direction: str, strength_rating: str):
        if passed_prefilter is False:
            return "NOT_READY"
        if strength_rating in {"STRONG", "READY"} and direction != "NEUTRAL":
            return "READY"
        if strength_rating == "EXHAUSTED":
            return "EXHAUSTED"
        if strength_rating == "WEAK":
            return "NOT_READY"
        return "UNKNOWN"
