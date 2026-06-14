"""MTES v4 trend strategy adapter.

Wraps LeanMTES (MTES V4 — Minimalist Trend Direction Indicator)
into the canonical TrendStrategyBase lifecycle so it can be used
in the composite backtest pipeline, watchlist scanner, and
benchmark comparisons.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.analysis.mtes_v4 import LeanMTES, LeanMTESConfig, TrendDirection, TrendStrength

from .base import (
    TrendResult,
    TrendStrategyBase,
    TrendStrategyConfig,
    clamp_confidence,
    clamp_signed_score,
)


@dataclass(frozen=True)
class MTESv4TrendStrategyConfig:
    """Configuration for the MTES v4 trend adapter."""

    required_bars: int = 100


class MTESv4TrendStrategy(TrendStrategyBase):
    """Adapter around LeanMTES (MTES V4).

    Maps LeanMTES.analyze() output into the canonical TrendResult
    consumed by CompositeTrendStrategy and CompositeBacktestSignalEngine.
    """

    name = "mtes_v4_trend"

    def __init__(
        self,
        config: MTESv4TrendStrategyConfig | None = None,
        mtes_config: LeanMTESConfig | None = None,
        evaluator: LeanMTES | None = None,
        strategy_config: TrendStrategyConfig | None = None,
    ) -> None:
        super().__init__(strategy_config=strategy_config)
        self.config = config or MTESv4TrendStrategyConfig()
        self.evaluator = evaluator or LeanMTES(mtes_config)

    # ── TrendStrategyBase lifecycle ────────────────────────────

    def _analyze_raw(self, df: pd.DataFrame):
        """Run LeanMTES and return its native result."""
        return self.evaluator.analyze(df)

    def _normalize(self, raw, df: pd.DataFrame) -> TrendResult:
        """Map LeanTrendResult fields into TrendResult."""
        direction = self._direction(raw.direction)
        confidence = clamp_confidence(float(raw.confidence))
        signed_score = clamp_signed_score(float(raw.final_score))
        strength_rating = self._strength_rating(raw.strength)
        readiness = self._readiness(raw.is_trending, direction, strength_rating)
        status = "NO_SIGNAL" if not raw.is_trending else "VALID"

        return TrendResult(
            direction=direction,
            confidence=confidence,
            signed_score=signed_score,
            status=status,
            strength_rating=strength_rating,
            readiness=readiness,
            regime="TRENDING" if raw.is_trending else "RANGING",
            passed_prefilter=raw.is_trending,
            components={
                "final_score": signed_score,
                "ichimoku_score": float(raw.ichimoku_score),
                "ema_score": float(raw.ema_score),
                "adx": float(raw.adx),
                "plus_di": float(raw.plus_di),
                "minus_di": float(raw.minus_di),
            },
            metadata={
                "source": "mtes_v4",
                "action_bias": raw.action_bias,
                "structure_event": raw.structure_event,
                "is_trending": raw.is_trending,
                "bars_analyzed": raw.bars_analyzed,
                "explanation": raw.explanation,
            },
        )

    def get_required_bars(self) -> int:
        return self.config.required_bars

    # ── Mapping helpers ────────────────────────────────────────

    @staticmethod
    def _direction(direction: TrendDirection) -> str:
        if isinstance(direction, TrendDirection):
            return direction.value
        return "NEUTRAL"

    @staticmethod
    def _strength_rating(strength: TrendStrength) -> str:
        if isinstance(strength, TrendStrength):
            return strength.value
        return "UNKNOWN"

    @staticmethod
    def _readiness(is_trending: bool, direction: str, strength_rating: str) -> str:
        if not is_trending:
            return "NOT_READY"
        if strength_rating in {"STRONG", "READY"} and direction != "NEUTRAL":
            return "READY"
        if strength_rating == "EXHAUSTED":
            return "EXHAUSTED"
        if strength_rating == "WEAK":
            return "NOT_READY"
        return "UNKNOWN"
