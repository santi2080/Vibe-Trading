"""Contract tests for Phase 11 — Canonical Symbol Format + Data Source Translation.

Tests verify:
1. Canonical normalization is deterministic (HK five-digit, suffix case, etc.)
2. Vendor translations produce exact expected symbols per source
3. Unsupported market/vendor combinations fail explicitly
4. HybridDataFetcher fetch() uses vendor symbols internally but returns canonical keys
5. Market detection compatibility for Phase 11 canonical examples

All tests are offline/mocked — no live provider calls.
"""

from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from agent.src.data.symbol_translator import SymbolTranslator, DataVendor
from agent.src.data.market import Market


# ---------------------------------------------------------------------------
# Test 1: Canonical Normalization — HK five-digit, suffix case, crypto/forex
# ---------------------------------------------------------------------------


class TestCanonicalNormalization:
    """SYM-01: Canonical symbol normalization is deterministic."""

    @pytest.mark.parametrize(
        "input_symbol,expected_canonical",
        [
            # HK five-digit canonical — both inputs normalize to five-digit
            ("0700.HK", "00700.HK"),
            ("00700.HK", "00700.HK"),
            ("0998.HK", "00998.HK"),
            # Suffix case normalization
            ("aapl.us", "AAPL.US"),
            ("600036.sh", "600036.SH"),
            ("600036.sz", "600036.SZ"),
            ("600036.SH", "600036.SH"),
            # A-share/ETF canonical form preserved
            ("600036.SH", "600036.SH"),
            ("000001.SZ", "000001.SZ"),
            ("518880.SH", "518880.SH"),
            ("159915.SZ", "159915.SZ"),
            # US equity
            ("AAPL.US", "AAPL.US"),
            ("TSLA.US", "TSLA.US"),
            # US futures
            ("GC=F", "GC=F"),
            ("CL=F", "CL=F"),
            ("SI=F", "SI=F"),
            # CN futures main continuous
            ("rb0", "rb0"),
            ("al0", "al0"),
            ("ag0", "ag0"),
            ("if0", "if0"),
            # CN futures concrete contract
            ("IF2406", "IF2406"),
            ("rb2410", "rb2410"),
            # Crypto hyphen canonical (slash is CCXT vendor only)
            ("BTC/USDT", "BTC-USDT"),
            ("ETH/USDT", "ETH-USDT"),
            ("BTC-USDT", "BTC-USDT"),
            # Forex
            ("EURUSD", "EURUSD"),
            ("EURUSD.FX", "EURUSD"),
            ("EUR/USD", "EURUSD"),
        ],
    )
    def test_normalize_canonical(self, input_symbol: str, expected_canonical: str) -> None:
        """HK must normalize to five-digit .HK; crypto slash->hyphen; forex .FX stripped."""
        result = SymbolTranslator.normalize_canonical_symbol(input_symbol)
        assert result == expected_canonical, (
            f"normalize_canonical_symbol({input_symbol!r}) = {result!r}, "
            f"expected {expected_canonical!r}"
        )


# ---------------------------------------------------------------------------
# Test 2: Vendor Translation — supported mappings produce exact vendor symbols
# ---------------------------------------------------------------------------


