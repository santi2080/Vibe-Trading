from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.major_trend_evaluator import (
    ASSET_WEIGHT_PROFILES,
    MajorTrendEvaluator,
    TrendState,
    classify_trend_state,
    get_weight_profile,
)
from src.analysis.watchlist_analyzer import WatchlistAnalyzer
from src.tools import build_registry


def make_ohlcv(length: int = 320, start: float = 100, step: float = 1.0, noise: float = 0.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    trend = pd.Series([start + i * step for i in range(length)], index=index)
    if noise:
        trend = trend + pd.Series([(-1) ** i * noise for i in range(length)], index=index)
    high = trend + 1.0
    low = trend - 1.0
    return pd.DataFrame(
        {
            "open": trend - 0.2,
            "high": high,
            "low": low,
            "close": trend,
            "volume": 1000,
        },
        index=index,
    )


def test_asset_profiles_total_100() -> None:
    for asset_class in ASSET_WEIGHT_PROFILES:
        assert sum(get_weight_profile(asset_class).values()) == 100


def test_unsupported_asset_class_fails_clearly() -> None:
    with pytest.raises(ValueError, match="unsupported asset class"):
        get_weight_profile("unknown")


def test_strong_bull_fixture_scores_and_classifies() -> None:
    result = MajorTrendEvaluator().evaluate(make_ohlcv(step=1.0), asset_class="futures")

    assert result.direction == "BULL"
    assert result.trend_state in {TrendState.BULL_CONFIRMED.value, TrendState.BULL_STRONG.value}
    assert 0 <= result.trend_score <= 100
    assert set(result.sub_scores) == {
        "direction",
        "strength",
        "structure",
        "momentum",
        "volatility_regime",
        "mtf",
    }
    assert round(sum(result.sub_scores.values()), 2) == result.trend_score
    assert len(result.top_drivers) >= 3


def test_strong_bear_fixture_scores_and_classifies() -> None:
    result = MajorTrendEvaluator().evaluate(make_ohlcv(start=420, step=-1.0), asset_class="futures")

    assert result.direction == "BEAR"
    assert result.trend_state in {TrendState.BEAR_CONFIRMED.value, TrendState.BEAR_STRONG.value}


def test_choppy_fixture_maps_to_neutral_or_early_state() -> None:
    result = MajorTrendEvaluator().evaluate(make_ohlcv(step=0.0, noise=2.0), asset_class="etf")

    assert result.trend_state in {
        TrendState.NEUTRAL_CHOPPY.value,
        TrendState.BULL_EARLY.value,
        TrendState.BEAR_EARLY.value,
    }
    assert "choppy_noise" in result.regime_flags or result.regime in {"choppy", "mixed"}


def test_classification_thresholds_cover_seven_states() -> None:
    assert classify_trend_state(85, "BULL") == TrendState.BULL_STRONG.value
    assert classify_trend_state(70, "BULL") == TrendState.BULL_CONFIRMED.value
    assert classify_trend_state(50, "BULL") == TrendState.BULL_EARLY.value
    assert classify_trend_state(30, "BULL") == TrendState.NEUTRAL_CHOPPY.value
    assert classify_trend_state(50, "BEAR") == TrendState.BEAR_EARLY.value
    assert classify_trend_state(70, "BEAR") == TrendState.BEAR_CONFIRMED.value
    assert classify_trend_state(85, "BEAR") == TrendState.BEAR_STRONG.value


def test_insufficient_data_returns_warning_without_crashing() -> None:
    result = MajorTrendEvaluator().evaluate(make_ohlcv(length=20), asset_class="stock")

    assert result.trend_state == TrendState.NEUTRAL_CHOPPY.value
    assert result.regime_flags == ["insufficient_data"]
    assert result.trend_score == 0.0


def test_missing_volume_does_not_crash() -> None:
    df = make_ohlcv().drop(columns=["volume"])

    result = MajorTrendEvaluator().evaluate(df, asset_class="fx")

    assert result.asset_class == "fx"
    assert result.trend_score >= 0


def test_mtf_alignment_uses_completed_higher_timeframe_bars() -> None:
    base = make_ohlcv(length=80, step=0.5)
    higher = make_ohlcv(length=20, step=2.0).resample("W").last().dropna()

    result = MajorTrendEvaluator().evaluate(
        base,
        asset_class="futures",
        higher_timeframe=higher,
        base_timeframe="1d",
        higher_timeframe_name="1w",
    )

    assert result.metadata["mtf"]["method"] == "backward_lag"
    assert result.raw_scores["mtf"] in {25.0, 90.0}


def test_watchlist_analyzer_includes_mtes_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    watchlist = tmp_path / "watchlist.csv"
    data_file = tmp_path / "data" / "us_futures" / "GC=F" / "1d.parquet"
    data_file.parent.mkdir(parents=True)
    make_ohlcv().to_parquet(data_file)
    watchlist.write_text(
        "symbol,name,market,exchange,sector,timeframes,contract_type,multiplier,max_lots,ATR\n"
        "GC=F,黄金,US_FUTURES,COMEX,metals,1D-1H,standard,1,1,10\n",
        encoding="utf-8",
    )

    result = WatchlistAnalyzer(watchlist_path=str(watchlist)).analyze_all(verbose=False)[0]
    payload = result.to_dict()

    assert payload["symbol"] == "GC=F"
    assert payload["asset_class"] == "futures"
    assert "trend_score" in payload
    assert "trend_state" in payload
    assert "sub_scores" in payload
    assert "top_drivers" in payload


def test_watchlist_tool_summary_includes_machine_readable_mtes() -> None:
    payload = json.loads(build_registry().execute("analyze_watchlist", {"watchlist_path": "watchlist/us_futures_watchlist.csv"}))

    assert payload["status"] == "ok"
    assert payload["mtes"]
    first = payload["mtes"][0]
    assert {"symbol", "asset_class", "trend_score", "trend_state", "direction", "confidence", "regime", "sub_scores", "top_drivers"} <= set(first)
