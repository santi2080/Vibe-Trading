"""Regression tests for audit cleanup findings."""

from __future__ import annotations

import pandas as pd

from backtest.loaders.client import DataClient
from backtest.strategies import StrategyRegistry
from backtest.strategies.trend import TrendEmaAdxStrategy
from src.analysis.report_generator import AnalysisResult, ReportGenerator


def test_data_client_load_forwards_force_refresh(monkeypatch, tmp_path):
    client = DataClient(
        cache_dir=str(tmp_path),
        enable_cache=False,
        enable_quality_check=False,
        enable_incremental=False,
    )

    called = {}

    def fake_load_from_api(symbol, interval, start_date, end_date, force_refresh=False):
        called["force_refresh"] = force_refresh
        return pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}
        )

    monkeypatch.setattr(client, "_load_from_api", fake_load_from_api)
    df = client.load("AAPL.US", force_refresh=True)

    assert called["force_refresh"] is True
    assert not df.empty


def test_strategy_registry_filter_by_market_matches_supported_markets():
    StrategyRegistry.register(TrendEmaAdxStrategy())

    results = StrategyRegistry.filter(market="us_futures")

    assert "trend_ema_adx" in results


def test_report_generator_formats_valid_signals_cleanly():
    generator = ReportGenerator()
    result = AnalysisResult(
        symbol="ES=F",
        name="S&P 500",
        market="us_futures",
        trend="UP",
        signal_direction="LONG",
        signal_price=7526.25,
        signal_date="2026-05-26",
        stop_loss=7410.5,
        atr_1n=88.16,
    )

    report = generator.generate_markdown([result], "watchlist/us_futures_watchlist.csv")

    assert "止损 7410.50 (88.16 ATR)" in report
    assert "ES=F" in report
