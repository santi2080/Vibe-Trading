"""MTES V4 - Lean Direction Indicator.

A minimalist trend direction indicator combining:
- ADX pre-filter for range detection
- Ichimoku Cloud for structural direction
- EMA alignment for momentum confirmation
- Market Structure as auxiliary reference (non-weighted)

Optimized for speed and low lag.
"""

from .base import (
    LeanTrendResult,
    TrendDirection,
    TrendStrength,
)
from .lean_mtes import LeanMTES, LeanMTESConfig
from .market_structure import MarketStructure, MarketStructureSignal

__all__ = [
    "LeanTrendResult",
    "TrendDirection",
    "TrendStrength",
    "LeanMTES",
    "LeanMTESConfig",
    "MarketStructure",
    "MarketStructureSignal",
]
