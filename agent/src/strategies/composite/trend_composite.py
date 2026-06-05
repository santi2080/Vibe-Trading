"""Composite trend strategy - aggregates multiple trend strategies into TradingSignal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from .base import (
    TradingSignal,
    clamp_signal_confidence,
    clamp_signal_score,
    map_trend_readiness,
)

if TYPE_CHECKING:
    from ..trend.base import TrendResult, TrendStrategyBase


@dataclass
class CompositeTrendConfig:
    """Configuration for CompositeTrendStrategy."""

    name: str = "composite_trend"


class CompositeTrendStrategy:
    """Aggregates multiple TrendStrategyBase outputs into a single TradingSignal.

    Minimal v0.1 composition:
        - Direction: unanimous BULL/BEAR -> that direction, otherwise NEUTRAL
        - Status: any INVALID -> INVALID, else all NO_SIGNAL -> NO_SIGNAL, else any FILTERED -> FILTERED, else VALID
        - Readiness: aggregate via map_trend_readiness, override to BLOCKED if status is INVALID
        - signal_score/confidence: mean of source values
        - components: merge source components dicts
    """

    name: str = "composite_trend"
    sources: list[TrendStrategyBase] = field(default_factory=list)

    def __init__(
        self,
        sources: list[TrendStrategyBase] | None = None,
        strategy_config: CompositeTrendConfig | None = None,
    ) -> None:
        self.sources = sources or []
        self.strategy_config = strategy_config or CompositeTrendConfig()

    def analyze(self, df: pd.DataFrame) -> TradingSignal:
        """Run all sources and aggregate into a TradingSignal."""
        # Validate input
        ok, reason = self.validate(df)
        if not ok:
            warning = reason or "validation failed"
            return TradingSignal(
                direction="NEUTRAL",
                status="INVALID",
                readiness="BLOCKED",
                signal_score=0.0,
                confidence=0.0,
                components={},
                reasons=[],
                warnings=[warning],
                source_results={},
                metadata={"strategy": self.strategy_config.name},
            )

        # Run all sources and aggregate
        source_results: dict[str, dict] = {}
        components: dict[str, float] = {}
        all_directions: list[str] = []
        all_scores: list[float] = []
        all_confidences: list[float] = []
        statuses: list[str] = []
        readinesies: list[str] = []
        all_warnings: list[str] = []
        all_reasons: list[str] = []

        for source in self.sources:
            try:
                result: TrendResult = source.analyze(df)
            except Exception as exc:
                # Catch any source exception, normalize to INVALID (PH08-SERIAL)
                source_results[source.name] = {"error": str(exc)}
                all_warnings.append(f"{source.name} failed: {exc}")
                statuses.append("INVALID")
                readinesies.append("BLOCKED")
                continue

            # Store serializable dict from to_dict() (D-04, PH08-SERIAL)
            source_results[source.name] = result.to_dict()

            # Aggregate components
            components.update(result.components)

            # Collect for aggregation
            all_directions.append(result.direction)
            all_scores.append(result.signed_score)
            all_confidences.append(result.confidence)
            statuses.append(result.status)
            readinesies.append(result.readiness)
            all_warnings.extend(result.warnings)

            # Add reason for directional sources
            if result.direction != "NEUTRAL":
                all_reasons.append(f"{source.name}: {result.direction}")

        # Aggregate direction (minimal v0.1)
        direction = self._aggregate_direction(all_directions)

        # Aggregate status
        signal_status = self._aggregate_status(statuses)

        # Aggregate readiness
        readiness = self._aggregate_readiness(readinesies, signal_status)

        # Aggregate scores
        signal_score = clamp_signal_score(sum(all_scores) / len(all_scores)) if all_scores else 0.0
        confidence = clamp_signal_confidence(sum(all_confidences) / len(all_confidences)) if all_confidences else 0.0

        return TradingSignal(
            direction=direction,
            status=signal_status,
            readiness=readiness,
            signal_score=signal_score,
            confidence=confidence,
            components=components,
            reasons=all_reasons,
            warnings=all_warnings,
            source_results=source_results,
            metadata={"strategy": self.strategy_config.name},
        )

    def validate(self, df: pd.DataFrame) -> tuple[bool, str | None]:
        """Validate the minimum OHLC input contract."""
        if df.empty:
            return False, "empty dataframe"

        required = {"open", "high", "low", "close"}
        columns = set(df.columns)
        missing = required - columns
        if missing:
            return False, f"missing columns: {sorted(missing)}"

        return True, None

    def _aggregate_direction(self, directions: list[str]) -> str:
        """Aggregate direction: unanimous -> that direction, else NEUTRAL."""
        if not directions:
            return "NEUTRAL"
        unique = set(directions)
        if unique == {"BULL"}:
            return "BULL"
        if unique == {"BEAR"}:
            return "BEAR"
        return "NEUTRAL"

    def _aggregate_status(self, statuses: list[str]) -> str:
        """Aggregate status: any INVALID -> INVALID, else all NO_SIGNAL -> NO_SIGNAL, else any FILTERED -> FILTERED, else VALID."""
        if "INVALID" in statuses:
            return "INVALID"
        if all(s == "NO_SIGNAL" for s in statuses):
            return "NO_SIGNAL"
        if "FILTERED" in statuses:
            return "FILTERED"
        return "VALID"

    def _aggregate_readiness(self, readinesies: list[str], signal_status: str) -> str:
        """Aggregate readiness: map sources, override to BLOCKED if INVALID."""
        if signal_status == "INVALID":
            return "BLOCKED"
        if not readinesies:
            return "UNKNOWN"
        # Use most restrictive readiness (EXHAUSTED > WAIT > UNKNOWN > READY)
        priority = {"EXHAUSTED": 3, "WAIT": 2, "UNKNOWN": 1, "READY": 0}
        mapped = [map_trend_readiness(r) for r in readinesies]
        return max(mapped, key=lambda r: priority.get(r, 0))
