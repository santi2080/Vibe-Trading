"""Trend strategy adapter layer."""

from __future__ import annotations

from .base import (
    Readiness,
    StrengthRating,
    TrendDirection,
    TrendResult,
    TrendStatus,
    TrendStrategyBase,
    TrendStrategyConfig,
)

__all__ = [
    "Readiness",
    "StrengthRating",
    "TrendDirection",
    "TrendResult",
    "TrendStatus",
    "TrendStrategyBase",
    "TrendStrategyConfig",
    "MTESv2TrendStrategy",
    "MTESv3TrendStrategy",
    "MTESv4TrendStrategy",
]


def __getattr__(name: str):
    """Lazily import concrete adapters to keep base imports lightweight."""
    if name == "EnhancedSuperTrendStrategy":
        from .enhanced_supertrend import EnhancedSuperTrendStrategy

        return EnhancedSuperTrendStrategy
    if name == "MTESv2TrendStrategy":
        from .mtes_v2 import MTESv2TrendStrategy

        return MTESv2TrendStrategy
    if name == "MTESv3TrendStrategy":
        from .mtes_v3 import MTESv3TrendStrategy

        return MTESv3TrendStrategy
    if name == "MTESv4TrendStrategy":
        from .mtes_v4 import MTESv4TrendStrategy

        return MTESv4TrendStrategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
