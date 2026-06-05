"""Composite strategy signal layer.

Exports the TradingSignal contract and helper functions.
CompositeTrendStrategy is available via `from src.strategies.composite.trend_composite import CompositeTrendStrategy`.
"""

from __future__ import annotations

from .base import (
    SignalDirection,
    SignalReadiness,
    SignalStatus,
    TradingSignal,
    clamp_signal_confidence,
    clamp_signal_score,
    map_trend_readiness,
)

__all__ = [
    "TradingSignal",
    "SignalDirection",
    "SignalStatus",
    "SignalReadiness",
    "clamp_signal_score",
    "clamp_signal_confidence",
    "map_trend_readiness",
]
