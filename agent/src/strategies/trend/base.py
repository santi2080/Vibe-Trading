"""Canonical trend strategy result and base adapter lifecycle."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import pandas as pd

TrendDirection = Literal["BULL", "BEAR", "NEUTRAL"]
TrendStatus = Literal["VALID", "NO_SIGNAL", "INVALID", "FILTERED"]
StrengthRating = Literal["STRONG", "READY", "WEAK", "EXHAUSTED", "UNKNOWN"]
Readiness = Literal["READY", "NOT_READY", "EXHAUSTED", "UNKNOWN"]


@dataclass(frozen=True)
class TrendStrategyConfig:
    """Shared trend strategy thresholds."""

    min_valid_confidence: float = 0.30
    min_ready_confidence: float = 0.50
    min_strong_confidence: float = 0.70
    strong_score_threshold: float = 70.0
    ready_score_threshold: float = 40.0
    weak_score_threshold: float = 25.0


@dataclass(frozen=True)
class TrendResult:
    """Canonical trend strategy output consumed by higher-level strategies."""

    direction: TrendDirection
    confidence: float
    signed_score: float
    status: TrendStatus = "VALID"
    strength_rating: StrengthRating = "UNKNOWN"
    readiness: Readiness = "UNKNOWN"
    regime: str = "UNKNOWN"
    passed_prefilter: bool | None = None
    explanation: str = ""
    components: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Return true when this result is a valid consumable trend result."""
        return self.status == "VALID"

    @property
    def is_actionable_trend(self) -> bool:
        """Return true when trend is directional and ready for entry-layer checks."""
        return self.status == "VALID" and self.direction != "NEUTRAL" and self.readiness == "READY"

    def to_dict(self) -> dict[str, Any]:
        """Return a machine-readable representation."""
        return {
            "direction": self.direction,
            "confidence": self.confidence,
            "signed_score": self.signed_score,
            "status": self.status,
            "strength_rating": self.strength_rating,
            "readiness": self.readiness,
            "regime": self.regime,
            "passed_prefilter": self.passed_prefilter,
            "explanation": self.explanation,
            "components": self.components,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class TrendStrategyBase(ABC):
    """Base class for trend strategy adapters.

    Subclasses call an existing analyzer in ``_analyze_raw`` and normalize its
    native result into :class:`TrendResult` in ``_normalize``.
    """

    name: str = "trend_strategy"

    def __init__(self, strategy_config: TrendStrategyConfig | None = None) -> None:
        self.strategy_config = strategy_config or TrendStrategyConfig()

    def analyze(self, df: pd.DataFrame) -> TrendResult:
        """Run the fixed adapter lifecycle and return a canonical result."""
        ok, reason = self.validate(df)
        if not ok:
            warning = reason or "validation failed"
            return TrendResult(
                direction="NEUTRAL",
                confidence=0.0,
                signed_score=0.0,
                status="INVALID",
                explanation=warning,
                warnings=[warning],
                metadata={"strategy": self.name},
            )

        try:
            raw = self._analyze_raw(df)
            result = self._normalize(raw, df)
            result = self._clamp_result(result)
            result = self._post_check(result, df)
            return self._ensure_explanation(result, raw, df)
        except Exception as exc:  # pragma: no cover - exact exception types vary by adapter
            return TrendResult(
                direction="NEUTRAL",
                confidence=0.0,
                signed_score=0.0,
                status="INVALID",
                explanation=f"{self.name} failed: {exc}",
                warnings=[str(exc)],
                metadata={"strategy": self.name},
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

        min_bars = self.get_required_bars()
        if len(df) < min_bars:
            return False, f"insufficient bars: {len(df)} < {min_bars}"

        close = df["close"]
        if close.isna().all():
            return False, "close column is all NaN"
        if (close.fillna(0) == 0).all():
            return False, "close column is all zero"

        return True, None

    def _post_check(self, result: TrendResult, df: pd.DataFrame) -> TrendResult:
        """Apply common status normalization while preserving explicit statuses."""
        if result.status in {"INVALID", "NO_SIGNAL", "FILTERED"}:
            return result

        if result.direction != "NEUTRAL" and result.confidence < self.strategy_config.min_valid_confidence:
            return replace(result, status="FILTERED", warnings=[*result.warnings, "low confidence filtered"])

        if result.direction == "NEUTRAL":
            return replace(result, status="NO_SIGNAL")

        return result

    def _ensure_explanation(self, result: TrendResult, raw: Any, df: pd.DataFrame) -> TrendResult:
        """Attach a default explanation when an adapter did not provide one."""
        if result.explanation:
            return result
        explanation = (
            f"{self.name}: direction={result.direction}, confidence={result.confidence:.2f}, "
            f"strength={result.strength_rating}, readiness={result.readiness}"
        )
        return replace(result, explanation=explanation)

    def _clamp_result(self, result: TrendResult) -> TrendResult:
        """Clamp numeric fields to the canonical public ranges."""
        return replace(
            result,
            confidence=clamp_confidence(result.confidence),
            signed_score=clamp_signed_score(result.signed_score),
        )

    @abstractmethod
    def _analyze_raw(self, df: pd.DataFrame) -> Any:
        """Return the underlying analyzer's native result."""

    @abstractmethod
    def _normalize(self, raw: Any, df: pd.DataFrame) -> TrendResult:
        """Normalize a native result into :class:`TrendResult`."""

    @abstractmethod
    def get_required_bars(self) -> int:
        """Return the minimum number of bars required by this strategy."""


def clamp_confidence(value: float) -> float:
    """Clamp confidence to the canonical 0..1 range."""
    if not math.isfinite(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))


def clamp_signed_score(value: float) -> float:
    """Clamp signed score to the canonical -100..100 range."""
    if not math.isfinite(value):
        return 0.0
    return float(max(-100.0, min(100.0, value)))
