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


class TestQualityMonitorIntegration:
    """Tests for DataQualityMonitor integration in HybridDataFetcher."""

    @pytest.fixture
    def fetcher(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            return HybridDataFetcher(enable_validation=True, min_quality_score=0.8)

    def test_quality_monitor_initialized(self, fetcher):
        """Test that quality_monitor is properly initialized."""
        assert fetcher.quality_monitor is not None
        assert fetcher.quality_monitor.min_score == 0.8
        assert fetcher._last_quality_reports == {}

    def test_quality_reports_initially_empty(self, fetcher):
        """Test that quality reports are empty before fetch."""
        reports = fetcher.get_quality_reports()
        assert reports == {}

    def test_quality_summary_initially_empty(self, fetcher):
        """Test that quality summary is empty before fetch."""
        summary = fetcher.get_quality_summary()
        assert summary["count"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0

    def test_quality_reports_populated_after_fetch(self, fetcher):
        """Test that quality reports are populated after fetch."""
        # Mock the fetch to return valid data
        mock_df = pd.DataFrame({
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [98.0, 99.0],
            "close": [103.0, 104.0],
            "volume": [1000.0, 1100.0],
        }, index=pd.date_range("2024-01-01", periods=2))

        with patch.object(fetcher.router, "route_symbol") as mock_route, \
             patch.object(fetcher.router, "check_available_sources") as mock_avail, \
             patch.object(fetcher.pool, "fetch") as mock_fetch:

            mock_route.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
            mock_avail.return_value = {DataSource.AKSHARE: True}
            mock_fetch.return_value = {"600519.SH": mock_df}

            results = fetcher.fetch(["600519.SH"], "2024-01-01", "2024-01-10")

            reports = fetcher.get_quality_reports()
            assert "600519.SH" in reports
            assert reports["600519.SH"].symbol == "600519.SH"

    def test_quality_summary_after_fetch(self, fetcher):
        """Test quality summary reflects fetched data."""
        mock_df = pd.DataFrame({
            "open": [100.0],
            "high": [105.0],
            "low": [98.0],
            "close": [103.0],
            "volume": [1000.0],
        }, index=[pd.Timestamp("2024-01-01")])

        with patch.object(fetcher.router, "route_symbol") as mock_route, \
             patch.object(fetcher.router, "check_available_sources") as mock_avail, \
             patch.object(fetcher.pool, "fetch") as mock_fetch:

            mock_route.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
            mock_avail.return_value = {DataSource.AKSHARE: True}
            mock_fetch.return_value = {"600519.SH": mock_df}

            fetcher.fetch(["600519.SH"], "2024-01-01", "2024-01-10")

            summary = fetcher.get_quality_summary()
            assert summary["count"] == 1

    def test_quality_reports_copy(self, fetcher):
        """Test that get_quality_reports returns a copy."""
        fetcher._last_quality_reports = {"TEST": None}
        reports = fetcher.get_quality_reports()
        reports["NEW"] = True
        assert "NEW" not in fetcher._last_quality_reports


class TestFreshnessCheckerIntegration:
    """Tests for DataFreshnessChecker integration in HybridDataFetcher."""

    @pytest.fixture
    def fetcher(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            return HybridDataFetcher(enable_freshness_check=True)

    def test_freshness_checker_initialized(self, fetcher):
        """Test that freshness_checker is properly initialized."""
        assert fetcher.freshness_checker is not None
        assert fetcher._last_freshness_reports == {}

    def test_freshness_reports_initially_empty(self, fetcher):
        """Test that freshness reports are empty before fetch."""
        reports = fetcher.get_freshness_reports()
        assert reports == {}

    def test_freshness_summary_initially_empty(self, fetcher):
        """Test that freshness summary is empty before fetch."""
        summary = fetcher.get_freshness_summary()
        assert summary["count"] == 0
        assert summary["fresh"] == 0

    def test_freshness_reports_populated_after_fetch(self, fetcher):
        """Test that freshness reports are populated after fetch."""
        mock_df = pd.DataFrame({
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [98.0, 99.0],
            "close": [103.0, 104.0],
            "volume": [1000.0, 1100.0],
        }, index=pd.date_range("2024-01-01", periods=2))

        with patch.object(fetcher.router, "route_symbol") as mock_route, \
             patch.object(fetcher.router, "check_available_sources") as mock_avail, \
             patch.object(fetcher.pool, "fetch") as mock_fetch:

            mock_route.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
            mock_avail.return_value = {DataSource.AKSHARE: True}
            mock_fetch.return_value = {"600519.SH": mock_df}

            results = fetcher.fetch(["600519.SH"], "2024-01-01", "2024-01-10", interval="1d")

            reports = fetcher.get_freshness_reports()
            assert "600519.SH" in reports
            assert "status" in reports["600519.SH"]
            assert "age_hours" in reports["600519.SH"]

    def test_freshness_summary_after_fetch(self, fetcher):
        """Test freshness summary reflects fetched data."""
        mock_df = pd.DataFrame({
            "open": [100.0],
            "high": [105.0],
            "low": [98.0],
            "close": [103.0],
            "volume": [1000.0],
        }, index=[pd.Timestamp("2024-01-01")])

        with patch.object(fetcher.router, "route_symbol") as mock_route, \
             patch.object(fetcher.router, "check_available_sources") as mock_avail, \
             patch.object(fetcher.pool, "fetch") as mock_fetch:

            mock_route.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
            mock_avail.return_value = {DataSource.AKSHARE: True}
            mock_fetch.return_value = {"600519.SH": mock_df}

            fetcher.fetch(["600519.SH"], "2024-01-01", "2024-01-10", interval="1d")

            summary = fetcher.get_freshness_summary()
            assert summary["count"] == 1

    def test_interval_stored_for_freshness(self, fetcher):
        """Test that interval is stored for freshness checking."""
        mock_df = pd.DataFrame({
            "open": [100.0],
            "high": [105.0],
            "low": [98.0],
            "close": [103.0],
            "volume": [1000.0],
        }, index=[pd.Timestamp("2024-01-01")])

        with patch.object(fetcher.router, "route_symbol") as mock_route, \
             patch.object(fetcher.router, "check_available_sources") as mock_avail, \
             patch.object(fetcher.pool, "fetch") as mock_fetch:

            mock_route.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
            mock_avail.return_value = {DataSource.AKSHARE: True}
            mock_fetch.return_value = {"600519.SH": mock_df}

            fetcher.fetch(["600519.SH"], "2024-01-01", "2024-01-10", interval="1h")

            assert fetcher._last_interval == "1h"
            reports = fetcher.get_freshness_reports()
            assert reports["600519.SH"]["timeframe"] == "1h"

    def test_freshness_reports_copy(self, fetcher):
        """Test that get_freshness_reports returns a copy."""
        fetcher._last_freshness_reports = {"TEST": {"status": "fresh"}}
        reports = fetcher.get_freshness_reports()
        reports["NEW"] = True
        assert "NEW" not in fetcher._last_freshness_reports


class TestSymbolTranslatorIntegration:
    """Tests for SymbolTranslator integration in HybridDataFetcher."""

    @pytest.fixture
    def router(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            return SymbolRouter()

    def test_source_to_vendor_mapping(self, router):
        """Test that SOURCE_TO_VENDOR maps DataSource to DataVendor."""
        from agent.src.data.symbol_translator import DataVendor as SrcVendor

        assert router.SOURCE_TO_VENDOR.get(DataSource.YFINANCE) == SrcVendor.YAHOO_FINANCE
        assert router.SOURCE_TO_VENDOR.get(DataSource.AKSHARE) == SrcVendor.AKSHARE
        assert router.SOURCE_TO_VENDOR.get(DataSource.TUSHARE) == SrcVendor.TUSHARE
        assert router.SOURCE_TO_VENDOR.get(DataSource.TQSDK) == SrcVendor.TQSDK

    def test_translate_symbol_for_yahoo_finance(self, router):
        """Test symbol translation for Yahoo Finance."""
        # GC=F -> GC=F (US Futures format)
        market = MarketType.US_FUTURES
        translated = router.translate_symbol("GC=F", market, DataSource.YFINANCE)
        assert translated == "GC=F"

    def test_translate_symbol_for_akshare_a_share(self, router):
        """Test symbol translation for A-share to Akshare."""
        market = MarketType.A_SHARE
        translated = router.translate_symbol("600519.SH", market, DataSource.AKSHARE)
        # Akshare uses pure numeric format
        assert "600519" in translated

    def test_translate_symbol_for_yahoo_hk(self, router):
        """Test symbol translation for HK stock to Yahoo."""
        market = MarketType.HK_EQUITY
        # Must use canonical form with .HK suffix
        translated = router.translate_symbol("00700.HK", market, DataSource.YFINANCE)
        assert translated == "00700.HK"

    def test_translate_symbol_unsupported_source(self, router):
        """Test symbol translation when vendor is not mapped."""
        market = MarketType.US_FUTURES
        # DATABENTO is not in SOURCE_TO_VENDOR
        translated = router.translate_symbol("GC=F", market, DataSource.OKX)
        assert translated == "GC=F"  # Returns original symbol

    def test_translate_symbol_cn_futures(self, router):
        """Test symbol translation for CN futures.

        CN futures to Tushare is explicitly unsupported (Phase 11).
        Tushare has no CN futures endpoint; stock daily() would return garbage.
        """
        from agent.src.data.symbol_translator import SymbolTranslator, DataVendor
        from agent.src.data.market import Market
        market = MarketType.CN_FUTURES
        # Phase 11: CN_FUTURES -> TUSHARE is explicitly unsupported
        result = SymbolTranslator.translate("rb2405", DataVendor.TUSHARE, Market.CN_FUTURES)
        assert not result.supported
        assert result.reason is not None
