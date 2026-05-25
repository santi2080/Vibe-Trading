"""Auto-registration of all strategy classes.

This module imports all strategies and registers them with the StrategyRegistry.
"""

from .trend import (
    TrendEmaAdxStrategy,
    TrendMacdStrategy,
    TrendDualEmaStrategy,
)
from .pullback import (
    PullbackRsiStrategy,
    PullbackBollingerBandsStrategy,
    PullbackStochasticStrategy,
    PullbackFibonacciStrategy,
)
from .entry import (
    BreakoutEntryStrategy,
    VolumeSpikeEntryStrategy,
    VwapEntryStrategy,
    SignalConfluenceStrategy,
)

# Import base classes and composer
from . import BaseStrategy, StrategyType, StrategyRegistry
from .composer import StrategyComposer, ComposerState, CompositeSignal
from .mtf import MTFAligner, MTFComposer, MTFConfig, Timeframe, AlignmentResult

# Auto-register all strategies
def _register_strategies():
    """Register all strategy instances."""
    strategies = [
        # Trend strategies
        TrendEmaAdxStrategy(),
        TrendMacdStrategy(),
        TrendDualEmaStrategy(),
        # Pullback strategies
        PullbackRsiStrategy(),
        PullbackBollingerBandsStrategy(),
        PullbackStochasticStrategy(),
        PullbackFibonacciStrategy(),
        # Entry strategies
        BreakoutEntryStrategy(),
        VolumeSpikeEntryStrategy(),
        VwapEntryStrategy(),
        SignalConfluenceStrategy(),
    ]

    for strategy in strategies:
        StrategyRegistry.register(strategy)

# Register on import
_register_strategies()

__all__ = [
    # Base classes
    "BaseStrategy",
    "StrategyType",
    "StrategyRegistry",
    "StrategySignal",
    "StrategyMetadata",
    # Composer
    "StrategyComposer",
    "ComposerState",
    "CompositeSignal",
    # MTF Alignment
    "MTFAligner",
    "MTFComposer",
    "MTFConfig",
    "Timeframe",
    "AlignmentResult",
    # Trend strategies
    "TrendEmaAdxStrategy",
    "TrendMacdStrategy",
    "TrendDualEmaStrategy",
    # Pullback strategies
    "PullbackRsiStrategy",
    "PullbackBollingerBandsStrategy",
    "PullbackStochasticStrategy",
    "PullbackFibonacciStrategy",
    # Entry strategies
    "BreakoutEntryStrategy",
    "VolumeSpikeEntryStrategy",
    "VwapEntryStrategy",
    "SignalConfluenceStrategy",
]
