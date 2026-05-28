"""Built-in strategy metadata tools for the agent registry."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool


def _load_strategy_tools():
    from src.agent import strategy_tools

    return strategy_tools


class ListStrategiesTool(BaseTool):
    """List built-in strategy modules and metadata."""

    name = "list_strategies"
    description = "List built-in trend, pullback, and entry strategies with optional type, tag, and timeframe filters."
    parameters = {
        "type": "object",
        "properties": {
            "strategy_type": {"type": "string", "description": "Optional type: trend, pullback, or entry."},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional strategy tags."},
            "timeframe": {"type": "string", "description": "Optional timeframe such as 1d, 4h, or 1h."},
        },
        "required": [],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        content = _load_strategy_tools().list_strategies(
            strategy_type=kwargs.get("strategy_type"),
            tags=kwargs.get("tags"),
            timeframe=kwargs.get("timeframe"),
        )
        return json.dumps({"status": "ok", "content": content}, ensure_ascii=False)


class GetStrategyInfoTool(BaseTool):
    """Return detailed metadata for one built-in strategy."""

    name = "get_strategy_info"
    description = "Get detailed metadata and usage guidance for a built-in strategy by name."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Strategy name, e.g. trend_ema_adx."},
        },
        "required": ["name"],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        content = _load_strategy_tools().get_strategy_info(kwargs["name"])
        status = "error" if content.startswith("Strategy '") and "not found" in content else "ok"
        return json.dumps({"status": status, "content": content}, ensure_ascii=False)


class GetComposerTemplateTool(BaseTool):
    """Generate a StrategyComposer code template."""

    name = "get_composer_template"
    description = "Generate a StrategyComposer template for selected trend, pullback, and entry strategies."
    parameters = {
        "type": "object",
        "properties": {
            "trend_strategy": {"type": "string", "description": "Trend strategy name."},
            "pullback_strategy": {"type": "string", "description": "Pullback strategy name."},
            "entry_strategy": {"type": "string", "description": "Entry strategy name."},
        },
        "required": [],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        content = _load_strategy_tools().get_composer_template(
            trend_strategy=kwargs.get("trend_strategy", "trend_ema_adx"),
            pullback_strategy=kwargs.get("pullback_strategy", "pullback_rsi"),
            entry_strategy=kwargs.get("entry_strategy", "entry_breakout"),
        )
        return json.dumps({"status": "ok", "content": content}, ensure_ascii=False)


class GetMtfTemplateTool(BaseTool):
    """Generate a multi-timeframe alignment code template."""

    name = "get_mtf_template"
    description = "Generate a lookahead-safe multi-timeframe alignment template using MTFAligner."
    parameters = {"type": "object", "properties": {}, "required": []}
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        del kwargs
        content = _load_strategy_tools().get_mtf_template()
        return json.dumps({"status": "ok", "content": content}, ensure_ascii=False)
