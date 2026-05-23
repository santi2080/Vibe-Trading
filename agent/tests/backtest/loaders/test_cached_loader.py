"""Unit tests for CachedDataLoader"""

import tempfile
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from agent.backtest.loaders.cached_loader import CachedDataLoader


class MockDataLoader:
    """Mock data loader for testing"""

    def __init__(self):
        self.name = "mock"
        self.markets = {"test_market"}
        self.requires_auth = False
        self.fetch_count = 0

    def is_available(self):
        return True

    def fetch(self, codes, start_date, end_date, fields=None, interval="1D"):
        """Mock fetch that returns test data"""
        self.fetch_count += 1
        results = {}
        for code in codes:
            # Generate simple test data
            dates = pd.date_range(start=start_date, end=end_date, freq="D")
            data = pd.DataFrame(
                {
                    "open": range(100, 100 + len(dates)),
                    "high": range(101, 101 + len(dates)),
                    "low": range(99, 99 + len(dates)),
                    "close": range(100, 100 + len(dates)),
                    "volume": [1000] * len(dates),
                },
                index=dates,
            )
            data.index.name = "trade_date"
            results[code] = data
        return results


class TestCachedDataLoader:
    """Test CachedDataLoader functionality"""

    def test_basic_fetch_with_cache(self):
        """Test basic fetch with caching enabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            # First fetch - should hit the base loader
            result1 = cached_loader.fetch(
                ["TEST.US"], "2024-01-01", "2024-01-10", interval="1D"
            )

            assert "TEST.US" in result1
            assert len(result1["TEST.US"]) == 10
            assert mock_loader.fetch_count == 1

            # Second fetch - should hit the cache
            result2 = cached_loader.fetch(
                ["TEST.US"], "2024-01-01", "2024-01-10", interval="1D"
            )

            assert "TEST.US" in result2
            assert len(result2["TEST.US"]) == 10
            assert mock_loader.fetch_count == 1  # No additional fetch

            # Verify data is identical
            pd.testing.assert_frame_equal(result1["TEST.US"], result2["TEST.US"])

    def test_cache_disabled(self):
        """Test that caching can be disabled"""
        mock_loader = MockDataLoader()
        cached_loader = CachedDataLoader(mock_loader, enable_cache=False)

        # First fetch
        result1 = cached_loader.fetch(
            ["TEST.US"], "2024-01-01", "2024-01-10", interval="1D"
        )
        assert mock_loader.fetch_count == 1

        # Second fetch - should hit the base loader again
        result2 = cached_loader.fetch(
            ["TEST.US"], "2024-01-01", "2024-01-10", interval="1D"
        )
        assert mock_loader.fetch_count == 2  # Additional fetch

    def test_multiple_symbols(self):
        """Test fetching multiple symbols with caching"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            # Fetch two symbols
            result1 = cached_loader.fetch(
                ["TEST1.US", "TEST2.US"], "2024-01-01", "2024-01-10", interval="1D"
            )

            assert "TEST1.US" in result1
            assert "TEST2.US" in result1
            assert mock_loader.fetch_count == 1

            # Fetch one cached, one new
            result2 = cached_loader.fetch(
                ["TEST1.US", "TEST3.US"], "2024-01-01", "2024-01-10", interval="1D"
            )

            assert "TEST1.US" in result2
            assert "TEST3.US" in result2
            assert mock_loader.fetch_count == 2  # Only fetched TEST3.US

    def test_different_intervals(self):
        """Test that different intervals are cached separately"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            # Fetch with 1D interval
            result1 = cached_loader.fetch(
                ["TEST.US"], "2024-01-01", "2024-01-10", interval="1D"
            )
            assert mock_loader.fetch_count == 1

            # Fetch with 1H interval - should miss cache
            result2 = cached_loader.fetch(
                ["TEST.US"], "2024-01-01", "2024-01-10", interval="1H"
            )
            assert mock_loader.fetch_count == 2

    def test_different_date_ranges(self):
        """Test that different date ranges are cached separately"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            # Fetch first date range
            result1 = cached_loader.fetch(
                ["TEST.US"], "2024-01-01", "2024-01-10", interval="1D"
            )
            assert mock_loader.fetch_count == 1

            # Fetch different date range - should miss cache
            result2 = cached_loader.fetch(
                ["TEST.US"], "2024-02-01", "2024-02-10", interval="1D"
            )
            assert mock_loader.fetch_count == 2

    def test_cache_stats(self):
        """Test cache statistics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            # Initial stats
            stats = cached_loader.get_cache_stats()
            assert stats["enabled"] is True
            assert stats["loader"] == "mock"

            # Fetch some data
            cached_loader.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")

            # Check stats after fetch
            stats = cached_loader.get_cache_stats()
            assert "hits" in stats
            assert stats["hits"]["l1_hits"] >= 0
            assert stats["hits"]["l2_hits"] >= 0
            assert stats["hits"]["misses"] >= 0

    def test_cache_stats_disabled(self):
        """Test cache statistics when cache is disabled"""
        mock_loader = MockDataLoader()
        cached_loader = CachedDataLoader(mock_loader, enable_cache=False)

        stats = cached_loader.get_cache_stats()
        assert stats["enabled"] is False

    def test_clear_cache(self):
        """Test clearing cache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            # Fetch and cache data
            cached_loader.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert mock_loader.fetch_count == 1

            # Clear cache
            cached_loader.clear_cache()

            # Fetch again - should hit base loader
            cached_loader.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert mock_loader.fetch_count == 2

    def test_loader_properties(self):
        """Test that loader properties are delegated correctly"""
        mock_loader = MockDataLoader()
        cached_loader = CachedDataLoader(mock_loader)

        assert cached_loader.name == "mock"
        assert cached_loader.markets == {"test_market"}
        assert cached_loader.requires_auth is False
        assert cached_loader.is_available() is True

    def test_empty_codes(self):
        """Test fetching with empty codes list"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loader = MockDataLoader()
            cached_loader = CachedDataLoader(mock_loader, cache_dir=tmpdir)

            result = cached_loader.fetch([], "2024-01-01", "2024-01-10", interval="1D")
            assert result == {}
            assert mock_loader.fetch_count == 0  # Should not call base loader for empty list


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
