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
    BaseLayer,
)
from .preprocessor import Preprocessor, PreprocessorConfig
from .layer1 import SMCAnalyzer


@dataclass
class MTESv3Config:
    """Configuration for MTES v3.

    Attributes:
        prefilter_config: Configuration for the preprocessor
        min_confidence: Minimum confidence required for a valid signal
        score_multiplier: Multiplier for final score calculation
    """
    prefilter_config: PreprocessorConfig = field(default_factory=PreprocessorConfig)
    min_confidence: float = 0.5
    score_multiplier: float = 1.0


class MTESv3:
    """Multi-Timeframe Evaluation System v3.

    A layered progressive trend analysis system that:
    - Layer 0: Pre-filters data using ADX
    - Layer 1: Identifies multi-timeframe trend using SMC
    - Layer 2: Confirms trend strength (placeholder)
    - Layer 3: Identifies entry timing (placeholder)
    """

    def __init__(self, config: Optional[MTESv3Config] = None):
        """Initialize MTES v3.

        Args:
            config: MTESv3 configuration (uses defaults if not provided)
        """
        self.config = config or MTESv3Config()

        # Initialize layers
        self.preprocessor = Preprocessor(self.config.prefilter_config)
        self.smc_analyzer = SMCAnalyzer()

    def analyze(self, df: pd.DataFrame, **kwargs) -> MTESv3Result:
        """Perform complete MTES v3 analysis.

        Args:
            df: OHLCV DataFrame with columns [open, high, low, close, volume]
            **kwargs: Additional arguments for specific layers

        Returns:
            MTESv3Result with trend analysis and entry signals
        """
        # Layer 0: Pre-filter
        prefilter_result = self.preprocessor.analyze(df)

        if not prefilter_result.passed:
            # Return neutral result if prefilter fails
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
                    regime="RANGE"
                ),
                entry=EntrySignal(signal="WAIT", reason="prefilter_failed"),
                final_score=0.0,
                final_confidence=0.0,
            )

        # Layer 1: SMC Market Structure Analysis
        smc_result = self.smc_analyzer.analyze(df)

        # Build trend bias from SMC result
        mtf_trend = TrendBias(
            direction=smc_result.trend,
            confidence=smc_result.confidence,
            signals={
                "bos_confirmed": smc_result.bos_confirmed,
                "mss_confirmed": smc_result.mss_confirmed,
                "swing_count": len(smc_result.swings),
                "last_swing_high": smc_result.last_swing_high,
                "last_swing_low": smc_result.last_swing_low,
            }
        )

        # Layer 2: Trend Strength (simplified using ADX)
        strength_rating = self._get_strength_rating(
            prefilter_result.adx_value,
            mtf_trend.direction
        )

        # Layer 3: Entry Signal (simplified based on trend)
        entry_signal = self._get_entry_signal(mtf_trend, strength_rating)

        # Calculate final score
        final_score = self._calculate_score(mtf_trend, strength_rating)
        final_confidence = self._calculate_confidence(
            mtf_trend,
            strength_rating,
            prefilter_result
        )

        return MTESv3Result(
            passed_prefilter=True,
            mtf_trend=mtf_trend,
            strength=strength_rating,
            entry=entry_signal,
            final_score=final_score,
            final_confidence=final_confidence,
        )

    def _get_strength_rating(
        self,
        adx_value: float,
        trend_direction: str
    ) -> StrengthRatingResult:
        """Determine strength rating from ADX.

        Args:
            adx_value: Current ADX value
            trend_direction: Current trend direction

        Returns:
            StrengthRatingResult
        """
        if adx_value >= 30:
            rating = "STRONG"
            regime = "TRENDING"
        elif adx_value >= 25:
            rating = "READY"
            regime = "TRENDING"
        elif adx_value >= 20:
            rating = "WEAK"
            regime = "TRANSITIONAL"
        else:
            rating = "EXHAUSTED"
            regime = "RANGE"

        return StrengthRatingResult(
            rating=rating,
            adx_value=adx_value,
            divergence=False,  # TODO: Implement divergence detection
            regime=regime,
        )

    def _get_entry_signal(
        self,
        trend: TrendBias,
        strength: StrengthRatingResult
    ) -> EntrySignal:
        """Generate entry signal based on trend and strength.

        Args:
            trend: Current trend bias
            strength: Current strength rating

        Returns:
            EntrySignal
        """
        # Only generate signals if trend is strong
        if strength.rating in ["STRONG", "READY"] and trend.direction in ["BULL", "BEAR"]:
            if trend.direction == "BULL":
                return EntrySignal(
                    signal="LONG",
                    reason=f"{strength.rating} BULL trend"
                )
            else:
                return EntrySignal(
                    signal="SHORT",
                    reason=f"{strength.rating} BEAR trend"
                )

        return EntrySignal(
            signal="WAIT",
            reason="insufficient_trend_strength"
        )

    def _calculate_score(
        self,
        trend: TrendBias,
        strength: StrengthRatingResult
    ) -> float:
        """Calculate final score.

        Score range: -100 (strong bear) to +100 (strong bull)

        Args:
            trend: Current trend bias
            strength: Current strength rating

        Returns:
            Final score
        """
        # Direction contribution: -100, 0, or +100
        if trend.direction == "BULL":
            direction_score = 100
        elif trend.direction == "BEAR":
            direction_score = -100
        else:
            direction_score = 0

        # Strength multiplier
        if strength.rating == "STRONG":
            strength_mult = 1.0
        elif strength.rating == "READY":
            strength_mult = 0.8
        elif strength.rating == "WEAK":
            strength_mult = 0.5
        else:
            strength_mult = 0.2

        # Confidence factor
        confidence_factor = trend.confidence

        final_score = direction_score * strength_mult * confidence_factor

        return round(final_score, 2)

    def _calculate_confidence(
        self,
        trend: TrendBias,
        strength: StrengthRatingResult,
        prefilter_result: any
    ) -> float:
        """Calculate final confidence.

        Args:
            trend: Current trend bias
            strength: Current strength rating
            prefilter_result: Preprocessor result

        Returns:
            Final confidence (0-1)
        """
        # Base confidence from prefilter
        adx_factor = min(prefilter_result.adx_value / 40.0, 1.0)  # Normalize to 40

        # Trend confidence
        trend_factor = trend.confidence

        # Strength factor
        if strength.rating == "STRONG":
            strength_factor = 1.0
        elif strength.rating == "READY":
            strength_factor = 0.8
        elif strength.rating == "WEAK":
            strength_factor = 0.5
        else:
            strength_factor = 0.2

        # Combined confidence
        confidence = (adx_factor * 0.3 + trend_factor * 0.4 + strength_factor * 0.3)

        return round(min(confidence, 1.0), 3)

    def analyze_batch(
        self,
        data_dict: dict[str, pd.DataFrame]
    ) -> dict[str, MTESv3Result]:
        """Analyze multiple symbols at once.

        Args:
            data_dict: Dictionary mapping symbol -> DataFrame

        Returns:
            Dictionary mapping symbol -> MTESv3Result
        """
        results = {}
        for symbol, df in data_dict.items():
            results[symbol] = self.analyze(df)
        return results
