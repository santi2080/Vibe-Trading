"""Regression tests for strategy and watchlist tool registration."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.analysis.watchlist_analyzer import AnalysisResult, WatchlistAnalyzer
from src.tools import build_registry
from src.tools import watchlist_tool

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKTEST_SCRIPT_PATH = REPO_ROOT / "scripts" / "backtest_trend_indicators.py"


def write_watchlist(path: Path, timeframes: str = "1D-4H") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "symbol,name,market,exchange,sector,timeframes,contract_type,multiplier,max_lots,ATR\n"
        f"GC=F,黄金,US_FUTURES,COMEX,贵金属,{timeframes},standard,1,1,10\n",
        encoding="utf-8",
    )


def write_ohlcv(path: Path, end: datetime, periods: int = 5, freq: str = "h") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    index = pd.date_range(end=end, periods=periods, freq=freq, name="timestamp")
    df = pd.DataFrame(
        {
            "open": [100 + index for index in range(periods)],
            "high": [101 + index for index in range(periods)],
            "low": [99 + index for index in range(periods)],
            "close": [100.5 + index for index in range(periods)],
            "volume": [1000 + index for index in range(periods)],
        },
        index=index,
    )
    df.to_parquet(path)


def load_backtest_module():
    module_name = "test_backtest_trend_indicators"
    spec = importlib.util.spec_from_file_location(module_name, BACKTEST_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def configure_temp_watchlist_env(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    watchlist_dir = tmp_path / "watchlist"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(watchlist_tool, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(watchlist_tool, "_WATCHLIST_DIR", watchlist_dir)
    monkeypatch.setattr(watchlist_tool, "_DATA_DIR", data_dir)
    return watchlist_dir, data_dir


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
        "check_watchlist_data",
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



def test_check_watchlist_data_tool_returns_gate_json(monkeypatch, tmp_path: Path) -> None:
    watchlist_dir, data_dir = configure_temp_watchlist_env(monkeypatch, tmp_path)
    watchlist_path = watchlist_dir / "test_watchlist.csv"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist_path, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")

    registry = build_registry()
    payload = json.loads(
        registry.execute(
            "check_watchlist_data",
            {
                "watchlist_path": "watchlist/test_watchlist.csv",
                "now": now.isoformat(),
            },
        )
    )

    assert payload["status"] == "ok"
    assert payload["gate"]["status"] == "FAIL"
    assert payload["gate"]["can_backtest"] is False
    assert payload["gate"]["blocking_failures"] > 0
    assert payload["gate"]["warnings"] == 0
    assert payload["rules"]["market_overrides"]["us_futures:1h"] == "24h"
    assert payload["items"]



def test_check_watchlist_data_tool_rejects_invalid_now(monkeypatch, tmp_path: Path) -> None:
    watchlist_dir, _ = configure_temp_watchlist_env(monkeypatch, tmp_path)
    write_watchlist(watchlist_dir / "test_watchlist.csv")

    registry = build_registry()
    payload = json.loads(
        registry.execute(
            "check_watchlist_data",
            {"watchlist_path": "watchlist/test_watchlist.csv", "now": "not-an-iso-timestamp"},
        )
    )

    assert payload["status"] == "error"
    assert payload["error_type"] == "validation"
    assert "Invalid now timestamp" in payload["error"]



def test_check_watchlist_data_tool_rejects_path_escape() -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("check_watchlist_data", {"watchlist_path": "../pyproject.toml"}))

    assert payload["status"] == "error"
    assert "escapes the watchlist directory" in payload["error"]



def test_analyze_watchlist_tool_returns_json_without_progress_stdout(capsys, monkeypatch) -> None:
    registry = build_registry()
    monkeypatch.setattr(
        watchlist_tool,
        "_build_watchlist_data_health_payload",
        lambda path, now=None: {
            "watchlist": str(path),
            "checked_at": "2026-05-27T12:00:00",
            "data_dir": str(watchlist_tool._DATA_DIR),
            "calendar_adjusted": False,
            "gate": {
                "empty_watchlist": False,
                "status": "PASS",
                "can_backtest": True,
                "blocking_failures": 0,
                "warnings": 0,
                "total_checks": 2,
            },
            "rules": {
                "blocking_timeframes": ["1d", "1h"],
                "staleness_thresholds": {"1d": "48h", "1h": "6h", "4h": "12h"},
                "market_overrides": {"us_futures:1h": "24h"},
                "calendar_adjusted": False,
            },
            "items": [],
        },
    )

    payload = json.loads(registry.execute("analyze_watchlist", {"watchlist_path": "watchlist/us_futures_watchlist.csv"}))
    captured = capsys.readouterr()

    assert captured.out == ""
    assert payload["status"] == "ok"
    assert payload["total"] == 8
    assert payload["data_health_gate"]["gate"]["can_backtest"] is True



def test_analyze_watchlist_blocks_when_required_data_health_fails(monkeypatch, tmp_path: Path) -> None:
    watchlist_dir, data_dir = configure_temp_watchlist_env(monkeypatch, tmp_path)
    watchlist_path = watchlist_dir / "blocked_watchlist.csv"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist_path, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")

    called = {"analyze_all": False}

    def fake_analyze_all(self, **kwargs):
        called["analyze_all"] = True
        return []

    monkeypatch.setattr(WatchlistAnalyzer, "analyze_all", fake_analyze_all)

    registry = build_registry()
    payload = json.loads(
        registry.execute("analyze_watchlist", {"watchlist_path": "watchlist/blocked_watchlist.csv"})
    )

    assert payload["status"] == "error"
    assert payload["error_type"] == "data_health_gate_blocked"
    assert payload["gate"]["can_backtest"] is False
    assert payload["gate"]["blocking_failures"] > 0
    assert payload["rules"]["blocking_timeframes"] == ["1d", "1h"]
    assert payload["items"]
    assert called["analyze_all"] is False



def test_analyze_watchlist_allows_warning_only_gate(monkeypatch, tmp_path: Path) -> None:
    watchlist_dir, data_dir = configure_temp_watchlist_env(monkeypatch, tmp_path)
    watchlist_path = watchlist_dir / "warning_watchlist.csv"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist_path, timeframes="1D-4H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    original_builder = watchlist_tool._build_watchlist_data_health_payload
    monkeypatch.setattr(
        watchlist_tool,
        "_build_watchlist_data_health_payload",
        lambda path, now=None: original_builder(path, now=datetime(2026, 5, 27, 12, 0, 0)),
    )

    called = {"analyze_all": False}

    def fake_analyze_all(self, **kwargs):
        called["analyze_all"] = True
        return [
            AnalysisResult(
                symbol="GC=F",
                name="黄金",
                market="US_FUTURES",
                trend="UP",
                signal_direction="LONG",
                signal_price=100.0,
            )
        ]

    monkeypatch.setattr(WatchlistAnalyzer, "analyze_all", fake_analyze_all)

    registry = build_registry()
    payload = json.loads(
        registry.execute(
            "analyze_watchlist",
            {"watchlist_path": "watchlist/warning_watchlist.csv", "format": "full"},
        )
    )

    assert payload["status"] == "ok"
    assert payload["data_health_gate"]["gate"]["status"] == "WARN"
    assert payload["data_health_gate"]["gate"]["can_backtest"] is True
    assert called["analyze_all"] is True
    assert payload["count"] == 1



def test_mcp_server_check_watchlist_data_wrapper_delegates_through_registry() -> None:
    source = (REPO_ROOT / "agent" / "mcp_server.py").read_text(encoding="utf-8")

    assert "def check_watchlist_data(" in source
    assert 'execute("check_watchlist_data", params)' in source



def test_watchlist_backtest_gate_blocks_missing_required_data(monkeypatch, tmp_path: Path) -> None:
    module = load_backtest_module()
    watchlist_path = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist_path, timeframes="1D-1H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("backtest_symbol should not run when the gate blocks")

    monkeypatch.setattr(module, "backtest_symbol", fail_if_called)

    exit_code, gate_payload, results = module.run_watchlist_backtest(
        watchlist_path,
        timeframe="1d",
        now=now,
        emit_output=False,
    )

    assert exit_code == 1
    assert gate_payload["status"] == "error"
    assert gate_payload["error_type"] == "data_health_gate_blocked"
    assert gate_payload["gate"]["can_backtest"] is False
    assert gate_payload["gate"]["blocking_failures"] > 0
    assert results == []



def test_watchlist_backtest_gate_allows_warning_only_execution(monkeypatch, tmp_path: Path) -> None:
    module = load_backtest_module()
    watchlist_path = tmp_path / "watchlist.csv"
    data_dir = tmp_path / "data"
    now = datetime(2026, 5, 27, 12, 0, 0)
    write_watchlist(watchlist_path, timeframes="1D-4H")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1d.parquet", now, freq="D")
    write_ohlcv(data_dir / "us_futures" / "GC=F" / "1h.parquet", now, freq="h")

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        module,
        "backtest_symbol",
        lambda symbol, name, market, timeframe: module.SymbolResult(
            symbol=symbol,
            name=name,
            market=market,
            timeframe=timeframe,
            data_points=100,
            period="2026-05-01 to 2026-05-27",
        ),
    )
    monkeypatch.setattr(module, "generate_report", lambda *args, **kwargs: tmp_path / "report.md")

    exit_code, gate_payload, results = module.run_watchlist_backtest(
        watchlist_path,
        timeframe="1d",
        now=now,
        emit_output=False,
    )

    assert exit_code == 0
    assert gate_payload["status"] == "ok"
    assert gate_payload["gate"]["status"] == "WARN"
    assert gate_payload["gate"]["can_backtest"] is True
    assert len(results) == 1
