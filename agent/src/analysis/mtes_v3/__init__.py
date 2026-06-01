"""MTES v3 - Multi-Timeframe Evaluation System v3.

分层递进趋势分析系统:
- Layer 0: 预处理层 (Preprocessor)
- Layer 1: 大周期趋势锁定 (MTF Trend Lock) - SMC + Elder + Ichimoku
- Layer 2: 趋势强度确认 (Strength Confirmation) - ADX + 背离
- Layer 3: 入场时机 (Entry Timing) - RSI + FVG + Range Filter
"""

from .base import (
    TrendBias,
    TrendDirection,
    StrengthRating,
    StrengthRatingResult,
    EntryAction,
    EntrySignal,
    MTESv3Result,
    BaseLayer,
)
from .preprocessor import Preprocessor, PreprocessorConfig
from .mtes_v3 import MTESv3, MTESv3Config
from .adapter import MTESv2Adapter, MTESv2Result, create_mtes_v2_result

# Layer 1
from .layer1 import (
    SMCAnalyzer, Swing, SwingDetector, MarketStructureResult,
    ElderTripleScreen, ElderSignal,
    IchimokuCloud, IchimokuSignal,
    Layer1Integrator,
)

# Layer 2
from .layer2 import (
    ADXStrengthFilter,
    MomentumDivergenceDetector, DivergenceResult,
)

# Layer 3
from .layer3 import EntryTiming

__all__ = [
    # Base
    "TrendDirection", "StrengthRating", "EntryAction",
    "TrendBias", "StrengthRatingResult", "EntrySignal", "MTESv3Result", "BaseLayer",

    # Config
    "MTESv3Config", "PreprocessorConfig",

    # Main
    "MTESv3",

    # Adapter
    "MTESv2Adapter", "MTESv2Result", "create_mtes_v2_result",

    # Layer 1
    "SMCAnalyzer", "Swing", "SwingDetector", "MarketStructureResult",
    "ElderTripleScreen", "ElderSignal",
    "IchimokuCloud", "IchimokuSignal",
    "Layer1Integrator",

    # Layer 2
    "ADXStrengthFilter", "MomentumDivergenceDetector", "DivergenceResult",

    # Layer 3
    "EntryTiming",
]
