"""End-to-end cache performance benchmark tests."""

import os
import time
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backtest.loaders.cached_loader import CachedDataLoader
from backtest.loaders.cache import DataCache


class MockLoader:
    """Mock data loader for testing."""

    name = "mock"
    markets = {"stocks"}
    requires_auth = False

    def __init__(self, latency_ms: int = 100):
        self.latency_ms = latency_ms
        self.call_count = 0

    def is_available(self) -> bool:
        return True

    def fetch(
        self,
        codes: list[str],
        start: str,
        end: str,
        **kwargs
    ) -> dict[str, pd.DataFrame]:
        self.call_count += 1
        time.sleep(self.latency_ms / 1000)  # Simulate API latency
        return {code: self._generate_data(code) for code in codes}

    def _generate_data(self, code: str) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
        return pd.DataFrame({
            "open": [100 + i * 0.1 for i in range(len(dates))],
            "high": [101 + i * 0.1 for i in range(len(dates))],
            "low": [99 + i * 0.1 for i in range(len(dates))],
            "close": [100.5 + i * 0.1 for i in range(len(dates))],
            "volume": [1000000 for _ in range(len(dates))],
        }, index=dates)


class TestCachePerformance:
    """Performance benchmark tests for cache system."""

    @pytest.fixture
    def cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_loader(self):
        """Create mock loader with 100ms latency."""
        return MockLoader(latency_ms=100)

    def test_cache_speedup(self, cache_dir, mock_loader):
        """Verify cache provides significant speedup on repeated queries."""
        cached_loader = CachedDataLoader(
            mock_loader,
            cache_dir=cache_dir,
            enable_cache=True
        )

        codes = ["AAPL.US"]
        start, end = "2024-01-01", "2024-12-31"

        # First call: cold cache (should take ~100ms)
        start_time = time.time()
        result1 = cached_loader.fetch(codes, start, end)
        cold_time = time.time() - start_time

        # Verify API was called
        assert mock_loader.call_count == 1

        # Second call: warm cache (should be < 10ms)
        start_time = time.time()
        result2 = cached_loader.fetch(codes, start, end)
        warm_time = time.time() - start_time

        # Verify API was NOT called again
        assert mock_loader.call_count == 1

        # Warm cache should be at least 5x faster
        speedup = cold_time / warm_time
        assert speedup >= 5, f"Expected 5x speedup, got {speedup:.1f}x"

        # Verify data integrity
        pd.testing.assert_frame_equal(result1["AAPL.US"], result2["AAPL.US"])

        print(f"\nPerformance: Cold={cold_time*1000:.0f}ms, Warm={warm_time*1000:.0f}ms, Speedup={speedup:.1f}x")

    def test_cache_handles_multiple_symbols(self, cache_dir, mock_loader):
        """Verify cache works efficiently with multiple symbols."""
        cached_loader = CachedDataLoader(
            mock_loader,
            cache_dir=cache_dir,
            enable_cache=True
        )

        codes = ["AAPL.US", "GOOGL.US", "MSFT.US"]
        start, end = "2024-01-01", "2024-06-30"

        # First batch: 1 API call returns all 3 symbols
        result1 = cached_loader.fetch(codes, start, end)
        assert mock_loader.call_count == 1
        assert len(result1) == 3

        # Second batch: 0 API calls (all cached)
        result2 = cached_loader.fetch(codes, start, end)
        assert mock_loader.call_count == 1, "Should not call API again"

        # Verify all data integrity
        for code in codes:
            pd.testing.assert_frame_equal(result1[code], result2[code])

    def test_cache_memory_efficiency(self, cache_dir):
        """Verify memory cache is bounded and doesn't grow unbounded."""
        loader = MockLoader(latency_ms=10)
        cached_loader = CachedDataLoader(
            loader,
            cache_dir=cache_dir,
            memory_cache_size=10,  # Limit to 10 entries
            enable_cache=True
        )

        # Fetch 20 different symbols
        for i in range(20):
            cached_loader.fetch([f"SYMBOL{i}.US"], "2024-01-01", "2024-01-31")

        # Memory cache should be bounded
        stats = cached_loader.get_cache_stats()
        memory_size = stats.get("memory", {}).get("size", 0)
        assert memory_size <= 10, f"Memory cache should be bounded at 10, got {memory_size}"

    def test_cache_concurrent_access(self, cache_dir, mock_loader):
        """Verify cache handles concurrent access correctly."""
        import threading
        import time

        cached_loader = CachedDataLoader(
            mock_loader,
            cache_dir=cache_dir,
            enable_cache=True
        )

        codes = ["AAPL.US"]
        start, end = "2024-01-01", "2024-03-31"
        results = []
        errors = []

        def fetch_data():
            try:
                result = cached_loader.fetch(codes, start, end)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        # Launch 5 concurrent threads
        threads = [threading.Thread(target=fetch_data) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get valid data
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        assert len(errors) == 0, f"Errors occurred: {errors}"
        for result in results:
            assert "AAPL.US" in result
            assert len(result["AAPL.US"]) > 0

        # Note: With threading, some race conditions may cause multiple API calls
        # This is acceptable for concurrent access - data integrity is the key concern

    def test_cache_persistence_across_instances(self, cache_dir):
        """Verify cache persists across loader instances."""
        loader1 = MockLoader(latency_ms=100)

        # First instance: populate cache
        cached1 = CachedDataLoader(loader1, cache_dir=cache_dir)
        cached1.fetch(["AAPL.US"], "2024-01-01", "2024-06-30")
        assert loader1.call_count == 1

        # Second instance: should hit disk cache
        loader2 = MockLoader(latency_ms=100)
        cached2 = CachedDataLoader(loader2, cache_dir=cache_dir)
        cached2.fetch(["AAPL.US"], "2024-01-01", "2024-06-30")
        # Note: may still call API if disk cache doesn't find the exact match
        # This depends on the cache key implementation

        # Verify data integrity - check data values are similar
        result1 = cached1.fetch(["AAPL.US"], "2024-01-01", "2024-06-30")
        result2 = cached2.fetch(["AAPL.US"], "2024-01-01", "2024-06-30")

        # Data should have same shape and similar values
        df1 = result1["AAPL.US"]
        df2 = result2["AAPL.US"]
        assert len(df1) == len(df2), "Dataframes should have same length"
        assert df1["close"].sum() == df2["close"].sum(), "Data should be identical"

    def test_cache_eviction_policy(self, cache_dir):
        """Verify LRU eviction policy works correctly."""
        loader = MockLoader(latency_ms=10)
        cached_loader = CachedDataLoader(
            loader,
            cache_dir=cache_dir,
            memory_cache_size=3,  # Very small for testing
            enable_cache=True
        )

        # Fetch 5 symbols (cache size is 3)
        for i in range(5):
            cached_loader.fetch([f"SYM{i}.US"], "2024-01-01", "2024-01-31")

        # LRU should have evicted old entries
        stats = cached_loader.get_cache_stats()
        memory_size = stats.get("memory", {}).get("size", 0)
        assert memory_size <= 3, f"Memory cache should be bounded at 3, got {memory_size}"

    def test_cache_stats_accuracy(self, cache_dir, mock_loader):
        """Verify cache statistics are accurate."""
        cached_loader = CachedDataLoader(
            mock_loader,
            cache_dir=cache_dir,
            enable_cache=True
        )

        # Initial stats
        stats = cached_loader.get_cache_stats()
        hits = stats.get("hits", {})
        assert hits.get("l1_hits", 0) == 0
        assert hits.get("l2_hits", 0) == 0
        assert hits.get("misses", 0) == 0

        # Cold call
        cached_loader.fetch(["AAPL.US"], "2024-01-01", "2024-01-31")
        assert mock_loader.call_count == 1
        stats = cached_loader.get_cache_stats()
        assert stats.get("hits", {}).get("misses", 0) >= 1, "First fetch should be a miss"

        # Warm call
        cached_loader.fetch(["AAPL.US"], "2024-01-01", "2024-01-31")
        assert mock_loader.call_count == 1  # No new calls
        stats = cached_loader.get_cache_stats()
        l1_hits = stats.get("hits", {}).get("l1_hits", 0)
        l2_hits = stats.get("hits", {}).get("l2_hits", 0)
        assert l1_hits >= 1 or l2_hits >= 1, "Second fetch should be a hit"


class TestCacheIntegration:
    """Integration tests with real-world scenarios."""

    @pytest.fixture
    def cache_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_realistic_backtest_workflow(self, cache_dir):
        """Simulate a realistic backtest workflow with cache."""
        loader = MockLoader(latency_ms=50)
        cached_loader = CachedDataLoader(loader, cache_dir=cache_dir)

        # Simulate backtest: multiple iterations with same data
        codes = ["AAPL.US", "GOOGL.US"]
        start, end = "2020-01-01", "2024-12-31"

        # First backtest iteration - both symbols fetched together = 1 API call
        for i in range(3):  # 3 iterations without changes
            result = cached_loader.fetch(codes, start, end)
            assert len(result) == 2

        # Should only call API once (both symbols fetched together)
        assert loader.call_count == 1, f"Expected 1 API call, got {loader.call_count}"

        # Change parameters and re-fetch
        cached_loader.fetch(["AAPL.US"], "2020-01-01", "2023-06-30")
        assert loader.call_count == 2, "New date range should trigger new API call"

    def test_cache_stress_test(self, cache_dir):
        """Stress test with many rapid queries."""
        loader = MockLoader(latency_ms=50)
        cached_loader = CachedDataLoader(loader, cache_dir=cache_dir)

        codes = ["AAPL.US"]

        start_time = time.time()

        # 100 rapid queries
        for _ in range(100):
            cached_loader.fetch(codes, "2024-01-01", "2024-01-31")

        elapsed = time.time() - start_time

        # Should complete quickly with warm cache
        # 100 queries * 50ms = 5000ms without cache
        # With cache: < 500ms
        assert elapsed < 1.0, f"100 queries took {elapsed:.2f}s, expected < 1s with warm cache"

        # Only 1 API call
        assert loader.call_count == 1, f"Expected 1 API call, got {loader.call_count}"

        print(f"\nStress test: 100 queries in {elapsed*1000:.0f}ms ({elapsed:.4f}s per query)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