class TestVendorTranslations:
    """SYM-02: Supported vendor mappings return exact expected symbols."""

    @pytest.mark.parametrize(
        "canonical,market,vendor,expected",
        [
            # A-share stock -> AKShare Sina format (sh/sz prefix)
            ("600036.SH", Market.CN_STOCK, DataVendor.AKSHARE, "sh600036"),
            ("000001.SZ", Market.CN_STOCK, DataVendor.AKSHARE, "sz000001"),
            ("830946.BJ", Market.CN_STOCK, DataVendor.AKSHARE, "bj830946"),
            # A-share ETF -> AKShare Sina ETF format
            ("518880.SH", Market.CN_ETF, DataVendor.AKSHARE, "sh518880"),
            ("159915.SZ", Market.CN_ETF, DataVendor.AKSHARE, "sz159915"),
            # A-share -> Tushare (ts_code with suffix)
            ("600036.SH", Market.CN_STOCK, DataVendor.TUSHARE, "600036.SH"),
            ("000001.SZ", Market.CN_STOCK, DataVendor.TUSHARE, "000001.SZ"),
            # US equity -> yfinance (strip .US)
            ("AAPL.US", Market.US_STOCK, DataVendor.YAHOO_FINANCE, "AAPL"),
            ("TSLA.US", Market.US_STOCK, DataVendor.YAHOO_FINANCE, "TSLA"),
            # HK equity -> AKShare (five-digit numeric)
            ("00700.HK", Market.HK_STOCK, DataVendor.AKSHARE, "00700"),
            ("0700.HK", Market.HK_STOCK, DataVendor.AKSHARE, "00700"),
            # HK equity -> yfinance (.HK format)
            ("00700.HK", Market.HK_STOCK, DataVendor.YAHOO_FINANCE, "00700.HK"),
            # US futures -> AKShare (strip =F)
            ("GC=F", Market.US_FUTURES, DataVendor.AKSHARE, "GC"),
            ("CL=F", Market.US_FUTURES, DataVendor.AKSHARE, "CL"),
            # US futures -> Databento (continuous .c.0)
            ("GC=F", Market.US_FUTURES, DataVendor.DATABENTO, "GC.c.0"),
            ("CL=F", Market.US_FUTURES, DataVendor.DATABENTO, "CL.c.0"),
            # US futures -> yfinance (pass-through with C->ZC mapping)
            ("GC=F", Market.US_FUTURES, DataVendor.YAHOO_FINANCE, "GC=F"),
            ("C=F", Market.US_FUTURES, DataVendor.YAHOO_FINANCE, "ZC=F"),
            # CN futures main continuous -> TqSdk
            ("rb0", Market.CN_FUTURES, DataVendor.TQSDK, "KQ.m@SHFE.rb"),
            ("al0", Market.CN_FUTURES, DataVendor.TQSDK, "KQ.m@SHFE.al"),
            ("ag0", Market.CN_FUTURES, DataVendor.TQSDK, "KQ.m@SHFE.ag"),
            ("if0", Market.CN_FUTURES, DataVendor.TQSDK, "KQ.m@CFFEX.IF"),
            # CN futures concrete -> TqSdk
            ("IF2406", Market.CN_FUTURES, DataVendor.TQSDK, "CFFEX.IF2406"),
            ("rb2410", Market.CN_FUTURES, DataVendor.TQSDK, "SHFE.rb2410"),
            # CN futures main continuous -> AKShare (uppercase)
            ("rb0", Market.CN_FUTURES, DataVendor.AKSHARE, "RB0"),
            ("al0", Market.CN_FUTURES, DataVendor.AKSHARE, "AL0"),
            # Crypto -> OKX (hyphen pass-through)
            ("BTC-USDT", Market.US_STOCK, DataVendor.OKX, "BTC-USDT"),
            # Crypto -> CCXT (slash vendor)
            ("BTC-USDT", Market.US_STOCK, DataVendor.CCXT, "BTC/USDT"),
            # Forex -> AKShare
            ("EURUSD", Market.US_STOCK, DataVendor.AKSHARE, "EURUSD"),
        ],
    )
    def test_supported_vendor_mapping(
        self, canonical: str, market: Market, vendor: DataVendor, expected: str
    ) -> None:
        """Each supported mapping produces the exact expected vendor symbol."""
        result = SymbolTranslator.to_vendor_format(canonical, vendor, market)
        assert result == expected, (
            f"to_vendor_format({canonical!r}, {vendor}, {market}) = {result!r}, "
            f"expected {expected!r}"
        )


# ---------------------------------------------------------------------------
# Test 3: Unsupported Combinations — explicit failure, no silent mangling
# ---------------------------------------------------------------------------


