"""Tests for enhanced MemoryCache features"""

import pytest
import pandas as pd
from datetime import datetime
from agent.backtest.loaders.cache.memory_cache import MemoryCache


class TestMemoryCacheEnhancedStats:
    """Test enhanced statistics in MemoryCache"""

    def setup_method(self):
        """Set up test fixtures"""
        self.cache = MemoryCache(max_size=10, max_memory_mb=1)

    def _create_sample_data(self, size_kb: float = 1.0) -> pd.DataFrame:
        """Create sample DataFrame with specified size"""
        rows = int(size_kb * 100)  # Approximate KB to rows
        return pd.DataFrame({
            'open': range(rows),
            'high': range(rows),
            'low': range(rows),
            'close': range(rows),
            'volume': range(rows),
        })

    def test_get_stats_contains_all_fields(self):
        """Test that get_stats returns all expected fields"""
        stats = self.cache.get_stats()

        assert 'entries' in stats
        assert 'memory_mb' in stats
        assert 'max_entries' in stats
        assert 'max_memory_mb' in stats
        assert 'total_hits' in stats
        assert 'hit_rate' in stats
        assert 'memory_usage_pct' in stats
        assert 'top_accessed' in stats

    def test_hit_rate_calculation(self):
        """Test hit rate calculation"""
        # Initially empty cache
        stats = self.cache.get_stats()
        assert stats['hit_rate'] == 0.0

        # Add some entries
        for i in range(3):
            df = self._create_sample_data(0.1)
            self.cache.set(f"hash_{i}", df)

        # All entries have 0 hits
        stats = self.cache.get_stats()
        assert stats['hit_rate'] == 0.0

        # Access some entries (creates hits)
        self.cache.get("hash_0")  # 1 hit
        self.cache.get("hash_0")  # 2 hits
        self.cache.get("hash_1")  # 1 hit

        stats = self.cache.get_stats()
        assert abs(stats['hit_rate'] - 0.666) < 0.01  # 2 out of 3 entries have hits

    def test_memory_usage_percentage(self):
        """Test memory usage percentage calculation"""
        stats = self.cache.get_stats()
        assert stats['memory_usage_pct'] == 0.0

        # Add data
        df = self._create_sample_data(100)  # ~100KB
        self.cache.set("test_hash", df)

        stats = self.cache.get_stats()
        assert stats['memory_usage_pct'] > 0.0
        assert stats['memory_usage_pct'] <= 1.0

    def test_top_accessed(self):
        """Test top accessed entries"""
        # Add entries
        for i in range(5):
            df = self._create_sample_data(0.1)
            self.cache.set(f"hash_{i}", df)

        # Access entries different number of times
        self.cache.get("hash_0")  # 1 hit
        self.cache.get("hash_0")  # 2 hits
        self.cache.get("hash_0")  # 3 hits
        self.cache.get("hash_1")  # 1 hit
        self.cache.get("hash_1")  # 2 hits
        self.cache.get("hash_2")  # 1 hit

        stats = self.cache.get_stats()
        top = stats['top_accessed']

        assert len(top) <= 5  # At most 5 entries
        assert top[0]['hit_count'] == 3  # hash_0 has most hits
        assert top[1]['hit_count'] == 2  # hash_1 has second most


