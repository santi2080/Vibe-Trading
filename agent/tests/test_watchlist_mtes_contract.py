"""Watchlist MTES adapter and machine-contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.analysis.watchlist_analyzer import WatchlistAnalyzer
from src.tools import build_registry
from src.tools import watchlist_tool


REQUIRED_MTES_FIELDS = {
    "symbol",
    "asset_class",
    "trend_score",
    "trend_state",
    "direction",
    "confidence",
    "regime",
    "sub_scores",
    "top_drivers",
}


def _make_ohlcv(length: int = 320, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series([start + i * step for i in range(length)], index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def _write_watchlist(path: Path, symbol: str = "GC=F", timeframes: str = "4H-1D") -> None:
    path.write_text(
        "symbol,name,market,exchange,sector,timeframes,contract_type,trade_contract_type,multiplier,max_lots,ATR\n"
        f"{symbol},Gold,US_FUTURES,COMEX,Metals,{timeframes},standard,main,1,1,70.0\n",
        encoding="utf-8",
    )


def _write_local_data(tmp_path: Path, market: str, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    data_path = tmp_path / "data" / market / symbol / f"{timeframe.lower()}.parquet"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(data_path)


def test_watchlist_analyzer_emits_required_mtes_contract_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    watchlist_path = tmp_path / "watchlist.csv"
    _write_watchlist(watchlist_path, symbol="GC=F", timeframes="1D-4H")
    _write_local_data(tmp_path, "us_futures", "GC=F", "1d", _make_ohlcv())

    result = WatchlistAnalyzer(watchlist_path=str(watchlist_path)).analyze_all(verbose=False)[0]
    payload = result.to_dict()

    assert payload["symbol"] == "GC=F"
    assert REQUIRED_MTES_FIELDS <= set(payload)


class _FakeMtesResult:
    def __init__(self, asset_class: str) -> None:
        self.asset_class = asset_class

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "trend_score": 77.7,
            "trend_state": "BULL_CONFIRMED",
            "direction": "BULL",
            "confidence": 0.77,
            "regime": "trend_friendly",
            "sub_scores": {
                "direction": 12.0,
                "strength": 12.0,
                "structure": 20.0,
                "momentum": 12.0,
                "volatility_regime": 11.0,
                "mtf": 10.7,
            },
            "top_drivers": [
                {"name": "structure", "score": 20.0},
                {"name": "direction", "score": 12.0},
                {"name": "strength", "score": 12.0},
            ],
        }


def test_watchlist_timeframes_are_passed_into_mtes_evaluator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    watchlist_path = tmp_path / "watchlist.csv"
    _write_watchlist(watchlist_path, symbol="GC=F", timeframes="4H-1D")

    base_df = _make_ohlcv(length=280, step=0.3)
    higher_df = _make_ohlcv(length=120, step=1.4)
    _write_local_data(tmp_path, "us_futures", "GC=F", "4h", base_df)
    _write_local_data(tmp_path, "us_futures", "GC=F", "1d", higher_df)

    calls: list[dict[str, Any]] = []

    def _fake_evaluate(self, df: pd.DataFrame, **kwargs: Any) -> _FakeMtesResult:
        calls.append(
            {
                "len": len(df),
                "asset_class": kwargs.get("asset_class"),
                "base_timeframe": kwargs.get("base_timeframe"),
                "higher_timeframe_name": kwargs.get("higher_timeframe_name"),
                "higher_timeframe": kwargs.get("higher_timeframe"),
            }
        )
        return _FakeMtesResult(kwargs.get("asset_class", "unknown"))

    monkeypatch.setattr(
        "src.analysis.major_trend_evaluator.MajorTrendEvaluator.evaluate",
        _fake_evaluate,
    )

    result = WatchlistAnalyzer(watchlist_path=str(watchlist_path)).analyze_all(verbose=False)[0]

    assert result.error is None
    assert len(calls) == 1
    assert calls[0]["asset_class"] == "futures"
    assert calls[0]["base_timeframe"] == "4h"
    assert calls[0]["higher_timeframe_name"] == "1d"
    assert isinstance(calls[0]["higher_timeframe"], pd.DataFrame)
    assert not calls[0]["higher_timeframe"].empty


def test_analyze_watchlist_tool_includes_machine_readable_mtes_and_no_stdout(
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    registry = build_registry()

    payload = json.loads(
        registry.execute(
            "analyze_watchlist",
            {"watchlist_path": "watchlist/us_futures_watchlist.csv"},
        )
    )
    captured = capsys.readouterr()

    assert captured.out == ""
    assert payload["status"] == "ok"
    assert isinstance(payload.get("mtes"), list)
    assert payload["mtes"]

    first = payload["mtes"][0]
    assert REQUIRED_MTES_FIELDS - {"symbol"} <= set(first) | {"symbol"}
    assert {
        "asset_class",
        "trend_score",
        "trend_state",
        "direction",
        "confidence",
        "regime",
        "sub_scores",
        "top_drivers",
    } <= set(first)
