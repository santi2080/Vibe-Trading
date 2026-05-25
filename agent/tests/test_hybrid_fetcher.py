"""Tests for HybridDataFetcher."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agent.backtest.loaders.hybrid_fetcher import (
    HybridDataFetcher,
    SymbolRouter,
    SourcePool,
    DataFusion,
    DataSource,
    MarketType,
    FetchResult,
)


class TestSymbolRouter:
    """Tests for SymbolRouter."""

    @pytest.fixture
    def router(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            return SymbolRouter()

    @pytest.mark.parametrize("symbol,expected", [
        ("600519.SH", MarketType.A_SHARE),
        ("000001.SZ", MarketType.A_SHARE),
        ("830946.BJ", MarketType.A_SHARE),
        ("AAPL.US", MarketType.US_EQUITY),
        ("GOOGL", MarketType.US_EQUITY),  # Bare symbol defaults to US
        ("00700.HK", MarketType.HK_EQUITY),
        ("rb0", MarketType.CN_FUTURES),
        ("AU0", MarketType.CN_FUTURES),
        ("GC=F", MarketType.US_FUTURES),
        ("CL=P", MarketType.US_FUTURES),
        ("BTC/USDT", MarketType.CRYPTO),
        ("ETH", MarketType.CRYPTO),
        ("518880.OF", MarketType.FUND),
        ("EURUSD", MarketType.FOREX),
        ("EUR/USD", MarketType.FOREX),
    ])
    def test_detect_market(self, router, symbol, expected):
        assert router.detect_market(symbol) == expected


class TestDataFusion:
    """Tests for DataFusion."""

    @pytest.fixture
    def fusion(self):
        return DataFusion()

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [98.0, 99.0, 100.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))

    def test_validate_valid_df(self, fusion, sample_df):
        is_valid, issues = fusion.validate(sample_df, "TEST")
        assert is_valid
        assert len(issues) == 0

    def test_validate_empty_df(self, fusion):
        is_valid, issues = fusion.validate(pd.DataFrame(), "TEST")
        assert not is_valid
        assert "Empty DataFrame" in issues

    def test_validate_missing_columns(self, fusion):
        df = pd.DataFrame({
            "open": [100.0],
            "close": [103.0],
        })
        is_valid, issues = fusion.validate(df, "TEST")
        assert not is_valid
        assert any("Missing columns" in i for i in issues)

    def test_validate_null_values(self, fusion):
        df = pd.DataFrame({
            "open": [100.0, None, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [98.0, 99.0, 100.0],
            "close": [103.0, None, 105.0],
            "volume": [1000.0, 1100.0, 1200.0],
        })
        is_valid, issues = fusion.validate(df, "TEST")
        # Should flag high null percentage
        assert any("null values" in i for i in issues)

    def test_merge_single_source(self, fusion):
        df1 = pd.DataFrame({"close": [100, 101]})
        results = {
            "TEST": {
                DataSource.AKSHARE: FetchResult("TEST", df1, "akshare"),
            }
        }
        merged = fusion.merge(results)
        assert "TEST" in merged
        assert merged["TEST"] is not None

    def test_merge_multiple_sources_selects_best(self, fusion):
        # Old data
        df_old = pd.DataFrame({"close": [90, 91]})
        # Recent data (should be selected)
        df_new = pd.DataFrame({"close": [100, 101]})

        results = {
            "TEST": {
                DataSource.AKSHARE: FetchResult("TEST", df_old, "akshare", latency_ms=100),
                DataSource.YFINANCE: FetchResult("TEST", df_new, "yfinance", latency_ms=200),
            }
        }
        merged = fusion.merge(results)
        # Should prefer recent data
        assert merged["TEST"]["close"].iloc[-1] == 101

    def test_merge_none_for_all_failed(self, fusion):
        results = {
            "TEST": {
                DataSource.AKSHARE: FetchResult("TEST", None, "akshare", error="Failed"),
            }
        }
        merged = fusion.merge(results)
        assert merged["TEST"] is None


class TestHybridDataFetcher:
    """Tests for HybridDataFetcher."""

    @pytest.fixture
    def fetcher(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            return HybridDataFetcher()

    @pytest.fixture
    def mock_router(self, fetcher):
        with patch.object(fetcher.router, "route_symbol") as mock:
            mock.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
            yield mock

    @pytest.fixture
    def mock_pool(self, fetcher):
        with patch.object(fetcher.pool, "fetch") as mock:
            mock.return_value = {
                "600519.SH": pd.DataFrame({
                    "open": [100.0],
                    "high": [105.0],
                    "low": [98.0],
                    "close": [103.0],
                    "volume": [1000.0],
                })
            }
            yield mock

    def test_fetch_one_symbol(self, fetcher, mock_router, mock_pool):
        with patch.object(fetcher.router, "check_available_sources") as mock_avail:
            mock_avail.return_value = {DataSource.AKSHARE: True}

            df = fetcher.fetch_one("600519.SH", "2024-01-01", "2024-01-10")
            assert df is not None
            assert "close" in df.columns

    def test_fetch_multiple_symbols(self, fetcher):
        with patch.object(fetcher.router, "route_symbol") as mock_route, \
             patch.object(fetcher.router, "check_available_sources") as mock_avail, \
             patch.object(fetcher.pool, "fetch") as mock_fetch:

            def route_side_effect(symbol):
                if symbol == "600519.SH":
                    return MarketType.A_SHARE, DataSource.AKSHARE
                elif symbol == "AAPL.US":
                    return MarketType.US_EQUITY, DataSource.YFINANCE
                return MarketType.A_SHARE, DataSource.AKSHARE

            mock_route.side_effect = route_side_effect
            mock_avail.return_value = {
                DataSource.AKSHARE: True,
                DataSource.YFINANCE: True,
            }
            mock_fetch.return_value = {
                "600519.SH": pd.DataFrame({"close": [100]}),
                "AAPL.US": pd.DataFrame({"close": [150]}),
            }

            results = fetcher.fetch(["600519.SH", "AAPL.US"], "2024-01-01", "2024-01-10")
            assert len(results) == 2
            assert "600519.SH" in results
            assert "AAPL.US" in results

    def test_check_availability(self, fetcher):
        with patch.object(fetcher.router, "check_available_sources") as mock:
            mock.return_value = {
                DataSource.AKSHARE: True,
                DataSource.YFINANCE: True,
                DataSource.TUSHARE: False,
            }
            with patch.object(fetcher.router, "get_best_source") as mock_best:
                def best_side_effect(market):
                    if market == MarketType.A_SHARE:
                        return DataSource.AKSHARE
                    elif market == MarketType.US_EQUITY:
                        return DataSource.YFINANCE
                    return None

                mock_best.side_effect = best_side_effect

                availability = fetcher.check_availability()
                assert availability["a_share"]
                assert availability["us_equity"]
                assert not availability["cn_futures"]  # No source available

    def test_get_stats(self, fetcher):
        with patch.object(fetcher.router, "check_available_sources") as mock:
            mock.return_value = {
                DataSource.AKSHARE: True,
                DataSource.YFINANCE: True,
                DataSource.TUSHARE: False,
            }

            stats = fetcher.get_stats()
            assert "akshare" in stats["available_sources"]
            assert "tushare" in stats["unavailable_sources"]


class TestSourcePool:
    """Tests for SourcePool."""

    def test_get_loader_creates_instance(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"), \
             patch("agent.backtest.loaders.hybrid_fetcher.LOADER_REGISTRY", {"akshare": MagicMock}):

            pool = SourcePool()
            # Should not create loader until requested
            assert DataSource.AKSHARE not in pool._loaders

    def test_mark_success_updates_health(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            pool = SourcePool()
            pool.mark_success(DataSource.AKSHARE, 100.0)

            health = pool.get_health(DataSource.AKSHARE)
            assert health.get("consecutive_successes") == 1
            assert health.get("last_latency_ms") == 100.0

    def test_mark_failure_updates_health(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            pool = SourcePool()
            pool.mark_failure(DataSource.AKSHARE, "Connection timeout")

            health = pool.get_health(DataSource.AKSHARE)
            assert health.get("consecutive_failures") == 1
            assert health.get("last_error") == "Connection timeout"
