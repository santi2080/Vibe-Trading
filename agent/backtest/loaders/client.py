"""Unified data client with caching, quality checks, and incremental updates.

This module provides a unified interface for data loading that combines:
- Three-level caching (memory, disk, API)
- Data quality validation
- Incremental updates
- Automatic fallback chains

Usage:
    from agent.backtest.loaders.client import DataClient

    client = DataClient()

    # Load with automatic caching and quality checks
    df = client.load("AAPL.US", "1D", "2024-01-01", "2024-12-31")

    # Check quality
    report = client.check_quality(df, "AAPL.US")

    # Get cache stats
    stats = client.get_cache_stats()
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


class DataClient:
    """Unified data client with caching, quality, and incremental updates.

    Features:
    - Automatic loader resolution with fallback chains
    - Three-level caching (L1 memory, L2 disk, L3 API)
    - Data quality validation before caching
    - Incremental updates to minimize API calls
    - Cache statistics and monitoring

    Example:
        >>> client = DataClient()
        >>>
        >>> # Load data with automatic caching
        >>> df = client.load("AAPL.US", "1D", "2024-01-01", "2024-12-31")
        >>>
        >>> # Check quality
        >>> report = client.check_quality(df, "AAPL.US")
        >>> print(report.get_summary())
        >>>
        >>> # Get stats
        >>> stats = client.get_cache_stats()
        >>> print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        market: str = "us_equity",
        enable_cache: bool = True,
        enable_quality_check: bool = True,
        enable_incremental: bool = True,
        memory_cache_size: int = 100,
        memory_cache_mb: int = 512,
    ):
        """Initialize data client.

        Args:
            cache_dir: Directory for disk cache. Defaults to ~/.cache/vibe-trading
            market: Market type for loader resolution. Options:
                - "a_share": Chinese A-shares (tushare, akshare)
                - "us_equity": US equities (yfinance, akshare)
                - "hk_equity": HK equities (yfinance, futu, akshare)
                - "crypto": Crypto (okx, ccxt)
                - "futures": Futures (tushare, akshare)
                - "fund": Funds (tushare, akshare)
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
            cache_dir = str(Path.home() / ".cache" / "vibe-trading")
        self.cache_dir = cache_dir
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        # Initialize components
        self._loader = None
        self._loader_name = None

        # Cache and quality checker
        if enable_cache:
            self._cache = DataCache(
                cache_dir=cache_dir,
                memory_cache_size=memory_cache_size,
                memory_cache_mb=memory_cache_mb,
            )
        else:
            self._cache = None

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
            f"DataClient initialized: market={market}, "
            f"cache={enable_cache}, quality={enable_quality_check}, "
            f"incremental={enable_incremental}"
        )

    def _get_loader(self) -> Any:
        """Get or create the data loader with fallback."""
        if self._loader is None:
            try:
                self._loader = resolve_loader(self.market, enable_cache=False)
                self._loader_name = self._loader.name
                logger.info(f"Using loader: {self._loader_name}")
            except Exception as e:
                logger.error(f"Failed to resolve loader for {self.market}: {e}")
                raise
        return self._loader

    def load(
        self,
        symbol: str,
        interval: str = "1D",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Load data with caching and quality checks.

        Args:
            symbol: Security symbol (e.g., "AAPL.US", "BTC-USDT", "600036.SS")
            interval: Time interval (e.g., "1D", "1H", "1m")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            force_refresh: Force API refresh, ignore cache

        Returns:
            DataFrame with OHLCV data (DatetimeIndex)
        """
        self._stats["loads"] += 1

        # Try cache first
        if self._cache and not force_refresh:
            cache_key = self._build_cache_key(symbol, interval, start_date, end_date)
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
        df = self._load_from_api(symbol, interval, start_date, end_date)

        if df.empty:
            logger.warning(f"Empty data returned for {symbol} {interval}")
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

    def _load_from_api(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        """Load data from API with optional incremental updates."""
        loader = self._get_loader()

        # Incremental update logic
        if self._incremental and start_date is None and end_date is None:
            # Check if we have cached data and only fetch new data
            metadata = self._incremental.get_metadata(symbol, interval)
            if metadata and not force_refresh:
                # Incremental update: fetch only new data
                needs_update, reason = self._incremental.needs_update(symbol, interval, force_refresh)
                if not needs_update:
                    # Return cached data if still fresh
                    if self._cache:
                        cached = self._cache.get(
                            symbol=symbol,
                            timeframe=interval,
                            start_time=pd.Timestamp(metadata.start_date),
                            end_time=pd.Timestamp(metadata.end_date),
                        )
                        if cached is not None and not cached.empty:
                            self._stats["cache_hits"] += 1
                            return cached

        # Full fetch
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

    def _build_cache_key(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Dict:
        """Build cache key dictionary."""
        return {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
        }

    def check_quality(self, df: pd.DataFrame, symbol: str) -> VibeQualityReport:
        """Check data quality.

        Args:
            df: DataFrame to check
            symbol: Security symbol for reporting

        Returns:
            QualityReport with check results
        """
        if self._quality_checker is None:
            self._quality_checker = DataQualityChecker()

        return self._quality_checker.check(df, symbol=symbol)

    def get_cache_stats(self) -> Dict:
        """Get cache and client statistics.

        Returns:
            Dictionary with statistics
        """
        stats = self._stats.copy()

        # Add cache stats if available
        if self._cache:
            cache_stats = self._cache.get_stats()
            stats.update({
                "cache_enabled": True,
                "cache_hit_rate": cache_stats["hits"]["hit_rate"],
                "cache_l1_size": cache_stats["memory"]["entries"],
                "cache_l2_size": cache_stats["disk"]["entries"],
                "cache_l2_mb": cache_stats["disk"]["total_size_mb"],
            })
        else:
            stats["cache_enabled"] = False

        # Add loader info
        if self._loader_name:
            stats["loader"] = self._loader_name

        return stats

    def clear_cache(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """Clear cache.

        Args:
            symbol: Optional symbol to clear (None = clear all)
            timeframe: Optional timeframe to clear
        """
        if self._cache:
            self._cache.clear()
            logger.info(f"Cache cleared: symbol={symbol}, timeframe={timeframe}")

    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_cache_stats()

        print("=" * 50)
        print("DataClient Statistics")
        print("=" * 50)

        if self._loader_name:
            print(f"Loader: {self._loader_name}")
            print(f"Market: {self.market}")

        print(f"\nLoads: {stats['loads']}")
        print(f"API Calls: {stats['api_calls']}")
        print(f"Cache Hits: {stats['cache_hits']}")

        if stats.get("cache_enabled"):
            print(f"Cache Hit Rate: {stats['cache_hit_rate']:.1%}")
            print(f"L1 Entries: {stats['cache_l1_size']}")
            print(f"L2 Entries: {stats['cache_l2_size']}")
            print(f"L2 Size: {stats['cache_l2_mb']:.1f} MB")

        print(f"Quality Checks: {stats['quality_checks']}")
        print(f"Incremental Updates: {stats['incremental_updates']}")
        print("=" * 50)

    def __repr__(self) -> str:
        return (
            f"DataClient(market={self.market}, "
            f"cache={self.enable_cache}, "
            f"quality={self.enable_quality_check}, "
            f"incremental={self.enable_incremental})"
        )


# Convenience function for quick access
_default_client: Optional[DataClient] = None


def get_client(**kwargs) -> DataClient:
    """Get or create the default data client.

    Args:
        **kwargs: Arguments passed to DataClient constructor

    Returns:
        DataClient instance
    """
    global _default_client
    if _default_client is None:
        _default_client = DataClient(**kwargs)
    return _default_client


def reset_client():
    """Reset the default client."""
    global _default_client
    _default_client = None
