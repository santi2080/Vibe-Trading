"""Base classes and dataclasses for MTES v3.

This module defines the core data structures and abstract base class
for all layers in the MTES v3 layered architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

import pandas as pd


class TrendDirection(Enum):
    """Trend direction enumeration."""
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


class StrengthRating(Enum):
    """Trend strength rating enumeration."""
    STRONG = "STRONG"
    READY = "READY"
    WEAK = "WEAK"
    EXHAUSTED = "EXHAUSTED"


class EntryAction(Enum):
    """Entry signal enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"
    WAIT = "WAIT"


@dataclass
class TrendBias:
    """Trend bias result from analysis.

    Attributes:
        direction: Trend direction (BULL, BEAR, NEUTRAL)
        confidence: Confidence level (0-1)
        signals: Dictionary of sub-signal details
    """
    direction: Literal["BULL", "BEAR", "NEUTRAL"]
    confidence: float  # 0-1
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "direction": self.direction,
            "confidence": self.confidence,
            "signals": self.signals,
        }


@dataclass
class StrengthRatingResult:
    """Trend strength rating result.

    Attributes:
        rating: Strength rating (STRONG, READY, WEAK, EXHAUSTED)
        adx_value: ADX value used for rating
        divergence: Whether divergence was detected
        regime: Volatility regime
    """
    rating: Literal["STRONG", "READY", "WEAK", "EXHAUSTED"]
    adx_value: float
    divergence: bool = False
    regime: str = "TRENDING"

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "rating": self.rating,
            "adx_value": self.adx_value,
            "divergence": self.divergence,
            "regime": self.regime,
        }


@dataclass
class EntrySignal:
    """Entry signal result.

    Attributes:
        signal: Entry action (LONG, SHORT, WAIT)
        entry_price: Suggested entry price (optional)
        stop_loss: Suggested stop loss (optional)
        reason: Reason for the signal (optional)
    """
    signal: Literal["LONG", "SHORT", "WAIT"]
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "signal": self.signal,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "reason": self.reason,
        }


@dataclass
class MTESv3Result:
    """MTES v3 final result combining all layers.

    Attributes:
        passed_prefilter: Whether the prefilter was passed
        mtf_trend: Multi-timeframe trend bias
        strength: Trend strength rating
        entry: Entry signal
        final_score: Final score (-100 to +100)
        final_confidence: Final confidence (0-1)
    """
    passed_prefilter: bool
    mtf_trend: TrendBias
    strength: StrengthRatingResult
    entry: EntrySignal
    final_score: float  # -100 to +100
    final_confidence: float  # 0-1

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "passed_prefilter": self.passed_prefilter,
            "mtf_trend": self.mtf_trend.to_dict() if self.mtf_trend else None,
            "strength": self.strength.to_dict() if self.strength else None,
            "entry": self.entry.to_dict() if self.entry else None,
            "final_score": self.final_score,
            "final_confidence": self.final_confidence,
        }


class BaseLayer(ABC):
    """Abstract base class for all MTES v3 layers.

    All layers must implement the analyze() and validate() methods.
    """

    @abstractmethod
    def analyze(self, df: pd.DataFrame, **kwargs) -> any:
        """Perform analysis on the given data.

        Args:
            df: OHLCV DataFrame with columns [open, high, low, close, volume]
            **kwargs: Additional keyword arguments for specific layer implementations

        Returns:
            Layer-specific result object
        """
        pass

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that the DataFrame has required columns and data.

        Args:
            df: OHLCV DataFrame

        Returns:
            True if data is valid, False otherwise
        """
        pass

    def get_name(self) -> str:
        """Get the layer name.

        Returns:
            Layer name string
        """
        return self.__class__.__name__
