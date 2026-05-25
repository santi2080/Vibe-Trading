"""Cached data loader wrapper for transparent caching of any DataLoader."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from agent.backtest.loaders.cache import DataCache
from agent.backtest.loaders.yfinance_loader import _to_yfinance_interval

logger = logging.getLogger(__name__)


class CachedDataLoader:
    """Wrapper that adds three-level caching to any DataLoader.

    This wrapper transparently caches data from any loader that follows
    the DataLoaderProtocol. It uses a three-level cache (L1 memory, L2 disk,
    L3 original loader) to minimize API calls and improve performance.

    Example:
        >>> from agent.backtest.loaders.yfinance_loader import DataLoader as YFinanceLoader
        >>> base_loader = YFinanceLoader()
        >>> cached_loader = CachedDataLoader(base_loader, cache_dir="./cache")
        >>> data = cached_loader.fetch(["AAPL.US"], "2024-01-01", "2024-12-31")
    """

    def __init__(
        self,
        loader,
        cache_dir: Optional[str] = None,
        memory_cache_size: int = 100,
        memory_cache_mb: int = 500,
        enable_cache: bool = True,
    ):
        """Initialize cached loader.

        Args:
            loader: Base data loader instance (must follow DataLoaderProtocol).
            cache_dir: Directory for disk cache. Defaults to ~/.cache/vibe-trading/{loader.name}.
            memory_cache_size: Maximum number of entries in L1 cache.
            memory_cache_mb: Maximum memory usage in MB for L1 cache.
            enable_cache: Whether to enable caching (useful for debugging).
        """
        self.loader = loader
        self.enable_cache = enable_cache

        if enable_cache:
            if cache_dir is None:
                cache_dir = str(Path.home() / ".cache" / "vibe-trading" / loader.name)

            self.cache = DataCache(
                cache_dir=cache_dir,
                memory_cache_size=memory_cache_size,
                memory_cache_mb=memory_cache_mb,
            )
            logger.info(f"Initialized cache for {loader.name} at {cache_dir}")
        else:
            self.cache = None
            logger.info(f"Cache disabled for {loader.name}")

    @property
    def name(self) -> str:
        """Loader name (delegates to base loader)."""
        return self.loader.name

    @property
    def markets(self) -> set[str]:
        """Supported markets (delegates to base loader)."""
        return self.loader.markets

    @property
    def requires_auth(self) -> bool:
        """Whether loader requires authentication (delegates to base loader)."""
        return self.loader.requires_auth

    def is_available(self) -> bool:
        """Check if loader is available (delegates to base loader)."""
        return self.loader.is_available()

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        fields: Optional[List[str]] = None,
        interval: str = "1D",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data with caching.

        Args:
            codes: List of symbols to fetch.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            fields: Optional list of fields to fetch.
            interval: Time interval (e.g., "1D", "1H").

        Returns:
            Dictionary mapping symbol to DataFrame.
        """
        if not codes:
            return {}

        if not self.enable_cache or self.cache is None:
            return self.loader.fetch(codes, start_date, end_date, fields=fields, interval=interval)

        # Convert date strings to datetime
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)

        # Convert interval for consistent cache keys
        cache_interval = _to_yfinance_interval(interval)

        results = {}
        cache_misses = []

        # Try to get data from cache for each symbol
        for code in codes:
            cached_data = self.cache.get(
                symbol=code,
                timeframe=cache_interval,
                start_time=start_dt,
                end_time=end_dt,
                fields=fields,
            )

            if cached_data is not None:
                results[code] = cached_data
                logger.debug(f"Cache hit for {code} ({cache_interval}, {start_date} to {end_date})")
            else:
                cache_misses.append(code)
                logger.debug(f"Cache miss for {code} ({cache_interval}, {start_date} to {end_date})")

        # Fetch missing data from base loader
        if cache_misses:
            logger.info(f"Fetching {len(cache_misses)} symbols from {self.loader.name}")
            try:
                fetched_data = self.loader.fetch(
                    cache_misses,
                    start_date,
                    end_date,
                    fields=fields,
                    interval=interval,
                )

                # Cache the fetched data
                for code, data in fetched_data.items():
                    if not data.empty:
                        self.cache.set(
                            symbol=code,
                            timeframe=cache_interval,
                            start_time=start_dt,
                            end_time=end_dt,
                            data=data,
                            fields=fields,
                        )
                        results[code] = data
                        logger.debug(f"Cached data for {code}")
                    else:
                        logger.warning(f"Empty data returned for {code}")

            except Exception as exc:
                logger.error(f"Failed to fetch data from {self.loader.name}: {exc}")
                raise

        return results

    def get_cache_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics (hits, misses, sizes, etc.).
        """
        if not self.enable_cache or self.cache is None:
            return {"enabled": False}

        stats = self.cache.get_stats()
        stats["enabled"] = True
        stats["loader"] = self.loader.name
        return stats

    def clear_cache(self) -> None:
        """Clear all cached data."""
        if self.enable_cache and self.cache is not None:
            self.cache.clear()
            logger.info(f"Cleared cache for {self.loader.name}")
