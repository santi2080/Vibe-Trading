"""Memory cache (L1) with LRU eviction policy

Fast in-memory cache with:
- LRU (Least Recently Used) eviction strategy
- Configurable max entries and memory limits
- Hit count tracking
- Memory usage monitoring
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata

    Attributes:
        data: Cached DataFrame
        created_at: Creation timestamp
        size_bytes: Memory size in bytes
        hit_count: Number of cache hits
    """

    data: pd.DataFrame
    created_at: datetime = field(default_factory=datetime.now)
    size_bytes: int = 0
    hit_count: int = 0

    def touch(self) -> None:
        """Increment hit count (called on cache hit)"""
        self.hit_count += 1


class MemoryCache:
    """L1 memory cache with LRU eviction

    Uses LRU (Least Recently Used) strategy to manage memory cache.
    When cache is full, evicts the least recently accessed entry.

    Attributes:
        max_size: Maximum number of entries
        max_memory_bytes: Maximum memory usage in bytes
    """

    def __init__(self, max_size: int = 100, max_memory_mb: int = 512):
        """Initialize memory cache

        Args:
            max_size: Maximum number of cache entries
            max_memory_mb: Maximum memory usage in MB
        """
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # LRU order (oldest first)
        self._current_memory = 0

    def get(self, cache_hash: str) -> Optional[pd.DataFrame]:
        """Get cached data

        Args:
            cache_hash: Cache key hash

        Returns:
            Cached DataFrame if exists, None otherwise
        """
        if cache_hash not in self._cache:
            return None

        entry = self._cache[cache_hash]
        entry.touch()

        # Update LRU order (move to end = most recently used)
        if cache_hash in self._access_order:
            self._access_order.remove(cache_hash)
        self._access_order.append(cache_hash)

        logger.debug(f"Memory cache hit: {cache_hash}")
        return entry.data.copy()

    def set(self, cache_hash: str, data: pd.DataFrame) -> None:
        """Set cache entry

        Args:
            cache_hash: Cache key hash
            data: DataFrame to cache
        """
        # Calculate data size
        size_bytes = data.memory_usage(deep=True).sum()

        # Evict entries if necessary
        while (
            len(self._cache) >= self.max_size
            or self._current_memory + size_bytes > self.max_memory_bytes
        ):
            if not self._access_order:
                break
            self._evict_oldest()

        # Create cache entry
        entry = CacheEntry(
            data=data.copy(),
            size_bytes=size_bytes,
        )

        self._cache[cache_hash] = entry
        self._access_order.append(cache_hash)
        self._current_memory += size_bytes

        logger.debug(
            f"Memory cache set: {cache_hash}, size: {size_bytes / 1024:.1f}KB"
        )

    def _evict_oldest(self) -> None:
        """Evict the least recently used entry"""
        if not self._access_order:
            return

        oldest_hash = self._access_order.pop(0)
        if oldest_hash in self._cache:
            entry = self._cache.pop(oldest_hash)
            self._current_memory -= entry.size_bytes
            logger.debug(f"Memory cache evicted: {oldest_hash}")

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._access_order.clear()
        self._current_memory = 0
        logger.info("Memory cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics

        Returns:
            Dictionary with cache stats:
            - entries: Number of cached entries
            - memory_mb: Current memory usage in MB
            - max_entries: Maximum allowed entries
            - max_memory_mb: Maximum allowed memory in MB
            - hit_rate: Cache hit rate (if tracked)
        """
        total_hits = sum(entry.hit_count for entry in self._cache.values())

        return {
            "entries": len(self._cache),
            "memory_mb": self._current_memory / (1024 * 1024),
            "max_entries": self.max_size,
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "total_hits": total_hits,
        }

    def __len__(self) -> int:
        """Return number of cached entries"""
        return len(self._cache)

    def __contains__(self, cache_hash: str) -> bool:
        """Check if cache hash exists"""
        return cache_hash in self._cache
