"""Data cache manager with three-level architecture

Three-level cache system:
- L1: Memory cache (fast, limited capacity)
- L2: Disk cache (persistent, larger capacity)
- L3: Raw data files (original data storage)

Query flow: L1 → L2 → L3 → API
Write flow: L1 + L2 (async)

Enhanced features:
- Expression cache support for computed results
- Real-time monitoring via CacheMonitor
- Health checks and alerting
- Performance metrics collection

Usage:
    from agent.backtest.loaders.cache import DataCache

    cache = DataCache()

    # Try to get cached data
    df = cache.get(
        symbol='BTC-USDT',
        timeframe='1h',
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 12, 31)
    )

    # Save data to cache
    if df is None:
        df = fetch_from_api(...)
        cache.set(
            symbol='BTC-USDT',
            timeframe='1h',
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            data=df
        )

    # Monitor cache performance
    monitor = cache.get_monitor()
    report = monitor.get_report()
"""

import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd

from .cache_key import CacheKey
from .disk_cache import DiskCache
from .memory_cache import MemoryCache
from .cache_monitor import CacheMonitor

logger = logging.getLogger(__name__)


class DataCache:
    """Three-level data cache manager

    Manages L1 (memory) and L2 (disk) caches with automatic fallback.

    Attributes:
        memory_cache: L1 memory cache
        disk_cache: L2 disk cache
    """

    def __init__(
        self,
        cache_dir: str = "./data/cache/vibe",
        memory_cache_size: int = 100,
        memory_cache_mb: int = 512,
    ):
        """Initialize data cache

        Args:
            cache_dir: Directory for disk cache
            memory_cache_size: Maximum number of entries in memory cache
            memory_cache_mb: Maximum memory usage in MB
        """
        self.memory_cache = MemoryCache(
            max_size=memory_cache_size,
            max_memory_mb=memory_cache_mb,
        )
        self.disk_cache = DiskCache(cache_dir=cache_dir)
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
        }
        # Initialize monitor
        self._monitor = CacheMonitor(self)

    def get(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        fields: Optional[List[str]] = None,
    ) -> Optional[pd.DataFrame]:
        """Get cached data

        Query flow: L1 → L2 → None

        Args:
            symbol: Security symbol (e.g., 'BTC-USDT', 'rb0')
            timeframe: Time interval (e.g., '1h', '1d')
            start_time: Start datetime
            end_time: End datetime
            fields: Optional list of fields

        Returns:
            Cached DataFrame if exists, None otherwise
        """
        # Build cache key
        key = CacheKey(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            fields=fields or [],
        )
        cache_hash = key.to_hash()

        # L1: Check memory cache
        result = self.memory_cache.get(cache_hash)
        if result is not None:
            self._stats["l1_hits"] += 1
            logger.debug(f"L1 cache hit: {key}")
            return result

        # L2: Check disk cache
        result = self.disk_cache.get(cache_hash)
        if result is not None:
            self._stats["l2_hits"] += 1
            logger.debug(f"L2 cache hit: {key}")
            # Backfill to L1
            self.memory_cache.set(cache_hash, result)
            return result

        # Cache miss
        self._stats["misses"] += 1
        logger.debug(f"Cache miss: {key}")
        return None

    def set(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        data: pd.DataFrame,
        fields: Optional[List[str]] = None,
    ) -> None:
        """Save data to cache

        Write flow: L1 + L2 (both levels)

        Args:
            symbol: Security symbol
            timeframe: Time interval
            start_time: Start datetime
            end_time: End datetime
            data: DataFrame to cache
            fields: Optional list of fields
        """
        # Build cache key
        key = CacheKey(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            fields=fields or [],
        )
        cache_hash = key.to_hash()

        # Save to L1 (memory)
        self.memory_cache.set(cache_hash, data)

        # Save to L2 (disk)
        self.disk_cache.set(cache_hash, data, key_info=key.to_dict())

        logger.debug(f"Cache set: {key}")

    def invalidate(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> int:
        """Invalidate cache entries

        Args:
            symbol: Invalidate entries for this symbol (None = all)
            timeframe: Invalidate entries for this timeframe (None = all)

        Returns:
            Number of entries invalidated (-1 for full clear)
        """
        if symbol is None and timeframe is None:
            # Clear all caches
            self.memory_cache.clear()
            self.disk_cache.clear()
            logger.info("All caches cleared")
            return -1

        # TODO: Implement selective invalidation
        # For now, clear all caches
        self.memory_cache.clear()
        self.disk_cache.clear()
        logger.info(f"Caches cleared for symbol={symbol}, timeframe={timeframe}")
        return -1

    def get_stats(self) -> dict:
        """Get cache statistics

        Returns:
            Dictionary with comprehensive cache stats:
            - memory: L1 memory cache stats
            - disk: L2 disk cache stats
            - hits: Cache hit statistics
            - hit_rate: Overall cache hit rate
        """
        total_requests = (
            self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["misses"]
        )
        hit_rate = (
            (self._stats["l1_hits"] + self._stats["l2_hits"]) / total_requests
            if total_requests > 0
            else 0.0
        )

        return {
            "memory": self.memory_cache.get_stats(),
            "disk": self.disk_cache.get_stats(),
            "hits": {
                "l1_hits": self._stats["l1_hits"],
                "l2_hits": self._stats["l2_hits"],
                "misses": self._stats["misses"],
                "total_requests": total_requests,
                "hit_rate": hit_rate,
            },
        }

    def get_monitor(self) -> CacheMonitor:
        """Get the cache monitor instance

        Returns:
            CacheMonitor instance for monitoring and alerting
        """
        return self._monitor

    def get_monitor_report(self) -> str:
        """Get a human-readable monitoring report

        Returns:
            String report with cache performance summary
        """
        return self._monitor.get_report()

    def check_cache_health(self) -> list:
        """Check cache health and return any alerts

        Returns:
            List of HealthAlert objects
        """
        return self._monitor.check_health()

    def clear(self) -> None:
        """Clear all caches"""
        self.memory_cache.clear()
        self.disk_cache.clear()
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
        }
        logger.info("All caches cleared")

    def cleanup_old_entries(self, days: int = 30) -> int:
        """Clean up old disk cache entries

        Args:
            days: Delete entries older than this many days

        Returns:
            Number of entries deleted
        """
        return self.disk_cache.cleanup_old_entries(days=days)


# Global cache instance
_data_cache: Optional[DataCache] = None


def get_data_cache() -> DataCache:
    """Get global data cache instance

    Returns:
        Global DataCache instance
    """
    global _data_cache
    if _data_cache is None:
        _data_cache = DataCache()
    return _data_cache


def reset_data_cache() -> None:
    """Reset global cache instance"""
    global _data_cache
    if _data_cache is not None:
        _data_cache.clear()
    _data_cache = None
