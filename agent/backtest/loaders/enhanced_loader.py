"""Enhanced cached data loader with incremental updates and quality checks.

This module extends CachedDataLoader with:
- Incremental update support
- Data quality validation
- Automatic fallback chain integration

Usage:
    from agent.backtest.loaders.enhanced_loader import EnhancedCachedLoader

    loader = EnhancedCachedLoader(market="us_equity")

    # Load with automatic caching, quality checks, and incremental updates
    df = loader.load("AAPL.US", "1D", "2024-01-01", "2024-12-31")

    # Check quality
    report = loader.check_quality(df, "AAPL.US")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

from agent.backtest.loaders.cache import DataCache, DataQualityChecker
from agent.backtest.loaders.cache.quality_checker import QualityReport as VibeQualityReport
from agent.backtest.loaders.cache.incremental_updater import IncrementalUpdater, UpdateMetadata
from agent.backtest.loaders.registry import resolve_loader, get_loader_cls_with_fallback

logger = logging.getLogger(__name__)


class EnhancedCachedLoader:
    """Enhanced cached loader with incremental updates and quality checks.

    Features:
    - Three-level caching (memory, disk, API)
    - Data quality validation before caching
    - Incremental updates to minimize API calls
    - Automatic fallback chain resolution
    - Cache statistics and monitoring

    Example:
        >>> loader = EnhancedCachedLoader(market="us_equity")
        >>>
        >>> # Load with caching and incremental updates
        >>> df = loader.load("AAPL.US", "1D", "2024-01-01", "2024-12-31")
        >>>
        >>> # Check quality
        >>> report = loader.check_quality(df, "AAPL.US")
        >>> print(report.get_summary())
        >>>
        >>> # Get stats
        >>> stats = loader.get_cache_stats()
        >>> print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
    """

    def __init__(
        self,
        market: str = "us_equity",
        cache_dir: Optional[str] = None,
        enable_cache: bool = True,
        enable_quality_check: bool = True,
        enable_incremental: bool = True,
        memory_cache_size: int = 100,
        memory_cache_mb: int = 512,
    ):
        """Initialize enhanced cached loader.

        Args:
            market: Market type for loader resolution. Options:
                - "a_share": Chinese A-shares
                - "us_equity": US equities
                - "hk_equity": HK equities
                - "crypto": Crypto
                - "futures": Futures
                - "fund": Funds
            cache_dir: Directory for disk cache
            enable_cache: Whether to enable caching
            enable_quality_check: Whether to check data quality
            enable_incremental: Whether to use incremental updates
            memory_cache_size: Maximum entries in L1 cache
            memory_cache_mb: Maximum memory for L1 cache in MB
        """
        self.market = market
        self.enable_cache = enable_cache
        self.enable_quality_check = enable_quality_check
        self.enable_incremental = enable_incremental

        # Setup cache directory
        if cache_dir is None:
            cache_dir = str(Path.home() / ".cache" / "vibe-trading" / market)
        self.cache_dir = cache_dir
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        # Cache
        if enable_cache:
            self._cache = DataCache(
                cache_dir=cache_dir,
                memory_cache_size=memory_cache_size,
                memory_cache_mb=memory_cache_mb,
            )
        else:
            self._cache = None

        # Quality checker
        if enable_quality_check:
            self._quality_checker = DataQualityChecker()
        else:
            self._quality_checker = None

        # Incremental updater
        if enable_incremental:
            self._incremental = IncrementalUpdater(
                metadata_dir=os.path.join(cache_dir, "metadata"),
            )
        else:
            self._incremental = None

        # Statistics
        self._stats = {
            "loads": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "quality_checks": 0,
            "incremental_updates": 0,
        }

        logger.info(
            f"EnhancedCachedLoader initialized: market={market}, "
            f"cache={enable_cache}, quality={enable_quality_check}, "
            f"incremental={enable_incremental}"
        )

    @property
    def name(self) -> str:
        return f"enhanced_{self.market}"

    @property
    def markets(self) -> set:
        return {self.market}

    @property
    def requires_auth(self) -> bool:
        return True

    def is_available(self) -> bool:
        try:
            resolve_loader(self.market, enable_cache=False)
            return True
        except Exception:
            return False

    def load(
        self,
        symbol: str,
        interval: str = "1D",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Load data with caching, quality checks, and incremental updates.

        Args:
            symbol: Security symbol (e.g., "AAPL.US", "BTC-USDT")
            interval: Time interval (e.g., "1D", "1H")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            force_refresh: Force API refresh, ignore cache

        Returns:
            DataFrame with OHLCV data
        """
        self._stats["loads"] += 1

        # Try cache first
        if self._cache and not force_refresh:
            cached = self._cache.get(
                symbol=symbol,
                timeframe=interval,
                start_time=pd.Timestamp(start_date) if start_date else datetime(2000, 1, 1),
                end_time=pd.Timestamp(end_date) if end_date else datetime.now(),
            )
            if cached is not None and not cached.empty:
                self._stats["cache_hits"] += 1
                logger.debug(f"Cache hit: {symbol} {interval}")
                return cached

        # Load from API
        df = self._fetch_from_api(symbol, interval, start_date, end_date, force_refresh)

        if df.empty:
            return df

        # Quality check
        if self._quality_checker:
            report = self._quality_checker.check(df, symbol=symbol)
            self._stats["quality_checks"] += 1

            if not report.passed:
                logger.warning(f"Quality issues for {symbol}: {len(report.issues)} issues")
                for issue in report.issues:
                    if issue.severity in ("error", "warning"):
                        logger.warning(f"  - [{issue.severity}] {issue.message}")

        # Cache the result
        if self._cache and not df.empty:
            self._cache.set(
                symbol=symbol,
                timeframe=interval,
                start_time=df.index.min(),
                end_time=df.index.max(),
                data=df,
            )

        return df

    def _fetch_from_api(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[str],
        end_date: Optional[str],
        force_refresh: bool,
    ) -> pd.DataFrame:
        """Fetch data from API with incremental updates."""
        # Get loader with fallback
        loader = resolve_loader(self.market, enable_cache=False)

        # Check for incremental update
        if self._incremental and not force_refresh:
            needs_update, reason = self._incremental.needs_update(symbol, interval, force_refresh)
            if not needs_update and start_date is None:
                logger.debug(f"Skipping {symbol}: {reason}")
                # Return cached data if available
                if self._cache:
                    cached = self._cache.get(
                        symbol=symbol,
                        timeframe=interval,
                        start_time=datetime(2000, 1, 1),
                        end_time=datetime.now(),
                    )
                    if cached is not None:
                        return cached

        # API call
        self._stats["api_calls"] += 1
        logger.info(f"API call: {symbol} {interval}")

        try:
            if start_date and end_date:
                result = loader.fetch([symbol], start_date, end_date, interval=interval)
            else:
                result = loader.fetch([symbol], interval=interval)

            if symbol in result:
                df = result[symbol]

                # Save incremental metadata
                if self._incremental and not df.empty:
                    metadata = UpdateMetadata(
                        symbol=symbol,
                        timeframe=interval,
                        last_update=datetime.now(),
                        start_date=df.index.min().strftime("%Y-%m-%d"),
                        end_date=df.index.max().strftime("%Y-%m-%d"),
                        row_count=len(df),
                        source=loader.name,
                    )
                    self._incremental.save_metadata(metadata)
                    self._stats["incremental_updates"] += 1

                return df
            else:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to load {symbol}: {e}")
            return pd.DataFrame()

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        fields: Optional[List[str]] = None,
        interval: str = "1D",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols.

        Args:
            codes: List of symbols
            start_date: Start date
            end_date: End date
            fields: Optional fields to fetch
            interval: Time interval

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        results = {}
        for code in codes:
            df = self.load(code, interval, start_date, end_date)
            if not df.empty:
                results[code] = df
        return results

    def check_quality(self, df: pd.DataFrame, symbol: str) -> VibeQualityReport:
        """Check data quality.

        Args:
            df: DataFrame to check
            symbol: Security symbol

        Returns:
            QualityReport with results
        """
        if self._quality_checker is None:
            self._quality_checker = DataQualityChecker()
        return self._quality_checker.check(df, symbol=symbol)

    def get_cache_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache and client stats
        """
        stats = self._stats.copy()

        if self._cache:
            cache_stats = self._cache.get_stats()
            total = cache_stats["hits"]["total_requests"]
            if total > 0:
                stats["cache_hit_rate"] = cache_stats["hits"]["hit_rate"]
            else:
                stats["cache_hit_rate"] = 0.0
            stats["cache_l1_entries"] = cache_stats["memory"]["entries"]
            stats["cache_l2_entries"] = cache_stats["disk"]["entries"]
            stats["cache_l2_mb"] = cache_stats["disk"]["total_size_mb"]
        else:
            stats["cache_hit_rate"] = 0.0

        return stats

    def clear_cache(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """Clear cache.

        Args:
            symbol: Optional symbol to clear
            timeframe: Optional timeframe to clear
        """
        if self._cache:
            self._cache.clear()

    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_cache_stats()

        print("=" * 50)
        print(f"EnhancedCachedLoader: {self.market}")
        print("=" * 50)
        print(f"Loads: {stats['loads']}")
        print(f"API Calls: {stats['api_calls']}")
        print(f"Cache Hits: {stats['cache_hits']}")
        print(f"Cache Hit Rate: {stats['cache_hit_rate']:.1%}")
        print(f"Quality Checks: {stats['quality_checks']}")
        print(f"Incremental Updates: {stats['incremental_updates']}")
        print("=" * 50)

    def __repr__(self) -> str:
        return (
            f"EnhancedCachedLoader(market={self.market}, "
            f"cache={self.enable_cache}, "
            f"quality={self.enable_quality_check}, "
            f"incremental={self.enable_incremental})"
        )
