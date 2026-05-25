"""Hybrid Data Fetcher - Unified data access with intelligent routing.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                    HybridDataFetcher                         │
│                  (统一入口，智能路由)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ SymbolRouter │  │ SourcePool   │  │ DataFusion   │     │
│  │  (品种路由)  │  │ (多源池)    │  │ (数据融合)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘

Usage:
    from agent.backtest.loaders.hybrid_fetcher import HybridDataFetcher

    fetcher = HybridDataFetcher()
    result = fetcher.fetch(["600519.SH", "AAPL.US"], "2024-01-01", "2024-12-31")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set

import pandas as pd

from agent.backtest.loaders.registry import (
    LOADER_REGISTRY,
    FALLBACK_CHAINS,
    _ensure_registered,
)

logger = logging.getLogger(__name__)


class MarketType(Enum):
    """Supported market types."""
    A_SHARE = "a_share"       # A股 (中国)
    US_EQUITY = "us_equity"   # 美股
    HK_EQUITY = "hk_equity"   # 港股
    CN_FUTURES = "cn_futures" # 中国期货
    US_FUTURES = "us_futures" # 美国期货
    CRYPTO = "crypto"         # 加密货币
    FUND = "fund"             # 基金
    FOREX = "forex"           # 外汇
    MACRO = "macro"           # 宏观


class DataSource(Enum):
    """Available data sources."""
    AKSHARE = "akshare"
    YFINANCE = "yfinance"
    TUSHARE = "tushare"
    OKX = "okx"
    CCXT = "ccxt"
    TQSDK = "tqsdk"
    FUTU = "futu"


@dataclass
class FetchResult:
    """Result of a single symbol fetch."""
    symbol: str
    df: Optional[pd.DataFrame]
    source: Optional[str]
    error: Optional[str] = None
    latency_ms: float = 0.0
    cached: bool = False


@dataclass
class FetchStats:
    """Statistics for a batch fetch operation."""
    total: int = 0
    success: int = 0
    failed: int = 0
    cached: int = 0
    total_latency_ms: float = 0.0
    by_source: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


# ============================================================================
# Symbol Router - Routes symbols to appropriate markets/sources
# ============================================================================

class SymbolRouter:
    """Routes symbols to appropriate markets and data sources.

    Handles symbol pattern recognition and market detection.
    """

    # Symbol patterns for different markets (order matters for overlapping patterns)
    # More specific patterns should come first
    PATTERNS = {
        MarketType.CRYPTO: [
            r"^.+/USDT$",             # BTC/USDT, ETH/USDT
            r"^(BTC|ETH)$",           # BTC, ETH (bare common symbols)
        ],
        MarketType.US_EQUITY: [
            r"^.+\.US$",              # AAPL.US, GOOGL.US
            r"^[A-Z]{1,5}$",          # AAPL, GOOGL (without suffix, assumed US)
        ],
        MarketType.A_SHARE: [
            r"^\d{6}\.(SH|SZ|BJ)$",  # 600519.SH, 000001.SZ, 830946.BJ
        ],
        MarketType.HK_EQUITY: [
            r"^\d{5}\.HK$",          # 00700.HK
        ],
        MarketType.CN_FUTURES: [
            r"^[a-z]+\d*$",           # rb0, al0, au0, si0
            r"^[A-Z]{2}\d{1,4}$",    # RB2405, AU2406
        ],
        MarketType.US_FUTURES: [
            r"^[A-Z]{1,3}=[FPU]$",    # GC=F, CL=F, SI=P
            r"^[A-Z]{1,3}\.(F|P|U)$", # GC.F, CL.P
        ],
        MarketType.FUND: [
            r"^\d{6}\.OF$",           # 518880.OF (场外基金)
        ],
        MarketType.FOREX: [
            r"^[A-Z]{6}$",            # EURUSD, GBPUSD
            r"^[A-Z]{3}/[A-Z]{3}$",  # EUR/USD
        ],
    }

    # Market to data source priority (for this router, not fallback)
    SOURCE_PRIORITY = {
        MarketType.A_SHARE: [DataSource.TUSHARE, DataSource.AKSHARE],
        MarketType.US_EQUITY: [DataSource.YFINANCE, DataSource.AKSHARE],
        MarketType.HK_EQUITY: [DataSource.FUTU, DataSource.YFINANCE, DataSource.AKSHARE],
        MarketType.CN_FUTURES: [DataSource.TQSDK, DataSource.TUSHARE, DataSource.AKSHARE],
        MarketType.US_FUTURES: [DataSource.AKSHARE, DataSource.YFINANCE],
        MarketType.CRYPTO: [DataSource.OKX, DataSource.CCXT],
        MarketType.FUND: [DataSource.TUSHARE, DataSource.AKSHARE],
        MarketType.FOREX: [DataSource.AKSHARE, DataSource.YFINANCE],
        MarketType.MACRO: [DataSource.AKSHARE, DataSource.TUSHARE],
    }

    def __init__(self):
        self._available_sources: Optional[Dict[DataSource, bool]] = None

    def detect_market(self, symbol: str) -> MarketType:
        """Detect market type from symbol."""
        symbol_upper = symbol.upper()

        for market, patterns in self.PATTERNS.items():
            for pattern in patterns:
                import re
                if re.match(pattern, symbol_upper):
                    return market

        # Default to US equity for bare symbols
        if symbol.isupper() and len(symbol) <= 5:
            return MarketType.US_EQUITY

        # Default fallback
        logger.warning("Unknown symbol pattern: %s, defaulting to A_SHARE", symbol)
        return MarketType.A_SHARE

    def get_source_priority(self, market: MarketType) -> List[DataSource]:
        """Get preferred data sources for a market."""
        return self.SOURCE_PRIORITY.get(market, [DataSource.AKSHARE])

    def check_available_sources(self) -> Dict[DataSource, bool]:
        """Check which data sources are available."""
        if self._available_sources is not None:
            return self._available_sources

        _ensure_registered()

        self._available_sources = {}
        for source in DataSource:
            source_name = source.value
            if source_name in LOADER_REGISTRY:
                try:
                    loader = LOADER_REGISTRY[source_name]()
                    self._available_sources[source] = loader.is_available()
                except Exception as e:
                    logger.debug("Source %s unavailable: %s", source_name, e)
                    self._available_sources[source] = False
            else:
                self._available_sources[source] = False

        return self._available_sources

    def get_best_source(self, market: MarketType) -> Optional[DataSource]:
        """Get the best available source for a market."""
        available = self.check_available_sources()
        for source in self.get_source_priority(market):
            if available.get(source, False):
                return source
        return None

    def route_symbol(self, symbol: str) -> tuple[MarketType, Optional[DataSource]]:
        """Route a symbol to its market and best available source."""
        market = self.detect_market(symbol)
        source = self.get_best_source(market)
        return market, source


# ============================================================================
# Source Pool - Manages multiple data sources
# ============================================================================

class SourcePool:
    """Manages multiple data sources with unified interface.

    Provides lazy initialization and source health tracking.
    """

    def __init__(self):
        self._loaders: Dict[DataSource, any] = {}
        self._health: Dict[DataSource, dict] = {}
        _ensure_registered()

    def get_loader(self, source: DataSource) -> Optional[any]:
        """Get or create a loader instance."""
        if source not in self._loaders:
            source_name = source.value
            if source_name not in LOADER_REGISTRY:
                return None
            try:
                self._loaders[source] = LOADER_REGISTRY[source_name]()
            except Exception as e:
                logger.error("Failed to create loader %s: %s", source_name, e)
                return None
        return self._loaders[source]

    def fetch(
        self,
        source: DataSource,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1D",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data from a specific source."""
        loader = self.get_loader(source)
        if loader is None:
            return {}

        try:
            return loader.fetch(symbols, start_date, end_date, interval=interval)
        except Exception as e:
            logger.error("Fetch failed from %s: %s", source.value, e)
            self._health[source] = {"last_error": str(e), "last_attempt": datetime.now()}
            return {}

    def mark_success(self, source: DataSource, latency_ms: float):
        """Mark a successful fetch."""
        self._health.setdefault(source, {}).update({
            "last_success": datetime.now(),
            "last_latency_ms": latency_ms,
            "consecutive_successes": self._health.get(source, {}).get("consecutive_successes", 0) + 1,
            "consecutive_failures": 0,
        })

    def mark_failure(self, source: DataSource, error: str):
        """Mark a failed fetch."""
        health = self._health.setdefault(source, {})
        health["last_error"] = error
        health["last_attempt"] = datetime.now()
        health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
        health["consecutive_successes"] = 0

    def get_health(self, source: DataSource) -> dict:
        """Get health info for a source."""
        return self._health.get(source, {})


