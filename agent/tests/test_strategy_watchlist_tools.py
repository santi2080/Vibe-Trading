"""Regression tests for strategy and watchlist tool registration."""

from __future__ import annotations

import json

from src.tools import build_registry


def test_strategy_tools_are_registered_for_agent_use() -> None:
    registry = build_registry()

    expected = {
        "list_strategies",
        "get_strategy_info",
        "get_composer_template",
        "get_mtf_template",
    }

    assert expected <= set(registry.tool_names)


def test_watchlist_tools_are_registered_for_agent_use() -> None:
    registry = build_registry()

    expected = {
        "list_watchlist",
        "analyze_security",
        "analyze_watchlist",
    }

    assert expected <= set(registry.tool_names)


def test_list_strategies_tool_executes() -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("list_strategies", {"strategy_type": "trend"}))

    assert payload["status"] == "ok"
    assert "trend_ema_adx" in payload["content"]


def test_list_watchlist_tool_executes_on_default_watchlist() -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("list_watchlist", {}))

    assert payload["status"] == "ok"
    assert payload["count"] >= 1
    assert any(item["symbol"] == "GC=F" for item in payload["securities"])


def test_watchlist_tools_reject_paths_outside_watchlist_dir() -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("list_watchlist", {"watchlist_path": "../pyproject.toml"}))

    assert payload["status"] == "error"
    assert "escapes the watchlist directory" in payload["error"]


def test_analyze_watchlist_tool_returns_json_without_progress_stdout(capsys) -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("analyze_watchlist", {"watchlist_path": "watchlist/us_futures_watchlist.csv"}))
    captured = capsys.readouterr()

    assert captured.out == ""
    assert payload["status"] == "ok"
    assert payload["total"] == 8

