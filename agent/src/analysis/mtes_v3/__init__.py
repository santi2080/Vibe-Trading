"""MTES v3 - Multi-Timeframe Evaluation System v3.

分层递进趋势分析系统:
- Layer 0: 预处理层 (Preprocessor)
- Layer 1: 大周期趋势锁定 (MTF Trend Lock)
- Layer 2: 趋势强度确认 (Strength Confirmation)
- Layer 3: 入场时机 (Entry Timing)
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
from .layer1 import SMCAnalyzer, Swing, SwingDetector, MarketStructureResult

__all__ = [
    # Base enums
    "TrendDirection",
    "StrengthRating",
    "EntryAction",
    # Base classes
    "TrendBias",
    "StrengthRatingResult",
    "EntrySignal",
    "MTESv3Result",
    "BaseLayer",
    # Preprocessor (Layer 0)
    "Preprocessor",
    "PreprocessorConfig",
    # Main class
    "MTESv3",
    "MTESv3Config",
    # Layer 1: SMC
    "SMCAnalyzer",
    "Swing",
    "SwingDetector",
    "MarketStructureResult",
]
