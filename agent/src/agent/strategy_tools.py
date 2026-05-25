"""Strategy tools for Agent - provides access to built-in strategy metadata and composition.

This module allows the Agent to query and use built-in strategies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add agent to path for imports
agent_path = Path(__file__).parent.parent
if str(agent_path) not in sys.path:
    sys.path.insert(0, str(agent_path))

# Import backtest strategies - this triggers auto-registration
from backtest.strategies import registry  # noqa: F401
from backtest.strategies import (
    StrategyRegistry,
    StrategyType,
    StrategyComposer,
    MTFAligner,
)


def list_strategies(
    strategy_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    timeframe: Optional[str] = None,
) -> str:
    """List available built-in strategies with optional filtering.

    Args:
        strategy_type: Filter by type: "trend", "pullback", "entry"
        tags: Filter by tags (e.g., ["ema", "adx"])
        timeframe: Filter by timeframe (e.g., "1d", "4h", "1h")

    Returns:
        Formatted list of strategies

    Example:
        >>> list_strategies()
        >>> list_strategies(strategy_type="trend")
        >>> list_strategies(tags=["ema"])
    """
    # Filter strategies
    if strategy_type:
        type_map = {
            "trend": StrategyType.TREND,
            "pullback": StrategyType.PULLBACK,
            "entry": StrategyType.ENTRY,
        }
        st_type = type_map.get(strategy_type.lower())
        if st_type:
            names = StrategyRegistry.list_strategies(st_type)
        else:
            return f"Unknown strategy type: {strategy_type}. Use: trend, pullback, entry"
    elif tags:
        names = StrategyRegistry.list_by_tags(tags)
    elif timeframe:
        names = StrategyRegistry.list_by_timeframe(timeframe)
    else:
        names = StrategyRegistry.list_strategies()

    if not names:
        return "No strategies found matching the criteria."

    # Build output
    lines = [f"# Available Strategies ({len(names)} found)\n"]

    for name in names:
        meta = StrategyRegistry.get_metadata(name)
        if meta:
            lines.append(f"## {name}")
            lines.append(f"- Type: {meta.type.value}")
            if meta.tags:
                lines.append(f"- Tags: {', '.join(meta.tags)}")
            if meta.timeframes:
                lines.append(f"- Timeframes: {', '.join(meta.timeframes)}")
            if meta.supported_markets:
                lines.append(f"- Markets: {', '.join(meta.supported_markets)}")
            lines.append("")

    return "\n".join(lines)


def get_strategy_info(name: str) -> str:
    """Get detailed information about a specific strategy.

    Args:
        name: Strategy name (e.g., "trend_ema_adx")

    Returns:
        Detailed strategy information

    Example:
        >>> get_strategy_info("trend_ema_adx")
    """
    meta = StrategyRegistry.get_metadata(name)

    if not meta:
        available = ", ".join(StrategyRegistry.list_strategies())
        return f"Strategy '{name}' not found. Available: {available}"

    lines = [f"# {meta.name}\n"]
    lines.append(f"**Type**: {meta.type.value}\n")

    if meta.description:
        lines.append(f"\n**Description**: {meta.description[:200]}...")

    if meta.tags:
        lines.append(f"\n**Tags**: {', '.join(meta.tags)}")

    if meta.timeframes:
        lines.append(f"\n**Recommended Timeframes**: {', '.join(meta.timeframes)}")

    if meta.supported_markets:
        lines.append(f"\n**Supported Markets**: {', '.join(meta.supported_markets)}")

    if meta.parameters:
        lines.append("\n**Parameters**:")
        for param, value in meta.parameters.items():
            lines.append(f"- {param}: {value}")

    lines.append("\n\n**Usage in StrategyComposer**:")
    lines.append(f"```python")
    lines.append(f"composer = StrategyComposer()")
    if meta.type == StrategyType.TREND:
        lines.append(f"composer.set_trend('{name}')")
    elif meta.type == StrategyType.PULLBACK:
        lines.append(f"composer.set_pullback('{name}')")
    elif meta.type == StrategyType.ENTRY:
        lines.append(f"composer.set_entry('{name}')")
    lines.append(f"result = composer.generate(df)")
    lines.append(f"```")

    return "\n".join(lines)


def get_composer_template(
    trend_strategy: str = "trend_ema_adx",
    pullback_strategy: str = "pullback_rsi",
    entry_strategy: str = "entry_breakout",
) -> str:
    """Generate a StrategyComposer template with the specified strategies.

    Args:
        trend_strategy: Name of trend strategy (default: "trend_ema_adx")
        pullback_strategy: Name of pullback strategy (default: "pullback_rsi")
        entry_strategy: Name of entry strategy (default: "entry_breakout")

    Returns:
        Python code template for using StrategyComposer

    Example:
        >>> get_composer_template()
        >>> get_composer_template(trend_strategy="trend_macd")
    """
    # Verify strategies exist
    trend_meta = StrategyRegistry.get_metadata(trend_strategy)
    pullback_meta = StrategyRegistry.get_metadata(pullback_strategy)
    entry_meta = StrategyRegistry.get_metadata(entry_strategy)

    warnings = []
    if not trend_meta:
        warnings.append(f"Warning: Trend strategy '{trend_strategy}' not found")
    if not pullback_meta:
        warnings.append(f"Warning: Pullback strategy '{pullback_strategy}' not found")
    if not entry_meta:
        warnings.append(f"Warning: Entry strategy '{entry_strategy}' not found")

    lines = ["# Strategy Composer Template\n"]

    if warnings:
        lines.append("\n".join(warnings))
        lines.append("")

    lines.append("```python")
    lines.append("from agent.backtest.strategies import StrategyComposer")
    lines.append("")
    lines.append("# Initialize composer")
    lines.append(f"composer = StrategyComposer()")
    lines.append("")
    lines.append("# Set strategies (must set before using generate)")
    lines.append(f"composer.set_trend('{trend_strategy}')")
    lines.append(f"composer.set_pullback('{pullback_strategy}')")
    lines.append(f"composer.set_entry('{entry_strategy}')")
    lines.append("")
    lines.append("# Run on data")
    lines.append("result = composer.generate(df)")
    lines.append("")
    lines.append("# Get composite signal")
    lines.append("signal = composer.get_composite_signal()")
    lines.append("if signal:")
    lines.append("    print(f\"Direction: {signal.direction}\")")
    lines.append("    print(f\"Confidence: {signal.confidence:.2f}\")")
    lines.append("    print(f\"State: {signal.state}\")")
    lines.append("```")
    lines.append("")
    lines.append("## Output Columns")
    lines.append("- signal: 1 (long), -1 (short), 0 (neutral)")
    lines.append("- state: neutral → trend_confirmed → pullback_detected → signal_triggered")
    lines.append("- trend: trend direction")
    lines.append("- pullback: pullback confirmation (True/False)")
    lines.append("- entry: entry signal (True/False)")

    return "\n".join(lines)


def get_mtf_template() -> str:
    """Generate a Multi-Timeframe alignment template.

    Returns:
        Python code template for using MTFAligner
    """
    lines = ["# Multi-Timeframe Alignment Template\n"]
    lines.append("")
    lines.append("```python")
    lines.append("from agent.backtest.strategies import MTFAligner, MTFConfig")
    lines.append("")
    lines.append("# Configure alignment (prevents look-ahead bias)")
    lines.append("config = MTFConfig(")
    lines.append("    lag_bars=1,           # Mandatory lag for closed bars")
    lines.append("    merge_direction='backward',")
    lines.append("    fill_forward=True,")
    lines.append(")")
    lines.append("")
    lines.append("aligner = MTFAligner(config)")
    lines.append("")
    lines.append("# Align D1 to H1")
    lines.append("result = aligner.align_htf_to_ltf(")
    lines.append("    htf_data=d1_data,      # Daily data")
    lines.append("    ltf_data=h1_data,      # Hourly data")
    lines.append("    htf_timeframe='1d',")
    lines.append("    ltf_timeframe='1h',")
    lines.append(")")
    lines.append("")
    lines.append("# Use aligned data")
    lines.append("aligned_df = result.data")
    lines.append("warmup_bars = result.warmup_bars  # Skip first N bars")
    lines.append("```")
    lines.append("")
    lines.append("## Alignment Methods")
    lines.append("1. **Mandatory Lag**: HTF values shifted to use only closed bars")
    lines.append("2. **Backward Merge**: Each LTF bar gets HTF value from completed HTF bar")
    lines.append("3. **Forward Fill**: HTF values fill forward for continuity")

    return "\n".join(lines)


# Export all tools
STRATEGY_TOOLS = {
    "list_strategies": list_strategies,
    "get_strategy_info": get_strategy_info,
    "get_composer_template": get_composer_template,
    "get_mtf_template": get_mtf_template,
}
