"""Layer 1: MTF Trend Lock.

This layer identifies the multi-timeframe trend using:
- SMC (Smart Money Concepts) Market Structure Analysis
- Elder Triple Screen
- Ichimoku Cloud
"""

from .smc_analyzer import (
    Swing,
    SwingDetector,
    MarketStructureResult,
    SMCAnalyzer,
)

__all__ = [
    "Swing",
    "SwingDetector",
    "MarketStructureResult",
    "SMCAnalyzer",
]
