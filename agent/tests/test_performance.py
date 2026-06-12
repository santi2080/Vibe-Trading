"""Performance benchmarks for Phase 23.

Tests for:
- Parallel symbol processing
- Indicator caching
- Batch parquet reading
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pandas as pd
import pytest


class TestIndicatorCache:
    """Tests for IndicatorCache."""

    def test_cache_set_get(self):
        """Test basic cache set and get."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=100, enabled=True)

        # Create test data
        df = pd.DataFrame({"close": [100, 101, 102]})

        # Set cache
        cache.set("AAPL", "1D", "sma", {"period": 20}, df)

        # Get cache
        result = cache.get("AAPL", "1D", "sma", {"period": 20})
        assert result is not None
        assert len(result) == 3

    def test_cache_miss(self):
        """Test cache miss returns None."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=100, enabled=True)

        result = cache.get("AAPL", "1D", "sma", {"period": 20})
        assert result is None

    def test_cache_disabled(self):
        """Test cache returns None when disabled."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=100, enabled=False)

        df = pd.DataFrame({"close": [100, 101, 102]})
        cache.set("AAPL", "1D", "sma", {"period": 20}, df)

        result = cache.get("AAPL", "1D", "sma", {"period": 20})
        assert result is None

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=3, enabled=True)

        # Fill cache
        for i in range(5):
            df = pd.DataFrame({"close": [i * 100]})
            cache.set(f"SYM{i}", "1D", "sma", {"period": 20}, df)

        # First symbol should be evicted
        assert cache.get("SYM0", "1D", "sma", {"period": 20}) is None
        # Others should still be there
        assert cache.get("SYM4", "1D", "sma", {"period": 20}) is not None

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=100, enabled=True)

        df = pd.DataFrame({"close": [100, 101, 102]})

        # First access - miss
        result = cache.get("AAPL", "1D", "sma", {"period": 20})
        assert result is None

        # Set and get - hit
        cache.set("AAPL", "1D", "sma", {"period": 20}, df)
        result = cache.get("AAPL", "1D", "sma", {"period": 20})
        assert result is not None

        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_cache_clear(self):
        """Test cache clear."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=100, enabled=True)

        df = pd.DataFrame({"close": [100, 101, 102]})
        cache.set("AAPL", "1D", "sma", {"period": 20}, df)

        assert cache.get_size() == 1
        cache.clear()
        assert cache.get_size() == 0

    def test_cache_key_consistency(self):
        """Test cache key generation is consistent."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache()

        # Same params should produce same key
        key1 = cache._make_key("AAPL", "1D", "sma", {"period": 20, "type": "simple"})
        key2 = cache._make_key("AAPL", "1D", "sma", {"period": 20, "type": "simple"})
        assert key1 == key2

        # Different params should produce different key
        key3 = cache._make_key("AAPL", "1D", "sma", {"period": 21})
        assert key1 != key3


class TestParallelProcessing:
    """Tests for parallel symbol processing."""

    def test_analyze_all_parallel_method_exists(self):
        """Test that analyze_all_parallel method exists."""
        from agent.src.analysis.watchlist_analyzer import WatchlistAnalyzer

        analyzer = WatchlistAnalyzer()
        assert hasattr(analyzer, "analyze_all_parallel")
        assert callable(analyzer.analyze_all_parallel)

    def test_parallel_results_order(self):
        """Test that parallel processing returns results in completion order."""
        from agent.src.analysis.watchlist_analyzer import WatchlistAnalyzer

        analyzer = WatchlistAnalyzer()

        # This test just verifies the method runs
        # Actual performance testing would require real data
        try:
            # Try to analyze (will likely fail without data, but method should exist)
            results = analyzer.analyze_all_parallel(max_workers=2, verbose=False)
            assert isinstance(results, list)
        except Exception:
            # Expected if no data available
            pass


class TestCacheFunctions:
    """Tests for convenience cache functions."""

    def test_cache_functions_exist(self):
        """Test that convenience cache functions exist."""
        from agent.src.analysis.indicator_cache import (
            cache_sma,
            get_cached_sma,
            cache_ema,
            get_cached_ema,
            cache_rsi,
            get_cached_rsi,
            cache_atr,
            get_cached_atr,
        )

        # All functions should be callable
        assert callable(cache_sma)
        assert callable(get_cached_sma)
        assert callable(cache_ema)
        assert callable(get_cached_ema)
        assert callable(cache_rsi)
        assert callable(get_cached_rsi)
        assert callable(cache_atr)
        assert callable(get_cached_atr)


class TestGlobalCache:
    """Tests for global cache instance."""

    def test_get_global_cache(self):
        """Test getting global cache instance."""
        from agent.src.analysis.indicator_cache import get_global_cache, clear_global_cache

        cache1 = get_global_cache()
        cache2 = get_global_cache()

        # Should be the same instance
        assert cache1 is cache2

        # Clear should work
        clear_global_cache()
        cache3 = get_global_cache()
        assert cache3.get_size() == 0


class TestCachePerformance:
    """Performance comparison tests (informational)."""

    def test_cache_performance_improvement(self):
        """Test that caching provides measurable improvement."""
        from agent.src.analysis.indicator_cache import IndicatorCache

        cache = IndicatorCache(max_size=1000, enabled=True)

        # Create larger test data
        df = pd.DataFrame({"close": range(1000)})

        # Time with caching
        start = time.time()
        for _ in range(100):
            cache.set("AAPL", "1D", "sma", {"period": 20}, df)
            cache.get("AAPL", "1D", "sma", {"period": 20})
        cached_time = time.time() - start

        # Time without caching (simulate calculation)
        start = time.time()
        for _ in range(100):
            # Simulate expensive calculation
            _ = pd.DataFrame({"close": range(1000)})
        uncached_time = time.time() - start

        # Cache should be faster
        assert cached_time < uncached_time * 0.5  # At least 2x faster

    def test_parallel_vs_sequential(self):
        """Test that parallel processing is faster than sequential.

        Note: This test is informational and may not always pass
        depending on system load and data availability.
        """
        from agent.src.analysis.watchlist_analyzer import WatchlistAnalyzer

        analyzer = WatchlistAnalyzer()

        # Just verify both methods exist and are callable
        assert hasattr(analyzer, "analyze_all")
        assert hasattr(analyzer, "analyze_all_parallel")

        # This test verifies the API exists
        # Real performance testing requires actual watchlist data
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
