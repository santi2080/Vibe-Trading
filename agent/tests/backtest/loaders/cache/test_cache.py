"""Unit tests for cache system"""

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from agent.backtest.loaders.cache import CacheKey, DataCache, DiskCache, MemoryCache


class TestCacheKey:
    """Test CacheKey functionality"""

    def test_hash_generation(self):
        """Test that hash is generated consistently"""
        key1 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )
        key2 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )

        assert key1.to_hash() == key2.to_hash()

    def test_different_symbols_different_hash(self):
        """Test that different symbols produce different hashes"""
        key1 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )
        key2 = CacheKey(
            symbol="ETH-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )

        assert key1.to_hash() != key2.to_hash()

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization"""
        key1 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            fields=["open", "close"],
        )

        data = key1.to_dict()
        key2 = CacheKey.from_dict(data)

        assert key1.to_hash() == key2.to_hash()
        assert key1.symbol == key2.symbol
        assert key1.timeframe == key2.timeframe


class TestMemoryCache:
    """Test MemoryCache functionality"""

    def test_basic_get_set(self):
        """Test basic get and set operations"""
        cache = MemoryCache(max_size=10, max_memory_mb=100)
        df = pd.DataFrame({"close": [100, 101, 102]})

        cache.set("test_hash", df)
        result = cache.get("test_hash")

        assert result is not None
        assert len(result) == 3
        pd.testing.assert_frame_equal(result, df)

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = MemoryCache()
        result = cache.get("nonexistent")

        assert result is None

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = MemoryCache(max_size=2, max_memory_mb=100)

        df1 = pd.DataFrame({"close": [100]})
        df2 = pd.DataFrame({"close": [200]})
        df3 = pd.DataFrame({"close": [300]})

        cache.set("hash1", df1)
        cache.set("hash2", df2)
        cache.set("hash3", df3)  # Should evict hash1

        assert cache.get("hash1") is None  # Evicted
        assert cache.get("hash2") is not None
        assert cache.get("hash3") is not None

    def test_lru_order_update(self):
        """Test that accessing an entry updates LRU order"""
        cache = MemoryCache(max_size=2, max_memory_mb=100)

        df1 = pd.DataFrame({"close": [100]})
        df2 = pd.DataFrame({"close": [200]})
        df3 = pd.DataFrame({"close": [300]})

        cache.set("hash1", df1)
        cache.set("hash2", df2)
        cache.get("hash1")  # Access hash1, making it most recent
        cache.set("hash3", df3)  # Should evict hash2, not hash1

        assert cache.get("hash1") is not None  # Still in cache
        assert cache.get("hash2") is None  # Evicted
        assert cache.get("hash3") is not None

    def test_clear(self):
        """Test clearing cache"""
        cache = MemoryCache()
        df = pd.DataFrame({"close": [100]})

        cache.set("test_hash", df)
        cache.clear()

        assert cache.get("test_hash") is None
        assert len(cache) == 0

    def test_stats(self):
        """Test cache statistics"""
        cache = MemoryCache(max_size=10, max_memory_mb=100)
        df = pd.DataFrame({"close": [100, 101, 102]})

        cache.set("test_hash", df)
        stats = cache.get_stats()

        assert stats["entries"] == 1
        assert stats["max_entries"] == 10
        assert stats["memory_mb"] > 0


class TestDiskCache:
    """Test DiskCache functionality"""

    def test_basic_get_set(self):
        """Test basic get and set operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir)
            df = pd.DataFrame({"close": [100, 101, 102]})

            cache.set("test_hash", df)
            result = cache.get("test_hash")

            assert result is not None
            assert len(result) == 3
            pd.testing.assert_frame_equal(result, df)

    def test_cache_miss(self):
        """Test cache miss returns None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir)
            result = cache.get("nonexistent")

            assert result is None

    def test_persistence(self):
        """Test that cache persists across instances"""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({"close": [100, 101, 102]})

            # Create cache and save data
            cache1 = DiskCache(cache_dir=tmpdir)
            cache1.set("test_hash", df)

            # Create new cache instance and retrieve data
            cache2 = DiskCache(cache_dir=tmpdir)
            result = cache2.get("test_hash")

            assert result is not None
            pd.testing.assert_frame_equal(result, df)

    def test_delete(self):
        """Test deleting cache entry"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir)
            df = pd.DataFrame({"close": [100]})

            cache.set("test_hash", df)
            assert cache.delete("test_hash") is True
            assert cache.get("test_hash") is None

    def test_clear(self):
        """Test clearing cache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir)
            df = pd.DataFrame({"close": [100]})

            cache.set("test_hash", df)
            cache.clear()

            assert cache.get("test_hash") is None
            assert len(cache) == 0

    def test_stats(self):
        """Test cache statistics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir)
            df = pd.DataFrame({"close": [100, 101, 102]})

            cache.set("test_hash", df)
            stats = cache.get_stats()

            assert stats["entries"] == 1
            assert stats["total_size_mb"] > 0


class TestDataCache:
    """Test DataCache three-level cache"""

    def test_l1_cache_hit(self):
        """Test L1 (memory) cache hit"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DataCache(cache_dir=tmpdir)
            df = pd.DataFrame({"close": [100, 101, 102]})

            cache.set(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
                data=df,
            )

            result = cache.get(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
            )

            assert result is not None
            pd.testing.assert_frame_equal(result, df)

            stats = cache.get_stats()
            assert stats["hits"]["l1_hits"] == 1

    def test_l2_cache_hit(self):
        """Test L2 (disk) cache hit after L1 eviction"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DataCache(cache_dir=tmpdir, memory_cache_size=1)
            df1 = pd.DataFrame({"close": [100]})
            df2 = pd.DataFrame({"close": [200]})

            # Set df1 (goes to L1 and L2)
            cache.set(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
                data=df1,
            )

            # Set df2 (evicts df1 from L1, but df1 still in L2)
            cache.set(
                symbol="ETH-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
                data=df2,
            )

            # Get df1 (should hit L2 and backfill to L1)
            result = cache.get(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
            )

            assert result is not None
            pd.testing.assert_frame_equal(result, df1)

            stats = cache.get_stats()
            assert stats["hits"]["l2_hits"] == 1

    def test_cache_miss(self):
        """Test cache miss"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DataCache(cache_dir=tmpdir)

            result = cache.get(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
            )

            assert result is None

            stats = cache.get_stats()
            assert stats["hits"]["misses"] == 1

    def test_hit_rate_calculation(self):
        """Test hit rate calculation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DataCache(cache_dir=tmpdir)
            df = pd.DataFrame({"close": [100]})

            # Set data
            cache.set(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
                data=df,
            )

            # Hit
            cache.get(
                symbol="BTC-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
            )

            # Miss
            cache.get(
                symbol="ETH-USDT",
                timeframe="1h",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 12, 31),
            )

            stats = cache.get_stats()
            assert stats["hits"]["hit_rate"] == 0.5  # 1 hit, 1 miss


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
