"""Integration tests for cache system with real data loaders."""

import os
import tempfile
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from backtest.loaders.registry import resolve_loader, _wrap_with_cache


class MockLoader:
    """Mock loader for testing cache integration."""

    name = "mock"
    markets = {"test_market"}
    requires_auth = False

    def __init__(self):
        self.fetch_count = 0

    def is_available(self):
        return True

    def fetch(self, codes, start_date, end_date, fields=None, interval="1D"):
        """Mock fetch that tracks call count."""
        self.fetch_count += 1
        result = {}
        for code in codes:
            df = pd.DataFrame({
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [99.0, 100.0, 101.0],
                "close": [104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200],
            }, index=pd.date_range(start_date, periods=3, freq="D"))
            df.index.name = "trade_date"
            result[code] = df
        return result


def test_wrap_with_cache_enabled():
    """Test that _wrap_with_cache wraps loader when enabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MockLoader()
        wrapped = _wrap_with_cache(loader, enable_cache=True)

        # Should be wrapped with CachedDataLoader
        assert wrapped.__class__.__name__ == "CachedDataLoader"
        assert hasattr(wrapped, "get_cache_stats")


def test_wrap_with_cache_disabled():
    """Test that _wrap_with_cache returns original loader when disabled."""
    loader = MockLoader()
    wrapped = _wrap_with_cache(loader, enable_cache=False)

    # Should be the original loader
    assert wrapped is loader
    assert wrapped.__class__.__name__ == "MockLoader"


def test_wrap_with_cache_env_disabled():
    """Test that VIBE_DISABLE_CACHE environment variable disables caching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MockLoader()

        # Set environment variable to disable cache
        with patch.dict(os.environ, {"VIBE_DISABLE_CACHE": "1"}):
            wrapped = _wrap_with_cache(loader, enable_cache=True)

        # Should be the original loader despite enable_cache=True
        assert wrapped is loader


def test_cached_loader_reduces_api_calls():
    """Test that cached loader reduces API calls for repeated queries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MockLoader()

        with patch.dict(os.environ, {"VIBE_CACHE_DIR": tmpdir}):
            wrapped = _wrap_with_cache(loader, enable_cache=True)

            # First fetch - should hit API
            result1 = wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader.fetch_count == 1
            assert "TEST.US" in result1
            assert len(result1["TEST.US"]) == 3

            # Second fetch with same parameters - should hit cache
            result2 = wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader.fetch_count == 1  # No additional API call
            assert "TEST.US" in result2

            # Verify data is identical
            pd.testing.assert_frame_equal(result1["TEST.US"], result2["TEST.US"])


def test_cached_loader_different_intervals():
    """Test that different intervals create separate cache entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MockLoader()

        # Set cache directory explicitly
        with patch.dict(os.environ, {"VIBE_CACHE_DIR": tmpdir}):
            wrapped = _wrap_with_cache(loader, enable_cache=True)

            # Fetch with 1D interval
            result1 = wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader.fetch_count == 1

            # Fetch with 1H interval - should hit API again
            result2 = wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1H")
            assert loader.fetch_count == 2

            # Fetch 1D again - should hit cache
            result3 = wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader.fetch_count == 2


def test_cached_loader_multiple_symbols():
    """Test that cache works correctly with multiple symbols."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MockLoader()

        with patch.dict(os.environ, {"VIBE_CACHE_DIR": tmpdir}):
            wrapped = _wrap_with_cache(loader, enable_cache=True)

            # Fetch multiple symbols
            result1 = wrapped.fetch(["AAPL.US", "MSFT.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader.fetch_count == 1
            assert "AAPL.US" in result1
            assert "MSFT.US" in result1

            # Fetch one cached symbol and one new symbol
            result2 = wrapped.fetch(["AAPL.US", "GOOGL.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader.fetch_count == 2  # Only GOOGL.US should hit API
            assert "AAPL.US" in result2
            assert "GOOGL.US" in result2


def test_cached_loader_stats():
    """Test that cache statistics are tracked correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MockLoader()

        with patch.dict(os.environ, {"VIBE_CACHE_DIR": tmpdir}):
            wrapped = _wrap_with_cache(loader, enable_cache=True)

            # First fetch - cache miss
            wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            stats = wrapped.get_cache_stats()
            assert stats["enabled"] is True
            assert stats["loader"] == "mock"

            # Second fetch - cache hit
            wrapped.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            stats = wrapped.get_cache_stats()
            assert stats["enabled"] is True


def test_resolve_loader_with_cache():
    """Test that resolve_loader returns cached loader by default."""
    with patch("backtest.loaders.registry.LOADER_REGISTRY", {"mock": MockLoader}):
        with patch("backtest.loaders.registry.FALLBACK_CHAINS", {"test_market": ["mock"]}):
            with patch("backtest.loaders.registry._registered", True):
                with tempfile.TemporaryDirectory() as tmpdir:
                    loader = resolve_loader("test_market", enable_cache=True)

                    # Should be wrapped
                    assert loader.__class__.__name__ == "CachedDataLoader"


def test_resolve_loader_without_cache():
    """Test that resolve_loader can return unwrapped loader."""
    with patch("backtest.loaders.registry.LOADER_REGISTRY", {"mock": MockLoader}):
        with patch("backtest.loaders.registry.FALLBACK_CHAINS", {"test_market": ["mock"]}):
            with patch("backtest.loaders.registry._registered", True):
                loader = resolve_loader("test_market", enable_cache=False)

                # Should be unwrapped
                assert loader.__class__.__name__ == "MockLoader"


def test_cache_persistence():
    """Test that cache persists across loader instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"VIBE_CACHE_DIR": tmpdir}):
            # First loader instance
            loader1 = MockLoader()
            wrapped1 = _wrap_with_cache(loader1, enable_cache=True)
            result1 = wrapped1.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")
            assert loader1.fetch_count == 1
            assert "TEST.US" in result1

            # Second loader instance with same cache directory
            loader2 = MockLoader()
            wrapped2 = _wrap_with_cache(loader2, enable_cache=True)
            result2 = wrapped2.fetch(["TEST.US"], "2024-01-01", "2024-01-10", interval="1D")

            # Should hit disk cache, not API
            assert loader2.fetch_count == 0
            assert "TEST.US" in result2

            # Verify data shape and values are identical
            assert result1["TEST.US"].shape == result2["TEST.US"].shape
            assert list(result1["TEST.US"].columns) == list(result2["TEST.US"].columns)
            assert (result1["TEST.US"]["close"].values == result2["TEST.US"]["close"].values).all()
