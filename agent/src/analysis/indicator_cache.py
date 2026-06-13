"""Indicator calculation result caching.

This module provides caching for expensive indicator calculations to avoid
recomputing the same indicators for the same data multiple times.

PERF-01: Cache indicator results with hash key
PERF-02: LRU eviction when cache is full
PERF-03: Cache statistics tracking
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default cache configuration
DEFAULT_MAX_SIZE = 1000
DEFAULT_TTL_SECONDS = 3600  # 1 hour


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = DEFAULT_MAX_SIZE

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "max_size": self.max_size,
            "hit_rate": f"{self.hit_rate:.1%}",
        }


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    data: pd.DataFrame
    created_at: float = field(default_factory=time.time)
    access_count: int = 1

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if entry is expired."""
        return (time.time() - self.created_at) > ttl_seconds


class IndicatorCache:
    """LRU cache for indicator calculation results.

    Uses MD5 hash of (symbol, timeframe, indicator_type, params) as key.
    Supports TTL-based expiration and LRU eviction.

    Usage:
        cache = IndicatorCache(max_size=1000, ttl_seconds=3600)

        # Try to get cached result
        result = cache.get("AAPL", "1D", "sma", {"period": 20})
        if result is None:
            # Calculate and cache
            result = calculate_sma(df, period=20)
            cache.set("AAPL", "1D", "sma", {"period": 20}, result)
    """

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        enabled: bool = True,
    ):
        """Initialize cache.

        Args:
            max_size: Maximum number of entries (LRU eviction when exceeded).
            ttl_seconds: Time-to-live in seconds (0 = no expiration).
            enabled: Whether caching is enabled.
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        self._stats = CacheStats(max_size=max_size)

    @property
    def enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable caching."""
        self._enabled = value

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.size = len(self._cache)
        return self._stats

    def _make_key(
        self,
        symbol: str,
        timeframe: str,
        indicator_type: str,
        params: Dict[str, Any],
    ) -> str:
        """Generate cache key from parameters.

        Args:
            symbol: Trading symbol.
            timeframe: Data timeframe (e.g., "1D", "1H").
            indicator_type: Type of indicator (e.g., "sma", "ema", "rsi").
            params: Indicator parameters.

        Returns:
            MD5 hash string as cache key.
        """
        key_data = {
            "symbol": str(symbol),
            "timeframe": str(timeframe),
            "type": str(indicator_type),
            "params": params,
        }
        # Sort keys for consistent hashing
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()

    def get(
        self,
        symbol: str,
        timeframe: str,
        indicator_type: str,
        params: Dict[str, Any],
    ) -> Optional[pd.DataFrame]:
        """Get cached indicator result.

        Args:
            symbol: Trading symbol.
            timeframe: Data timeframe.
            indicator_type: Type of indicator.
            params: Indicator parameters.

        Returns:
            Cached DataFrame or None if not found/expired.
        """
        if not self._enabled:
            return None

        key = self._make_key(symbol, timeframe, indicator_type, params)
        entry = self._cache.get(key)

        if entry is None:
            self._stats.misses += 1
            return None

        # Check expiration
        if self._ttl_seconds > 0 and entry.is_expired(self._ttl_seconds):
            del self._cache[key]
            self._stats.misses += 1
            self._stats.evictions += 1
            return None

        # Update access count (for LRU tracking)
        entry.access_count += 1
        self._stats.hits += 1
        return entry.data

    def set(
        self,
        symbol: str,
        timeframe: str,
        indicator_type: str,
        params: Dict[str, Any],
        data: pd.DataFrame,
    ) -> None:
        """Cache indicator result.

        Args:
            symbol: Trading symbol.
            timeframe: Data timeframe.
            indicator_type: Type of indicator.
            params: Indicator parameters.
            data: Calculated indicator DataFrame to cache.
        """
        if not self._enabled or data is None or data.empty:
            return

        key = self._make_key(symbol, timeframe, indicator_type, params)

        # LRU eviction if at capacity
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._evict_lru()

        self._cache[key] = CacheEntry(data=data)

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with lowest access count
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].access_count)
        del self._cache[lru_key]
        self._stats.evictions += 1

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = CacheStats(max_size=self._max_size)

    def get_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def get_memory_estimate(self) -> int:
        """Estimate memory usage in bytes.

        This is a rough estimate based on DataFrame memory usage.
        """
        total = 0
        for entry in self._cache.values():
            if entry.data is not None:
                total += entry.data.memory_usage(deep=True).sum()
        return total


# Global cache instance (singleton pattern)
_global_cache: Optional[IndicatorCache] = None


def get_global_cache() -> IndicatorCache:
    """Get or create the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = IndicatorCache()
    return _global_cache


def clear_global_cache() -> None:
    """Clear the global cache."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()


def cached_indicator(
    indicator_type: str,
    symbol: str,
    timeframe: str,
    params: Dict[str, Any],
):
    """Decorator for caching indicator calculations.

    Usage:
        @cached_indicator("sma", symbol="AAPL", timeframe="1D", params={"period": 20})
        def calculate_sma(df, period):
            return df["close"].rolling(period).mean()

    Args:
        indicator_type: Type of indicator.
        symbol: Trading symbol.
        timeframe: Data timeframe.
        params: Indicator parameters.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_global_cache()

            # Try to get from cache
            result = cache.get(symbol, timeframe, indicator_type, params)
            if result is not None:
                logger.debug(f"Cache hit: {symbol}:{timeframe}:{indicator_type}")
                return result

            # Calculate and cache
            result = func(*args, **kwargs)
            cache.set(symbol, timeframe, indicator_type, params, result)
            return result

        return wrapper
    return decorator


# Convenience functions for common operations
def cache_sma(symbol: str, timeframe: str, period: int, data: pd.DataFrame) -> None:
    """Cache SMA calculation result."""
    get_global_cache().set(symbol, timeframe, "sma", {"period": period}, data)


def get_cached_sma(symbol: str, timeframe: str, period: int) -> Optional[pd.DataFrame]:
    """Get cached SMA result."""
    return get_global_cache().get(symbol, timeframe, "sma", {"period": period})


def cache_ema(symbol: str, timeframe: str, period: int, data: pd.DataFrame) -> None:
    """Cache EMA calculation result."""
    get_global_cache().set(symbol, timeframe, "ema", {"period": period}, data)


def get_cached_ema(symbol: str, timeframe: str, period: int) -> Optional[pd.DataFrame]:
    """Get cached EMA result."""
    return get_global_cache().get(symbol, timeframe, "ema", {"period": period})


def cache_rsi(symbol: str, timeframe: str, period: int, data: pd.DataFrame) -> None:
    """Cache RSI calculation result."""
    get_global_cache().set(symbol, timeframe, "rsi", {"period": period}, data)


def get_cached_rsi(symbol: str, timeframe: str, period: int) -> Optional[pd.DataFrame]:
    """Get cached RSI result."""
    return get_global_cache().get(symbol, timeframe, "rsi", {"period": period})


def cache_atr(symbol: str, timeframe: str, period: int, data: pd.DataFrame) -> None:
    """Cache ATR calculation result."""
    get_global_cache().set(symbol, timeframe, "atr", {"period": period}, data)


def get_cached_atr(symbol: str, timeframe: str, period: int) -> Optional[pd.DataFrame]:
    """Get cached ATR result."""
    return get_global_cache().get(symbol, timeframe, "atr", {"period": period})