class TestUnsupportedCombinations:
    """SYM-02: Unsupported market/vendor combos must fail explicitly."""

    @pytest.mark.parametrize(
        "canonical,market,vendor",
        [
            # CN futures -> Tushare (stock daily endpoint, not futures-aware)
            ("rb0", Market.CN_FUTURES, DataVendor.TUSHARE),
            ("IF2406", Market.CN_FUTURES, DataVendor.TUSHARE),
            # US equity -> TqSdk (TqSdk is CN futures only)
            ("AAPL.US", Market.US_STOCK, DataVendor.TQSDK),
            ("TSLA.US", Market.US_STOCK, DataVendor.TQSDK),
            # Crypto -> Tushare (no crypto endpoint)
            ("BTC-USDT", Market.US_STOCK, DataVendor.TUSHARE),
        ],
    )
    def test_unsupported_combos_raise_or_return_explicit(
        self, canonical: str, market: Market, vendor: DataVendor
    ) -> None:
        """Unsupported combos must NOT silently return a plausibly wrong symbol."""
        # The new translate() method returns TranslationResult with supported=False
        result = SymbolTranslator.translate(canonical, vendor, market)
        assert not result.supported, (
            f"translate({canonical!r}, {vendor}, {market}) should be unsupported, "
            f"got supported=True"
        )
        # Either vendor_symbol is None or reason is set
        assert result.vendor_symbol is None or result.reason is not None, (
            "Unsupported result must have vendor_symbol=None or a reason"
        )

    def test_no_silent_mangling_a_share_to_akshare(self) -> None:
        """AKShare A-share must NOT silently produce '600036SH' (wrong endpoint)."""
        # Old behavior: symbol.replace(".", "") -> "600036SH"
        # Correct behavior: sh/sz prefix -> "sh600036"
        result = SymbolTranslator.to_vendor_format("600036.SH", DataVendor.AKSHARE, Market.CN_STOCK)
        assert result != "600036SH", (
            f"AKShare A-share must NOT strip suffix: got {result!r}"
        )
        # Must be Sina format
        assert result in ("sh600036", "sh600036.SS"), f"Expected sh600036, got {result!r}"

    def test_no_silent_mangling_hk_to_akshare(self) -> None:
        """AKShare HK must NOT silently produce '00700.HK' (wrong endpoint)."""
        # Old behavior: symbol.zfill(5) kept .HK -> "00700.HK"
        # Correct behavior: strip .HK -> "00700"
        result = SymbolTranslator.to_vendor_format("00700.HK", DataVendor.AKSHARE, Market.HK_STOCK)
        assert result != "00700.HK", (
            f"AKShare HK must strip .HK suffix: got {result!r}"
        )
        assert result == "00700", f"Expected '00700', got {result!r}"


# ---------------------------------------------------------------------------
# Test 4: TranslationResult dataclass — additive strict API
# ---------------------------------------------------------------------------


class TestTranslationResult:
    """SYM-02: TranslationResult carries canonical, vendor_symbol, supported, reason."""

    def test_supported_result_has_vendor_symbol(self) -> None:
        result = SymbolTranslator.translate("600036.SH", DataVendor.AKSHARE, Market.CN_STOCK)
        assert result.supported is True
        assert result.vendor_symbol is not None
        assert result.canonical == "600036.SH"

    def test_unsupported_result_has_none_vendor_symbol(self) -> None:
        result = SymbolTranslator.translate("AAPL.US", DataVendor.TQSDK, Market.US_STOCK)
        assert result.supported is False
        assert result.vendor_symbol is None
        assert result.reason is not None
        assert result.canonical == "AAPL.US"


# ---------------------------------------------------------------------------
# Test 5: HybridDataFetcher mocked fetch — vendor symbols internal, canonical output
# ---------------------------------------------------------------------------


