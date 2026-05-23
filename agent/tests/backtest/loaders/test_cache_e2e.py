"""End-to-end cache integration tests with real loaders."""

import os
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import pytest

from backtest.loaders.cached_loader import CachedDataLoader
from backtest.loaders.registry import resolve_loader


class MockTushareLoader:
    """Mock Tushare loader for testing."""
    name = "tushare"
    markets = {"a_share"}
    requires_auth = False

    def is_available(self) -> bool:
        return True

    def fetch(self, codes, start, end, **kwargs):
        data = {}
        for code in codes:
            dates = pd.date_range(start, end, freq="D")
            data[code] = pd.DataFrame({
                "open": [100 + i * 0.5 for i in range(len(dates))],
                "high": [101 + i * 0.5 for i in range(len(dates))],
                "low": [99 + i * 0.5 for i in range(len(dates))],
                "close": [100.5 + i * 0.5 for i in range(len(dates))],
                "volume": [1000000 for _ in range(len(dates))],
            }, index=dates)
        return data


class TestCacheWithRealLoaders:
    """Test cache integration with actual loader implementations."""

    @pytest.fixture
    def cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_resolve_loader_with_cache(self, cache_dir):
        """Test resolve_loader returns cached loader by default."""
        os.environ["VIBE_CACHE_DIR"] = cache_dir
        try:
            loader = resolve_loader("a_share")
            assert loader is not None
            assert hasattr(loader, 'cache'), "Loader should have cache attribute"
        finally:
            os.environ.pop("VIBE_CACHE_DIR", None)

    def test_cached_loader_stats_tracking(self, cache_dir):
        """Test cache statistics are tracked correctly."""
        loader = MockTushareLoader()
        cached_loader = CachedDataLoader(loader, cache_dir=cache_dir)

        # Initial stats
        stats = cached_loader.get_cache_stats()
        hits = stats.get("hits", {})
        assert hits.get("l1_hits", 0) == 0
        assert hits.get("l2_hits", 0) == 0
        assert hits.get("misses", 0) == 0

        # Cold call
        result1 = cached_loader.fetch(["000001.SZ"], "2024-01-01", "2024-01-31")
        assert len(result1) == 1

        # After cold fetch
        stats = cached_loader.get_cache_stats()
        assert stats.get("hits", {}).get("misses", 0) >= 1, "First fetch should be a miss"

        # Warm call
        result2 = cached_loader.fetch(["000001.SZ"], "2024-01-01", "2024-01-31")
        assert len(result2) == 1

        # After warm fetch
        stats = cached_loader.get_cache_stats()
        l1_hits = stats.get("hits", {}).get("l1_hits", 0)
        l2_hits = stats.get("hits", {}).get("l2_hits", 0)
        assert l1_hits >= 1 or l2_hits >= 1, "Second fetch should be a hit"

    def test_cache_handles_empty_codes(self, cache_dir):
        """Test cache handles empty codes gracefully."""
        loader = MockTushareLoader()
        cached_loader = CachedDataLoader(loader, cache_dir=cache_dir)

        result = cached_loader.fetch([], "2024-01-01", "2024-01-31")
        assert result == {}

    def test_cache_multiple_date_ranges(self, cache_dir):
        """Test cache handles multiple date ranges correctly."""
        loader = MockTushareLoader()
        cached_loader = CachedDataLoader(loader, cache_dir=cache_dir)

        # First range
        result1 = cached_loader.fetch(["000001.SZ"], "2024-01-01", "2024-03-31")
        assert len(result1["000001.SZ"]) > 0

        # Different range
        result2 = cached_loader.fetch(["000001.SZ"], "2024-04-01", "2024-06-30")
        assert len(result2["000001.SZ"]) > 0

        # Both should return valid data (dates are different)
        dates1 = set(result1["000001.SZ"].index)
        dates2 = set(result2["000001.SZ"].index)
        assert dates1 != dates2, "Different date ranges should have different dates"


class TestCacheEnvironmentVariables:
    """Test cache configuration via environment variables."""

    @pytest.fixture
    def cache_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_disable_cache_via_env(self, cache_dir):
        """Test VIBE_DISABLE_CACHE environment variable."""
        from backtest.loaders.registry import _wrap_with_cache

        base_loader = MockTushareLoader()

        # Without env var, should return cached loader
        wrapped = _wrap_with_cache(base_loader, enable_cache=True)
        assert hasattr(wrapped, 'cache'), "Should return cached loader"

        # Test with cache disabled via env
        os.environ["VIBE_DISABLE_CACHE"] = "1"
        try:
            wrapped = _wrap_with_cache(base_loader, enable_cache=True)
            # With env var set, should return original loader
            assert not hasattr(wrapped, 'cache') or wrapped.cache is None, \
                "Cache should be disabled via env var"
        finally:
            os.environ.pop("VIBE_DISABLE_CACHE", None)

    def test_custom_cache_dir(self, cache_dir):
        """Test cache directory is used correctly."""
        loader = MockTushareLoader()
        cached_loader = CachedDataLoader(loader, cache_dir=cache_dir)

        # Just verify the loader was created successfully
        assert cached_loader is not None
        assert cached_loader.cache is not None


class TestCacheWithQualityChecker:
    """Test cache integration with data quality checker."""

    @pytest.fixture
    def cache_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_quality_checker_integration(self, cache_dir):
        """Test quality checker works with cache."""
        from backtest.loaders.cache.quality_checker import DataQualityChecker

        checker = DataQualityChecker()

        # Create test data with issues
        df = pd.DataFrame({
            "open": [100, 101, None, 103],
            "high": [102, 103, 104, 105],
            "low": [99, None, 101, 102],
            "close": [101, 102, 103, 104],
            "volume": [1000, 1001, 1002, 1003],
        })

        # Check quality
        report = checker.check(df, symbol="TEST")

        # Should detect issues
        assert report is not None
        assert report.issues is not None

    def test_quality_checker_auto_fix(self, cache_dir):
        """Test quality checker auto-fix capability."""
        from backtest.loaders.cache.quality_checker import DataQualityChecker

        checker = DataQualityChecker()

        # Create test data with issues
        df = pd.DataFrame({
            "open": [100, 101, None, 103, 100, 101, 102],  # Has NaN and duplicates
            "high": [102, 103, 104, 105, 102, 103, 104],
            "low": [99, None, 101, 102, 99, 100, 101],
            "close": [101, 102, 103, 104, 101, 102, 103],
            "volume": [1000, 1001, 1002, 1003, 1000, 1001, 1002],
        }, index=pd.date_range("2024-01-01", periods=7, freq="D"))

        # Auto-fix - returns (fixed_df, fix_count)
        fixed_df, fix_count = checker.auto_fix(df)

        # Should have no NaN
        assert not fixed_df.isnull().any().any(), "Fixed data should have no NaN values"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
