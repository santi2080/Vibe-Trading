"""Layer 1: MTF Trend Lock.

This layer identifies the multi-timeframe trend using:
- Ichimoku Cloud (dominant, weight 0.5)
- EMA Alignment (secondary, weight 0.3)
- SMC Swing Detection (auxiliary, weight 0.2)

Design Philosophy:
- Ichimoku: Most reliable for quant systems
- EMA: Momentum confirmation
- SMC: Price level reference only
"""

from .smc_analyzer import (
    Swing,
    SwingDetector,
    MarketStructureResult,
    SMCAnalyzer,
)
from .elder_screen import ElderTripleScreen, ElderSignal
from .ichimoku import IchimokuCloud, IchimokuSignal
from .ema_alignment import EMAAnalyzer, EMASignal
from .integrator import Layer1Integrator

__all__ = [
    "Swing",
    "SwingDetector",
    "MarketStructureResult",
    "SMCAnalyzer",
    "ElderTripleScreen",
    "ElderSignal",
    "IchimokuCloud",
    "IchimokuSignal",
    "EMAAnalyzer",
    "EMASignal",
    "Layer1Integrator",
]
