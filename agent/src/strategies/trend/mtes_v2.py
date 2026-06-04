"""MTES v2 trend strategy adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.analysis.major_trend_evaluator import (
    DIRECTION_PERIODS,
    MajorTrendConfig,
    MajorTrendEvaluator,
    MajorTrendResult,
    resolve_asset_class,
)

from .base import TrendResult, TrendStrategyBase, TrendStrategyConfig, clamp_confidence, clamp_signed_score


@dataclass(frozen=True)
class MTESv2TrendStrategyConfig:
    """Configuration for the MTES v2 trend adapter."""

    asset_class: str = "stock"
    base_timeframe: str = "1d"
    higher_timeframe_name: str = "1w"


class MTESv2TrendStrategy(TrendStrategyBase):
    """Adapter around :class:`MajorTrendEvaluator`."""

    name = "mtes_v2_trend"

    def __init__(
        self,
        config: MTESv2TrendStrategyConfig | None = None,
        mtes_config: MajorTrendConfig | None = None,
        evaluator: MajorTrendEvaluator | None = None,
        strategy_config: TrendStrategyConfig | None = None,
        higher_timeframe: pd.DataFrame | None = None,
        cross_section_context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(strategy_config=strategy_config)
        self.config = config or MTESv2TrendStrategyConfig()
        self.evaluator = evaluator or MajorTrendEvaluator(mtes_config or MajorTrendConfig(asset_class=self.config.asset_class))
        self.higher_timeframe = higher_timeframe
        self.cross_section_context = cross_section_context

    def _analyze_raw(self, df: pd.DataFrame) -> MajorTrendResult:
        return self.evaluator.evaluate(
            df,
            asset_class=self.config.asset_class,
            higher_timeframe=self.higher_timeframe,
            base_timeframe=self.config.base_timeframe,
            higher_timeframe_name=self.config.higher_timeframe_name,
            cross_section_context=self.cross_section_context,
        )

    def _normalize(self, raw: MajorTrendResult, df: pd.DataFrame) -> TrendResult:
        confidence = clamp_confidence(float(raw.confidence))
        signed_score = self._signed_score(raw)
        strength_rating = self._strength_rating(signed_score, confidence)
        readiness = self._readiness(str(raw.direction), strength_rating)
        components = self._components(raw, signed_score, confidence)

        return TrendResult(
            direction=self._direction(str(raw.direction)),
            confidence=confidence,
            signed_score=signed_score,
            strength_rating=strength_rating,
            readiness=readiness,
            regime=str(raw.regime),
            passed_prefilter=None,
            explanation=str(raw.explanation),
            components=components,
            metadata={
                "source": "mtes_v2",
                "trend_state": raw.trend_state,
                "sub_scores": raw.sub_scores,
                "raw_scores": raw.raw_scores,
                "weights": raw.weights,
                "top_drivers": raw.top_drivers,
                "regime_flags": raw.regime_flags,
                "use_v2_scoring": raw.use_v2_scoring,
                "raw_metadata": raw.metadata,
            },
        )

    def get_required_bars(self) -> int:
        try:
            asset_class = resolve_asset_class(self.config.asset_class)
            return int(DIRECTION_PERIODS[asset_class]["long"])
        except Exception:
            return 200

    def _signed_score(self, raw: MajorTrendResult) -> float:
        direction_signal = float(getattr(raw, "direction_signal", 0.0) or 0.0)
        if direction_signal != 0.0 or raw.direction == "NEUTRAL":
            return clamp_signed_score(direction_signal)

        trend_score = float(raw.trend_score)
        if not raw.use_v2_scoring and raw.direction == "BEAR" and trend_score > 0:
            trend_score = -trend_score
        return clamp_signed_score(trend_score)

    def _strength_rating(self, signed_score: float, confidence: float):
        abs_score = abs(signed_score)
        if abs_score >= self.strategy_config.strong_score_threshold and confidence >= self.strategy_config.min_strong_confidence:
            return "STRONG"
        if abs_score >= self.strategy_config.ready_score_threshold and confidence >= self.strategy_config.min_ready_confidence:
            return "READY"
        if abs_score < self.strategy_config.weak_score_threshold or confidence < self.strategy_config.min_ready_confidence:
            return "WEAK"
        return "UNKNOWN"

    @staticmethod
    def _readiness(direction: str, strength_rating: str):
        if direction != "NEUTRAL" and strength_rating in {"STRONG", "READY"}:
            return "READY"
        if strength_rating == "EXHAUSTED":
            return "EXHAUSTED"
        return "NOT_READY"

    @staticmethod
    def _components(raw: MajorTrendResult, signed_score: float, confidence: float) -> dict[str, float]:
        components = {
            "direction": signed_score,
            "strength": float(raw.strength_score),
            "confidence": confidence * 100.0,
        }
        if raw.strength_components:
            components.update({key: float(value) for key, value in raw.strength_components.items()})
        else:
            components.update({key: float(value) for key, value in raw.sub_scores.items()})
        return components

    @staticmethod
    def _direction(direction: str):
        return direction if direction in {"BULL", "BEAR", "NEUTRAL"} else "NEUTRAL"