class TestMemoryCacheLRU:
    """Test LRU eviction and related methods"""

    def setup_method(self):
        """Set up test fixtures"""
        self.cache = MemoryCache(max_size=5, max_memory_mb=1)

    def _create_sample_data(self, size_kb: float = 1.0) -> pd.DataFrame:
        """Create sample DataFrame with specified size"""
        rows = int(size_kb * 100)
        return pd.DataFrame({
            'open': range(rows),
            'high': range(rows),
            'low': range(rows),
            'close': range(rows),
            'volume': range(rows),
        })

    def test_get_least_recently_used(self):
        """Test getting LRU entries"""
        # Add entries in order
        for i in range(5):
            df = self._create_sample_data(0.1)
            self.cache.set(f"hash_{i}", df)

        # Access some entries (changes LRU order)
        self.cache.get("hash_0")  # Moves to end
        self.cache.get("hash_2")  # Moves to end

        lru = self.cache.get_least_recently_used(3)

        assert len(lru) == 3
        # hash_1 should be first LRU (least recently used)
        assert lru[0]['hash'] == 'hash_1'

    def test_get_least_recently_used_empty_cache(self):
        """Test LRU entries with empty cache"""
        lru = self.cache.get_least_recently_used(5)
        assert len(lru) == 0

    def test_get_eviction_candidates(self):
        """Test getting eviction candidates"""
        # Add entries
        for i in range(5):
            df = self._create_sample_data(0.1)
            self.cache.set(f"hash_{i}", df)

        # Access some entries to create hit counts
        self.cache.get("hash_0")  # 1 hit
        self.cache.get("hash_1")  # 1 hit
        # hash_2, hash_3, hash_4 have 0 hits

        candidates = self.cache.get_eviction_candidates(3)

        assert len(candidates) == 3
        # Entries with 0 hits should be candidates
        assert 'hash_2' in candidates
        assert 'hash_3' in candidates
        assert 'hash_4' in candidates

    def test_eviction_candidates_prefers_low_hits(self):
        """Test that eviction prefers entries with low hit counts"""
        # Add entries
        for i in range(5):
            df = self._create_sample_data(0.1)
            self.cache.set(f"hash_{i}", df)

        # Access to create different hit counts
        for _ in range(10):
            self.cache.get("hash_0")  # 10 hits
        for _ in range(5):
            self.cache.get("hash_1")  # 5 hits
        # hash_2, hash_3, hash_4 have 0 hits

        candidates = self.cache.get_eviction_candidates(3)

        # Should prioritize 0-hit entries
        assert candidates[0] in ['hash_2', 'hash_3', 'hash_4']


class TestMemoryCacheBackwardCompatibility:
    """Test backward compatibility with existing functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.cache = MemoryCache(max_size=10, max_memory_mb=1)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({
            'open': [100, 101, 102],
            'high': [102, 103, 104],
            'low': [99, 100, 101],
            'close': [101, 102, 103],
            'volume': [1000, 1001, 1002],
        })

    def test_basic_get_set_still_works(self):
        """Test that basic get/set operations still work"""
        df = self._create_sample_data()

        # Set and get
        self.cache.set("test_key", df)
        result = self.cache.get("test_key")

        assert result is not None
        assert len(result) == 3

    def test_lru_eviction_still_works(self):
        """Test that LRU eviction still works"""
        small_cache = MemoryCache(max_size=3, max_memory_mb=10)

        # Add more entries than max_size
        for i in range(5):
            df = self._create_sample_data()
            small_cache.set(f"hash_{i}", df)

        # Only last 3 entries should remain
        assert len(small_cache) == 3
        assert small_cache.get("hash_0") is None  # Evicted
        assert small_cache.get("hash_4") is not None  # Still there

    def test_clear_still_works(self):
        """Test that clear still works"""
        df = self._create_sample_data()

        self.cache.set("key1", df)
        self.cache.set("key2", df)

        assert len(self.cache) == 2

        self.cache.clear()

        assert len(self.cache) == 0
        assert self.cache.get("key1") is None

    def test_contains_still_works(self):
        """Test that __contains__ still works"""
        df = self._create_sample_data()

        self.cache.set("test_key", df)

        assert "test_key" in self.cache
        assert "other_key" not in self.cache


class TestMemoryCachePerformance:
    """Test performance characteristics"""

    def test_large_cache_handling(self):
        """Test handling large number of entries"""
        cache = MemoryCache(max_size=1000, max_memory_mb=100)

        df = pd.DataFrame({'data': range(100)})

        # Add 500 entries
        for i in range(500):
            cache.set(f"hash_{i}", df)

        stats = cache.get_stats()
        assert stats['entries'] <= 1000  # Should not exceed max_size

    def test_memory_limit_respected(self):
        """Test that memory limit is respected"""
        cache = MemoryCache(max_size=1000, max_memory_mb=1)  # 1 MB limit

        # Create larger DataFrames (~10KB each)
        df = pd.DataFrame({'data': range(10000)})

        # Add entries until memory limit is hit
        for i in range(200):
            cache.set(f"hash_{i}", df)

        stats = cache.get_stats()
        # Memory should be under limit
        assert stats['memory_usage_pct'] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
