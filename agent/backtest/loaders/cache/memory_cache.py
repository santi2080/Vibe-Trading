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
            Dictionary with comprehensive cache stats:
            - entries: Number of cached entries
            - memory_mb: Current memory usage in MB
            - max_entries: Maximum allowed entries
            - max_memory_mb: Maximum allowed memory in MB
            - total_hits: Total number of cache hits
            - hit_rate: Calculated hit rate (based on access order)
            - memory_usage_pct: Memory usage percentage
            - top_accessed: Top 5 most accessed entries
        """
        total_hits = sum(entry.hit_count for entry in self._cache.values())

        # Calculate hit rate based on access frequency
        hit_rate = self._calculate_hit_rate()

        # Get top accessed entries
        top_accessed = self._get_top_accessed(5)

        return {
            "entries": len(self._cache),
            "memory_mb": self._current_memory / (1024 * 1024),
            "max_entries": self.max_size,
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "total_hits": total_hits,
            "hit_rate": hit_rate,
            "memory_usage_pct": self._get_memory_usage_pct(),
            "top_accessed": top_accessed,
        }

    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate based on access patterns

        Returns:
            Hit rate as a percentage (0.0 to 1.0)
        """
        if not self._cache:
            return 0.0

        # Simple hit rate based on average hits per entry
        total_hits = sum(entry.hit_count for entry in self._cache.values())
        entries_with_hits = sum(1 for entry in self._cache.values() if entry.hit_count > 0)

        if entries_with_hits == 0:
            return 0.0

        # Hit rate = entries with hits / total entries
        return entries_with_hits / len(self._cache)

    def _get_memory_usage_pct(self) -> float:
        """Calculate memory usage percentage

        Returns:
            Memory usage as a percentage (0.0 to 1.0)
        """
        if self.max_memory_bytes == 0:
            return 0.0
        return self._current_memory / self.max_memory_bytes

    def _get_top_accessed(self, n: int = 5) -> List[dict]:
        """Get top N most accessed cache entries

        Args:
            n: Number of top entries to return

        Returns:
            List of dicts with hash, hit_count, and memory_kb for top entries
        """
        # Sort entries by hit count (descending)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].hit_count,
            reverse=True
        )

        # Return top N entries
        top_entries = []
        for cache_hash, entry in sorted_entries[:n]:
            top_entries.append({
                "hash": cache_hash[:8],  # Short hash for display
                "hit_count": entry.hit_count,
                "memory_kb": entry.size_bytes / 1024,
                "created": entry.created_at.isoformat(),
            })

        return top_entries

    def __len__(self) -> int:
        """Return number of cached entries"""
        return len(self._cache)

    def __contains__(self, cache_hash: str) -> bool:
        """Check if cache hash exists"""
        return cache_hash in self._cache

    def get_least_recently_used(self, n: int = 10) -> List[dict]:
        """Get least recently used entries (candidates for eviction)

        Args:
            n: Number of entries to return

        Returns:
            List of dicts with hash and last access time for LRU entries
        """
        # Access order is oldest first (LRU)
        lru_entries = []
        for cache_hash in self._access_order[:n]:
            if cache_hash in self._cache:
                entry = self._cache[cache_hash]
                lru_entries.append({
                    "hash": cache_hash[:8],
                    "hit_count": entry.hit_count,
                    "memory_kb": entry.size_bytes / 1024,
                    "created": entry.created_at.isoformat(),
                })

        return lru_entries

    def get_eviction_candidates(self, count: int = 5) -> List[str]:
        """Get cache hashes that are candidates for eviction

        These are the least recently used entries with lowest hit counts.

        Args:
            count: Number of candidates to return

        Returns:
            List of cache hashes to evict
        """
        # Combine LRU order with hit count
        candidates = []
        for cache_hash in self._access_order:
            if cache_hash in self._cache:
                entry = self._cache[cache_hash]
                # Score = position in LRU * (1 / (hit_count + 1))
                # Lower score = better candidate for eviction
                candidates.append((cache_hash, entry.hit_count))

        # Sort by hit count (ascending), then by LRU position
        candidates.sort(key=lambda x: (x[1], self._access_order.index(x[0])))

        return [c[0] for c in candidates[:count]]
