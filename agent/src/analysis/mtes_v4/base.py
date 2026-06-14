"""Base types for MTES V4."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Any

# Import from market_structure to avoid circular import issues
try:
    from .market_structure import MarketStructureSignal
except ImportError:
    MarketStructureSignal = Any


class TrendDirection(Enum):
    """Trend direction enum."""
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


class TrendStrength(Enum):
    """Trend strength enum."""
    STRONG = "STRONG"
    READY = "READY"
    WEAK = "WEAK"
    EXHAUSTED = "EXHAUSTED"


@dataclass
class IchimokuSignal:
    """Ichimoku analysis result."""
    direction: TrendDirection
    price_vs_cloud: Literal["above", "in_cloud", "below"]
    tk_cross: Literal["bullish", "bearish", "neutral"]
    cloud_direction: Literal["bullish", "bearish"]
    chikou_confirm: bool
    confidence: float  # 0-1


@dataclass
class EMASignal:
    """EMA alignment result."""
    direction: TrendDirection
    alignment: Literal["bullish", "bearish", "mixed", "flat"]
    price_vs_ema: bool  # True if price above mid EMA
    slope: Literal["UP", "DOWN", "FLAT"]
    confidence: float  # 0-1


@dataclass
class LeanTrendResult:
    """Final result from LeanMTES."""
    # Core direction
    direction: TrendDirection
    confidence: float  # 0-1
    final_score: float  # -100 to +100

    # Market state
    is_trending: bool  # True if ADX >= threshold
    strength: TrendStrength

    # ADX values
    adx: float
    plus_di: float
    minus_di: float

    # Component scores (0-100)
    ichimoku_score: float
    ema_score: float

    # Detailed signals
    ichimoku_signal: IchimokuSignal | None = None
    ema_signal: EMASignal | None = None

    # Auxiliary: Market Structure (non-weighted)
    market_structure: MarketStructureSignal | None = None

    # Auxiliary: Structure health summary (BOS/CHoCH)
    # "BOS" = Break of Structure (trend continuation confirmed)
    # "CHoCH" = Change of Character (trend structure broken, early reversal warning)
    structure_event: Literal["BOS", "CHoCH", "NONE"] = "NONE"

    # Unified action bias
    # WAIT           → no valid signal (neutral/exhausted/CHoCH)
    # STRONG_LONG    → BULL + STRONG + BOS (confident, confirmed)
    # CAUTIOUS_LONG  → BULL + any strength (moderate confidence)
    # STRONG_SHORT    → BEAR + STRONG + BOS (confident, confirmed)
    # CAUTIOUS_SHORT → BEAR + any strength (moderate confidence)
    action_bias: Literal["STRONG_LONG", "CAUTIOUS_LONG", "CAUTIOUS_SHORT", "STRONG_SHORT", "WAIT"] = "WAIT"

    # Metadata
    bars_analyzed: int = 0
    explanation: str = ""

    @staticmethod
    def compute_action_bias(
        direction: "TrendDirection",
        strength: "TrendStrength",
        structure_event: str,
    ) -> Literal["STRONG_LONG", "CAUTIOUS_LONG", "CAUTIOUS_SHORT", "STRONG_SHORT", "WAIT"]:
        """Compute action_bias from direction, strength, and structure_event.

        Priority:
        1. NEUTRAL or EXHAUSTED or CHoCH → WAIT
        2. BULL + STRONG + BOS → STRONG_LONG
        3. BEAR + STRONG + BOS → STRONG_SHORT
        4. BULL + any strength → CAUTIOUS_LONG
        5. BEAR + any strength → CAUTIOUS_SHORT
        """
        # Guard conditions: no valid signal
        if direction == TrendDirection.NEUTRAL:
            return "WAIT"
        if strength == TrendStrength.EXHAUSTED:
            return "WAIT"
        if structure_event == "CHoCH":
            return "WAIT"

        # Strong + confirmed (BOS)
        if direction == TrendDirection.BULL and strength == TrendStrength.STRONG and structure_event == "BOS":
            return "STRONG_LONG"
        if direction == TrendDirection.BEAR and strength == TrendStrength.STRONG and structure_event == "BOS":
            return "STRONG_SHORT"

        # Moderate confidence (any strength, BOS or NONE)
        if direction == TrendDirection.BULL:
            return "CAUTIOUS_LONG"
        if direction == TrendDirection.BEAR:
            return "CAUTIOUS_SHORT"

        return "WAIT"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "direction": self.direction.value,
            "confidence": self.confidence,
            "final_score": self.final_score,
            "is_trending": self.is_trending,
            "strength": self.strength.value,
            "adx": round(self.adx, 2),
            "plus_di": round(self.plus_di, 2),
            "minus_di": round(self.minus_di, 2),
            "ichimoku_score": round(self.ichimoku_score, 1),
            "ema_score": round(self.ema_score, 1),
            "bars_analyzed": self.bars_analyzed,
            "explanation": self.explanation,
            "structure_event": self.structure_event,
            "action_bias": self.action_bias,
        }

        # Include market structure as auxiliary info
        if self.market_structure:
            result["market_structure"] = self.market_structure.to_dict()

        return result
