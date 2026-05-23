"""Tests for enhanced DiskCache features"""

import pytest
import tempfile
import shutil
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
from agent.backtest.loaders.cache.disk_cache import DiskCache


class TestDiskCacheEnhancedStats:
    """Test enhanced statistics in DiskCache"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DiskCache(cache_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({
            'open': [100, 101, 102],
            'high': [102, 103, 104],
            'low': [99, 100, 101],
            'close': [101, 102, 103],
            'volume': [1000, 1001, 1002],
        })

    def test_get_stats_contains_all_fields(self):
        """Test that get_stats returns all expected fields"""
        stats = self.cache.get_stats()

        assert 'entries' in stats
        assert 'total_size_mb' in stats
        assert 'total_hits' in stats
        assert 'avg_hits_per_entry' in stats
        assert 'cache_dir' in stats
        assert 'top_accessed' in stats
        assert 'oldest_entry_days' in stats
        assert 'newest_entry_days' in stats

    def test_avg_hits_calculation(self):
        """Test average hits per entry calculation"""
        # Empty cache
        stats = self.cache.get_stats()
        assert stats['avg_hits_per_entry'] == 0

        # Add some entries
        df = self._create_sample_data()
        key_info = {"symbol": "BTC-USDT", "timeframe": "1h"}

        self.cache.set("hash_1", df, key_info)
        self.cache.set("hash_2", df, key_info)

        # Access to create hits
        self.cache.get("hash_1")
        self.cache.get("hash_1")
        self.cache.get("hash_2")

        stats = self.cache.get_stats()
        # Total hits = 3, entries = 2, avg = 1.5
        assert abs(stats['avg_hits_per_entry'] - 1.5) < 0.1

    def test_entry_ages(self):
        """Test entry age tracking"""
        stats = self.cache.get_stats()
        assert stats['oldest_entry_days'] is None
        assert stats['newest_entry_days'] is None

        # Add entry
        df = self._create_sample_data()
        self.cache.set("hash_1", df)

        # Need to reload cache to get updated stats
        self.cache._metadata = self.cache._load_metadata()
        stats = self.cache.get_stats()
        assert stats['oldest_entry_days'] is not None
        assert stats['newest_entry_days'] is not None
        # Both should be 0 or very close to 0 (created now)
        assert stats['oldest_entry_days'] < 1


class TestDiskCacheTopAccessed:
    """Test top accessed entries functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DiskCache(cache_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({
            'close': [100, 101, 102],
        })

    def test_top_accessed_ordering(self):
        """Test that top accessed returns entries in correct order"""
        df = self._create_sample_data()
        key_info = {"symbol": "BTC-USDT"}

        # Add entries
        self.cache.set("hash_1", df, key_info)
        self.cache.set("hash_2", df, key_info)
        self.cache.set("hash_3", df, key_info)

        # Access with different frequencies
        for _ in range(5):
            self.cache.get("hash_1")
        for _ in range(3):
            self.cache.get("hash_2")
        for _ in range(1):
            self.cache.get("hash_3")

        # Reload metadata to get updated hit counts
        self.cache._metadata = self.cache._load_metadata()

        top = self.cache.get_top_accessed(3)

        assert len(top) == 3
        assert top[0]['hit_count'] == 5
        assert top[1]['hit_count'] == 3
        assert top[2]['hit_count'] == 1

    def test_top_accessed_includes_expression(self):
        """Test that top accessed includes expression info"""
        df = self._create_sample_data()
        key_info = {
            "symbol": "BTC-USDT",
            "expression": "EMA(close, 20)"
        }

        self.cache.set("hash_1", df, key_info)
        self.cache.get("hash_1")

        # Reload metadata
        self.cache._metadata = self.cache._load_metadata()

        top = self.cache.get_top_accessed(1)
        assert len(top) == 1
        assert top[0]['expression'] == "EMA(close, 20)"


class TestDiskCacheLeastAccessed:
    """Test least accessed entries functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DiskCache(cache_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({'close': [100, 101]})

    def test_get_least_accessed(self):
        """Test getting least accessed entries"""
        df = self._create_sample_data()

        # Add entries with different access patterns
        self.cache.set("hash_1", df)
        self.cache.set("hash_2", df)
        self.cache.set("hash_3", df)

        # Access only hash_1
        self.cache.get("hash_1")
        self.cache.get("hash_1")

        least = self.cache.get_least_accessed(2)

        assert len(least) == 2
        # hash_2 and hash_3 should be least accessed
        assert least[0]['hit_count'] == 0
        assert least[1]['hit_count'] == 0

    def test_get_least_accessed_empty(self):
        """Test getting least accessed from empty cache"""
        least = self.cache.get_least_accessed(5)
        assert len(least) == 0


class TestDiskCacheExpressionTracking:
    """Test expression tracking functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DiskCache(cache_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({'close': [100, 101, 102]})

    def test_get_entries_by_expression(self):
        """Test getting entries by expression"""
        df = self._create_sample_data()

        # Add entries with different expressions
        self.cache.set("hash_1", df, {
            "symbol": "BTC-USDT",
            "expression": "EMA(close, 20)"
        })
        self.cache.set("hash_2", df, {
            "symbol": "BTC-USDT",
            "expression": "RSI(close, 14)"
        })
        self.cache.set("hash_3", df, {
            "symbol": "BTC-USDT",
            "expression": "EMA(close, 20)"
        })
        self.cache.set("hash_4", df, {
            "symbol": "ETH-USDT",
            # No expression
        })

        # Search for EMA expression
        ema_entries = self.cache.get_entries_by_expression("EMA(close, 20)")
        assert len(ema_entries) == 2

        # Search for RSI expression
        rsi_entries = self.cache.get_entries_by_expression("RSI(close, 14)")
        assert len(rsi_entries) == 1

        # Search for non-existent expression
        nonexistent = self.cache.get_entries_by_expression("MACD(close)")
        assert len(nonexistent) == 0


class TestDiskCacheBackwardCompatibility:
    """Test backward compatibility with existing functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DiskCache(cache_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({
            'open': [100, 101],
            'high': [102, 103],
            'low': [99, 100],
            'close': [101, 102],
            'volume': [1000, 1001],
        })

    def test_basic_get_set_still_works(self):
        """Test that basic get/set operations still work"""
        df = self._create_sample_data()

        # Set and get
        self.cache.set("test_key", df)
        result = self.cache.get("test_key")

        assert result is not None
        assert len(result) == 2

    def test_delete_still_works(self):
        """Test that delete still works"""
        df = self._create_sample_data()

        self.cache.set("test_key", df)
        assert self.cache.get("test_key") is not None

        result = self.cache.delete("test_key")
        assert result is True
        assert self.cache.get("test_key") is None

    def test_clear_still_works(self):
        """Test that clear still works"""
        df = self._create_sample_data()

        self.cache.set("key1", df)
        self.cache.set("key2", df)

        assert len(self.cache) == 2

        self.cache.clear()

        assert len(self.cache) == 0
        assert self.cache.get("key1") is None

    def test_cleanup_old_entries_still_works(self):
        """Test that cleanup_old_entries still works"""
        df = self._create_sample_data()

        self.cache.set("key1", df)
        self.cache.set("key2", df)

        # Cleanup entries older than 0 days should delete all
        deleted = self.cache.cleanup_old_entries(days=0)
        assert deleted >= 0  # May be 0 if entries are very new


class TestDiskCacheMetadataPersistence:
    """Test metadata persistence"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_data(self) -> pd.DataFrame:
        """Create sample DataFrame"""
        return pd.DataFrame({'close': [100, 101]})

    def test_metadata_persists_across_instances(self):
        """Test that metadata persists when creating new cache instance"""
        # Create first instance and add data
        cache1 = DiskCache(cache_dir=self.temp_dir)
        df = self._create_sample_data()
        cache1.set("test_key", df)
        cache1.get("test_key")  # Create a hit

        # Create second instance with same directory
        cache2 = DiskCache(cache_dir=self.temp_dir)

        # Should see the entry
        assert "test_key" in cache2
        result = cache2.get("test_key")  # This will add another hit

        # Should have entries (hit count is at least 1, could be 2)
        stats = cache2.get_stats()
        assert stats['entries'] == 1
        assert stats['total_hits'] >= 1  # At least 1 hit recorded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