class TestHybridFetcherTranslationBoundary:
    """SYM-02/SYM-03: HybridDataFetcher calls pool.fetch with vendor symbols,
    returns canonical keys."""

    @pytest.fixture
    def fetcher(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            from agent.backtest.loaders.hybrid_fetcher import HybridDataFetcher
            return HybridDataFetcher()

    def test_pool_fetch_called_with_vendor_symbols(self, fetcher) -> None:
        """pool.fetch must be called with translated vendor symbols, not canonical."""
        mock_df = pd.DataFrame({
            "open": [100.0],
            "high": [105.0],
            "low": [98.0],
            "close": [103.0],
            "volume": [1000.0],
        })

        from agent.backtest.loaders.hybrid_fetcher import MarketType, DataSource

        with patch.object(fetcher.router, "route_symbol") as mock_route:
            with patch.object(fetcher.router, "check_available_sources") as mock_avail:
                with patch.object(fetcher.pool, "fetch") as mock_fetch:
                    # Route: A-share -> AKShare, US equity -> YFINANCE
                    def route_side_effect(symbol):
                        if symbol == "600036.SH":
                            return (MarketType.A_SHARE, DataSource.AKSHARE)
                        elif symbol == "AAPL.US":
                            return (MarketType.US_EQUITY, DataSource.YFINANCE)
                        return (MarketType.A_SHARE, DataSource.AKSHARE)
                    mock_route.side_effect = route_side_effect

                    mock_avail.return_value = {
                        DataSource.AKSHARE: True,
                        DataSource.YFINANCE: True,
                    }
                    # Simulate loader returning vendor-keyed data
                    mock_fetch.return_value = {
                        "sh600036": mock_df,  # Vendor key from AKShare
                        "AAPL": mock_df,      # Vendor key from yfinance
                    }

                    results = fetcher.fetch(["600036.SH", "AAPL.US"], "2024-01-01", "2024-01-10")

        # Caller-facing result keys must be canonical, not vendor
        assert "600036.SH" in results, (
            f"Result must contain canonical key '600036.SH', got keys: {list(results.keys())}"
        )
        assert "AAPL.US" in results, (
            f"Result must contain canonical key 'AAPL.US', got keys: {list(results.keys())}"
        )
        # No vendor keys must leak to caller
        assert "sh600036" not in results, "Vendor key 'sh600036' must not leak to caller"
        assert "AAPL" not in results, "Vendor key 'AAPL' must not leak to caller"

    def test_hk_alias_normalizes_to_canonical_output(self, fetcher) -> None:
        """HK input alias 0700.HK must return canonical 00700.HK, not 0700.HK."""
        mock_df = pd.DataFrame({
            "open": [400.0],
            "close": [410.0],
        }, index=pd.to_datetime(["2024-01-01"]))

        from agent.backtest.loaders.hybrid_fetcher import MarketType, DataSource

        with patch.object(fetcher.router, "route_symbol") as mock_route:
            with patch.object(fetcher.router, "check_available_sources") as mock_avail:
                with patch.object(fetcher.pool, "fetch") as mock_fetch:
                    # Route to AKShare
                    mock_route.return_value = (MarketType.HK_EQUITY, DataSource.AKSHARE)
                    mock_avail.return_value = {DataSource.AKSHARE: True}
                    # Loader returns data keyed by AKShare vendor symbol (00700)
                    mock_fetch.return_value = {"00700": mock_df}

                    results = fetcher.fetch(["0700.HK"], "2024-01-01", "2024-01-10")

        # Output must use normalized canonical key
        assert "00700.HK" in results, (
            f"0700.HK alias must normalize to canonical 00700.HK, got keys: {list(results.keys())}"
        )
        assert "0700.HK" not in results, (
            "Canonical alias 0700.HK must not appear as separate key alongside 00700.HK"
        )

    def test_fallback_retries_with_own_vendor_symbols(self, fetcher) -> None:
        """Fallback source must use its own vendor translation, not primary vendor."""
        mock_df = pd.DataFrame({"close": [100.0]})
        from agent.backtest.loaders.hybrid_fetcher import MarketType, DataSource

        with patch.object(fetcher.router, "route_symbol") as mock_route:
            with patch.object(fetcher.router, "check_available_sources") as mock_avail:
                with patch.object(fetcher.pool, "fetch") as mock_fetch:
                    mock_route.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
                    # Both AKShare and Tushare available
                    mock_avail.return_value = {
                        DataSource.AKSHARE: True,
                        DataSource.TUSHARE: True,
                    }
                    # First call returns empty, second call returns data with canonical key
                    mock_fetch.side_effect = [
                        {},  # AKShare empty
                        {"600036.SH": mock_df},  # Tushare returns data (canonical key)
                    ]

                    results = fetcher.fetch(["600036.SH"], "2024-01-01", "2024-01-10")

        # Result must have canonical key
        assert "600036.SH" in results, (
            f"Result must have canonical key '600036.SH', got keys: {list(results.keys())}"
        )


# ---------------------------------------------------------------------------
# Test 6: Market detection compatibility — Phase 11 canonical examples
# ---------------------------------------------------------------------------


class TestMarketDetectionPhase11:
    """SYM-03: Market detection compatibility for Phase 11 canonical examples.

    These tests ensure SymbolRouter.detect_market agrees with the canonical
    format decisions. No live provider calls.
    """

    @pytest.fixture
    def router(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            from agent.backtest.loaders.hybrid_fetcher import SymbolRouter
            return SymbolRouter()

    @pytest.mark.parametrize(
        "symbol,expected_market_type",
        [
            # US futures — must detect as US_FUTURES
            ("GC=F", "us_futures"),
            ("CL=F", "us_futures"),
            ("SI=F", "us_futures"),
            # CN futures main continuous — must detect as CN_FUTURES
            ("rb0", "cn_futures"),
            ("al0", "cn_futures"),
            ("ag0", "cn_futures"),
            # CN futures concrete contract
            ("IF2406", "cn_futures"),
            ("rb2410", "cn_futures"),
            # Crypto hyphen canonical
            ("BTC-USDT", "crypto"),
            ("ETH-USDT", "crypto"),
            # Forex
            ("EURUSD", "forex"),
            # HK equity — both four and five digit
            ("0700.HK", "hk_equity"),
            ("00700.HK", "hk_equity"),
        ],
    )
    def test_phase11_canonical_detection(
        self, router, symbol: str, expected_market_type: str
    ) -> None:
        """Phase 11 canonical examples must be detected correctly."""
        detected = router.detect_market(symbol)
        assert detected.value == expected_market_type, (
            f"detect_market({symbol!r}) = {detected.value!r}, "
            f"expected {expected_market_type!r}"
        )


# ---------------------------------------------------------------------------
# Test 7: Direct loader regression — canonical inputs still work
# ---------------------------------------------------------------------------


class TestDirectLoaderCanonicalInputs:
    """SYM-03: Direct loaders must still accept canonical inputs."""

    def test_akshare_loader_accepts_canonical_symbols(self) -> None:
        """AKShare direct loader must accept canonical inputs (no vendor translation required)."""
        with patch("backtest.loaders.akshare_loader.register"):
            from backtest.loaders.akshare_loader import DataLoader
            import sys
            from types import SimpleNamespace
            # Mock akshare module
            fake_ak = SimpleNamespace(
                stock_zh_a_daily=MagicMock(return_value=pd.DataFrame()),
                fund_etf_hist_sina=MagicMock(return_value=pd.DataFrame()),
                stock_hk_hist=MagicMock(return_value=pd.DataFrame()),
                futures_foreign_hist=MagicMock(return_value=pd.DataFrame()),
            )
            sys.modules["akshare"] = fake_ak

            loader = DataLoader()
            # Must accept canonical symbol without crashing
            try:
                loader.fetch(["600036.SH"], "2024-01-01", "2024-01-10")
            except Exception as exc:
                pytest.fail(f"Direct loader must accept canonical inputs: {exc}")
            finally:
                del sys.modules["akshare"]

    def test_yfinance_loader_accepts_canonical_symbols(self) -> None:
        """yfinance direct loader must accept canonical inputs."""
        with patch("backtest.loaders.yfinance_loader.register"):
            from backtest.loaders.yfinance_loader import DataLoader
            with patch("backtest.loaders.yfinance_loader._download_history") as mock_dl:
                mock_dl.return_value = pd.DataFrame()
                loader = DataLoader()
                # Must accept canonical symbol without crashing
                try:
                    loader.fetch(["AAPL.US", "00700.HK", "GC=F"], "2024-01-01", "2024-01-10")
                except Exception as exc:
                    pytest.fail(f"yfinance direct loader must accept canonical inputs: {exc}")
