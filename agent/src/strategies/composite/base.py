"""Composite strategy signal layer - TradingSignal contract and helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

# Signal direction mirrors TrendResult direction semantics (D-01)
SignalDirection = Literal["BULL", "BEAR", "NEUTRAL"]

# Signal status - signal validity for downstream consumption (D-02)
SignalStatus = Literal["VALID", "NO_SIGNAL", "FILTERED", "INVALID"]

# Signal readiness - execution readiness distinct from validity (D-02)
SignalReadiness = Literal["READY", "WAIT", "BLOCKED", "EXHAUSTED", "UNKNOWN"]


@dataclass(frozen=True)
class TradingSignal:
    """Canonical composite strategy signal output.

    Aggregates multiple trend strategy results into a unified signal contract
    consumed by downstream backtests, reports, and execution adapters.

    Direction semantics (D-01):
        BULL/BEAR/NEUTRAL align with trend evaluation, NOT execution actions.
        LONG/SHORT/WAIT are handled by execution adapters downstream.

    Status vs Readiness (D-02):
        - status: signal validity (VALID/NO_SIGNAL/FILTERED/INVALID)
        - readiness: execution readiness (READY/WAIT/BLOCKED/EXHAUSTED)

    Core scoring (D-03):
        - signal_score: -100..100, direction-aware strength
        - confidence: 0..1, signal reliability
        - components: dict[str, float], per-source contributions

    Explainability (D-04):
        - reasons: why the signal was generated
        - warnings: risk factors or concerns
        - source_results: serializable summaries from source strategies
        - metadata: extensible key-value data
    """

    direction: SignalDirection
    status: SignalStatus
    readiness: SignalReadiness
    signal_score: float = 0.0
    confidence: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Runtime validation: reject LONG/SHORT/WAIT at construction time (D-01)
        # PH08-DEFER-EXEC: direction uses BULL/BEAR/NEUTRAL only.
        if self.direction not in ("BULL", "BEAR", "NEUTRAL"):
            raise ValueError(
                f"TradingSignal.direction must be BULL/BEAR/NEUTRAL, got '{self.direction}'. "
                "Use execution adapters for LONG/SHORT/WAIT semantics."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a machine-readable dictionary.

        Stores source_results as TrendResult.to_dict() outputs (D-04).
        """
        return {
            "direction": self.direction,
            "status": self.status,
            "readiness": self.readiness,
            "signal_score": self.signal_score,
            "confidence": self.confidence,
            "components": self.components,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "source_results": self.source_results,
            "metadata": self.metadata,
        }

    @property
    def is_valid(self) -> bool:
        """Return True when status is VALID, False otherwise."""
        return self.status == "VALID"


def clamp_signal_score(value: float) -> float:
    """Clamp signal score to the canonical -100..100 range (PH08-CLAMP).

    Returns 0.0 for non-finite values (NaN, inf, -inf).
    """
    if not math.isfinite(value):
        return 0.0
    return float(max(-100.0, min(100.0, value)))


def clamp_signal_confidence(value: float) -> float:
    """Clamp confidence to the canonical 0..1 range (PH08-CLAMP).

    Returns 0.0 for non-finite values (NaN, inf, -inf).
    """
    if not math.isfinite(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))


def map_trend_readiness(trend_readiness: str) -> SignalReadiness:
    """Map TrendResult Readiness to SignalReadiness (PH08-MAP).

    Readiness mapping table:
        NOT_READY -> WAIT
        READY     -> READY
        EXHAUSTED -> EXHAUSTED
        UNKNOWN   -> UNKNOWN

    Invalid/unknown values default to WAIT.
    """
    mapping: dict[str, SignalReadiness] = {
        "NOT_READY": "WAIT",
        "READY": "READY",
        "EXHAUSTED": "EXHAUSTED",
        "UNKNOWN": "UNKNOWN",
    }
    return mapping.get(trend_readiness, "WAIT")