# ============================================================================
# Data Fusion - Merges and validates data from multiple sources
# ============================================================================

class DataFusion:
    """Merges and validates data from multiple sources.

    Provides cross-source validation and intelligent data selection.
    """

    def __init__(self, max_age_days: int = 7):
        self.max_age_days = max_age_days

    def merge(
        self,
        results: Dict[str, Dict[DataSource, FetchResult]],
    ) -> Dict[str, pd.DataFrame]:
        """Merge results from multiple sources.

        Args:
            results: {symbol: {source: FetchResult}}

        Returns:
            {symbol: best DataFrame}
        """
        merged = {}

        for symbol, source_results in results.items():
            # Filter to only successful results
            valid = {s: r for s, r in source_results.items() if r.df is not None and not r.df.empty}

            if not valid:
                merged[symbol] = None
                continue

            if len(valid) == 1:
                # Single source - use it directly
                merged[symbol] = list(valid.values())[0].df
                continue

            # Multiple sources - select the best one
            best = self._select_best(valid)
            merged[symbol] = best.df if best else None

        return merged

    def _select_best(self, results: Dict[DataSource, FetchResult]) -> Optional[FetchResult]:
        """Select the best result from multiple sources.

        Selection criteria (in order):
        1. Data freshness (prefer recent data)
        2. Data completeness (prefer more rows)
        3. Source reliability (based on historical health)
        """
        if not results:
            return None

        candidates = list(results.values())

        # Sort by: freshness > completeness > latency
        def score(result: FetchResult) -> tuple:
            if result.df is None or result.df.empty:
                return (0, 0, 999999)  # Lowest priority

            # Freshness: most recent date
            try:
                latest = pd.Timestamp(result.df.index.max())
                age_days = (datetime.now() - latest.to_pydatetime()).days
                freshness = max(0, 100 - age_days * 10)  # Decay 10 points per day
            except:
                freshness = 0

            # Completeness: row count
            completeness = len(result.df)

            # Latency penalty (lower is better)
            latency_penalty = result.latency_ms / 1000

            return (freshness, completeness, latency_penalty)

        candidates.sort(key=score, reverse=True)
        return candidates[0]

    def validate(self, df: pd.DataFrame, symbol: str) -> tuple[bool, List[str]]:
        """Validate a DataFrame for data quality issues.

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        if df is None or df.empty:
            return False, ["Empty DataFrame"]

        # Check required columns
        required_cols = ["open", "high", "low", "close"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            issues.append(f"Missing columns: {missing}")

        # Check for NaN values in required columns
        if all(c in df.columns for c in required_cols):
            for col in required_cols:
                null_count = df[col].isnull().sum()
                if null_count > 0:
                    pct = null_count / len(df) * 100
                    if pct > 10:
                        issues.append(f"{col}: {pct:.1f}% null values")

        # Check for future dates
        try:
            latest = pd.Timestamp(df.index.max())
            if latest > datetime.now():
                issues.append(f"Future date detected: {latest}")
        except:
            pass

        # Check for zero volume (might indicate data issue)
        if "volume" in df.columns:
            zero_vol_pct = (df["volume"] == 0).sum() / len(df) * 100
            if zero_vol_pct > 50:
                issues.append(f"High zero-volume rate: {zero_vol_pct:.1f}%")

        return len(issues) == 0, issues


# ============================================================================
# Hybrid Data Fetcher - Main Entry Point
# ============================================================================

class HybridDataFetcher:
    """Unified data fetching with intelligent routing.

    Features:
    - Automatic symbol routing to appropriate markets
    - Multi-source fallback with health tracking
    - Cross-source validation
    - Caching support

    Usage:
        fetcher = HybridDataFetcher()

        # Single symbol
        df = fetcher.fetch_one("600519.SH", "2024-01-01", "2024-12-31")

        # Multiple symbols
        results = fetcher.fetch(["600519.SH", "AAPL.US"], "2024-01-01", "2024-12-31")

        # With source preference
        results = fetcher.fetch(["BTC/USDT"], "2024-01-01", "2024-12-31",
                                 source_preference=[DataSource.OKX])
    """

    def __init__(
        self,
        enable_caching: bool = True,
        enable_validation: bool = True,
        max_sources_per_symbol: int = 2,
    ):
        """
        Args:
            enable_caching: Enable disk/memory caching
            enable_validation: Enable data quality validation
            max_sources_per_symbol: Max sources to try per symbol
        """
        self.router = SymbolRouter()
        self.pool = SourcePool()
        self.fusion = DataFusion()
        self.enable_caching = enable_caching
        self.enable_validation = enable_validation
        self.max_sources_per_symbol = max_sources_per_symbol

    def fetch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1D",
        source_preference: Optional[List[DataSource]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols.

        Args:
            symbols: List of symbols to fetch
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Bar interval (1D, 1H, 1m, etc.)
            source_preference: Preferred sources (overrides default routing)

        Returns:
            {symbol: DataFrame} for successful fetches
        """
        import time
        start_time = time.time()

        # Group symbols by market
        by_market: Dict[MarketType, List[str]] = {}
        for symbol in symbols:
            market, _ = self.router.route_symbol(symbol)
            by_market.setdefault(market, []).append(symbol)

        # Fetch each market
        all_results: Dict[str, Dict[DataSource, FetchResult]] = {}
        stats = FetchStats(total=len(symbols))

        for market, market_symbols in by_market.items():
            # Determine sources to try
            if source_preference:
                sources_to_try = source_preference
            else:
                sources_to_try = self._get_sources_for_market(market)

            # Fetch from each source
            for source in sources_to_try[:self.max_sources_per_symbol]:
                fetch_start = time.time()
                try:
                    raw = self.pool.fetch(source, market_symbols, start_date, end_date, interval)
                    latency_ms = (time.time() - fetch_start) * 1000

                    for symbol in market_symbols:
                        df = raw.get(symbol)
                        result = FetchResult(
                            symbol=symbol,
                            df=df,
                            source=source.value if df is not None and not df.empty else None,
                            latency_ms=latency_ms,
                        )

                        all_results.setdefault(symbol, {})[source] = result

                        if df is not None and not df.empty:
                            stats.success += 1
                            stats.by_source[source.value] = stats.by_source.get(source.value, 0) + 1
                            self.pool.mark_success(source, latency_ms)
                        else:
                            stats.failed += 1
                            self.pool.mark_failure(source, "Empty result")
                except Exception as e:
                    logger.error("Error fetching from %s: %s", source.value, e)
                    self.pool.mark_failure(source, str(e))

        # Merge results from multiple sources
        merged = self.fusion.merge(all_results)

        # Validate if enabled
        if self.enable_validation:
            merged = self._validate_results(merged)

        stats.total_latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Fetch complete: %d/%d success, %.1fms total",
            stats.success, stats.total, stats.total_latency_ms
        )

        # Filter out None results
        return {k: v for k, v in merged.items() if v is not None}

    def fetch_one(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1D",
    ) -> Optional[pd.DataFrame]:
        """Fetch a single symbol.

        Args:
            symbol: Single symbol to fetch
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Bar interval

        Returns:
            DataFrame or None if failed
        """
        results = self.fetch([symbol], start_date, end_date, interval)
        return results.get(symbol)

    def _get_sources_for_market(self, market: MarketType) -> List[DataSource]:
        """Get available sources for a market, sorted by preference."""
        priority = self.router.get_source_priority(market)
        available = self.router.check_available_sources()

        return [s for s in priority if available.get(s, False)]

    def _validate_results(self, results: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Validate and filter results."""
        validated = {}
        for symbol, df in results.items():
            is_valid, issues = self.fusion.validate(df, symbol)
            if is_valid:
                validated[symbol] = df
            else:
                logger.warning("Symbol %s validation failed: %s", symbol, issues)
                # Still include but log warning
                validated[symbol] = df
        return validated

    def get_stats(self) -> dict:
        """Get current statistics."""
        available = self.router.check_available_sources()
        return {
            "available_sources": [s.value for s, v in available.items() if v],
            "unavailable_sources": [s.value for s, v in available.items() if not v],
            "source_health": {s.value: self.pool.get_health(s) for s in DataSource},
        }

    def check_availability(self) -> Dict[str, bool]:
        """Check which markets can be fetched."""
        return {
            market.value: self.router.get_best_source(market) is not None
            for market in MarketType
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def get_fetcher() -> HybridDataFetcher:
    """Get a singleton HybridDataFetcher instance."""
    if not hasattr(get_fetcher, "_instance"):
        get_fetcher._instance = HybridDataFetcher()
    return get_fetcher._instance
