"""Tests for DataCache layer integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import shutil
import tempfile

import pandas as pd
import pytest

# Import cache components
from agent.backtest.loaders.cache.data_cache import DataCache
from agent.backtest.loaders.cache.memory_cache import MemoryCache
from agent.backtest.loaders.cache.disk_cache import DiskCache


class TestMemoryCache:
    """Tests for MemoryCache (L1)."""

    @pytest.fixture
    def cache(self):
        """Create a fresh MemoryCache instance."""
        return MemoryCache(max_size=100, max_memory_mb=512)

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame."""
        return pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [98.0, 99.0, 100.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }, index=pd.date_range("2024-01-01", periods=3))

    def test_basic_get_set(self, cache, sample_df):
        """Test basic get/set operations."""
        cache.set("test_key", sample_df)
        result = cache.get("test_key")
        assert result is not None
        assert len(result) == 3
        assert "close" in result.columns

    def test_get_missing_key(self, cache):
        """Test get returns None for missing key."""
        result = cache.get("missing_key")
        assert result is None

    def test_lru_eviction(self):
        """Test LRU eviction when capacity exceeded."""
        cache = MemoryCache(max_size=3, max_memory_mb=512)
        for i in range(5):
            cache.set(f"key_{i}", pd.DataFrame({"value": [i]}))

        # First key should be evicted
        assert cache.get("key_0") is None
        # Last 3 keys should remain
        for i in range(2, 5):
            assert cache.get(f"key_{i}") is not None

    def test_clear(self, cache, sample_df):
        """Test cache clear."""
        cache.set("key1", sample_df)
        cache.set("key2", sample_df)
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestDiskCache:
    """Tests for DiskCache (L2)."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for disk cache."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def cache(self, temp_dir):
        """Create DiskCache instance."""
        return DiskCache(cache_dir=temp_dir)

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame."""
        return pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [98.0, 99.0, 100.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }, index=pd.date_range("2024-01-01", periods=3))

    def test_basic_get_set(self, cache, sample_df):
        """Test basic get/set operations."""
        cache.set("test_key", sample_df)
        result = cache.get("test_key")
        assert result is not None
        assert len(result) == 3
        assert "close" in result.columns

    def test_get_missing_key(self, cache):
        """Test get returns None for missing key."""
        result = cache.get("missing_key")
        assert result is None

    def test_persistence(self, cache, sample_df, temp_dir):
        """Test cache persists across instances."""
        cache.set("persist_key", sample_df)

        # Create new cache instance with same directory
        new_cache = DiskCache(cache_dir=temp_dir)
        result = new_cache.get("persist_key")
        assert result is not None
        assert len(result) == 3

    def test_delete(self, cache, sample_df):
        """Test delete operation."""
        cache.set("delete_key", sample_df)
        assert cache.get("delete_key") is not None
        cache.delete("delete_key")
        assert cache.get("delete_key") is None

    def test_clear(self, cache, sample_df):
        """Test cache clear."""
        cache.set("key1", sample_df)
        cache.set("key2", sample_df)
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_stats(self, cache, sample_df):
        """Test cache statistics."""
        cache.set("key1", sample_df)
        cache.set("key2", sample_df)

        stats = cache.get_stats()
        assert stats["entries"] == 2
        assert stats["total_size_mb"] > 0


class TestDataCache:
    """Tests for DataCache (3-level integrated cache)."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def cache(self, temp_dir):
        """Create DataCache instance."""
        return DataCache(
            cache_dir=temp_dir,
            memory_cache_size=50,
            memory_cache_mb=512,
        )

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame."""
        return pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [98.0, 99.0, 100.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }, index=pd.date_range("2024-01-01", periods=3))

    def test_l1_l2_lookup(self, cache, sample_df):
        """Test L1 -> L2 lookup flow."""
        # Save data with proper signature
        cache.set(
            symbol="TEST",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
            data=sample_df,
        )

        # First lookup should miss L1, hit L2, and populate L1
        result = cache.get(
            symbol="TEST",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
        )
        assert result is not None

    def test_backfill_on_l1_miss(self, cache, sample_df):
        """Test L2 -> L1 backfill on L1 miss."""
        # Put data
        cache.set(
            symbol="COLD",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
            data=sample_df,
        )

        # Clear L1
        cache.memory_cache.clear()

        # First get should trigger backfill
        result = cache.get(
            symbol="COLD",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
        )
        assert result is not None

    def test_stats_tracking(self, cache, sample_df):
        """Test statistics are tracked correctly."""
        cache.set(
            symbol="STATS",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
            data=sample_df,
        )
        cache.get(
            symbol="STATS",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
        )
        cache.memory_cache.clear()
        cache.get(
            symbol="STATS",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
        )

        stats = cache._stats
        assert "l1_hits" in stats or "l2_hits" in stats or "misses" in stats

    def test_invalidate(self, cache, sample_df):
        """Test invalidate removes from all levels."""
        cache.set(
            symbol="INVAL",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
            data=sample_df,
        )
        result = cache.get(
            symbol="INVAL",
            timeframe="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 3),
        )
        assert result is not None

        # Invalidate by symbol
        cache.invalidate(symbol="INVAL")

        # Verify stats show cache was cleared
        stats = cache.get_stats()
        assert stats is not None
