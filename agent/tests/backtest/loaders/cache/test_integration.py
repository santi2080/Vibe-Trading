"""Integration tests for the complete cache system.

Tests the integration of all cache components:
- DataCache with MemoryCache and DiskCache
- CacheMonitor for performance tracking
- DataQualityChecker for data validation
- IncrementalUpdater for efficient updates

Run with: pytest agent/tests/backtest/loaders/cache/test_integration.py -v
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

from agent.backtest.loaders.cache import (
    DataCache,
    CacheKey,
)
from agent.backtest.loaders.cache.cache_monitor import CacheMonitor
from agent.backtest.loaders.cache.quality_checker import DataQualityChecker
from agent.backtest.loaders.cache.incremental_updater import (
    IncrementalUpdater,
    UpdateMetadata,
)


def create_sample_ohlcv(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    freq: str = "1h",
) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    n = len(dates)

    # Generate realistic price data
    base_price = 100.0
    returns = np.random.randn(n) * 0.02
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(n)) * 0.01),
            "low": prices * (1 - np.abs(np.random.randn(n)) * 0.01),
            "close": prices,
            "volume": np.random.randint(1000, 10000, n),
        },
        index=dates,
    )

    # Ensure OHLC consistency
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)

    df.index.name = "timestamp"
    return df


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for tests."""
    return create_sample_ohlcv(
        symbol="BTC-USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 7),
        freq="1h",
    )


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "cache"


@pytest.fixture
def data_cache(temp_cache_dir):
    """Create DataCache instance."""
    return DataCache(
        cache_dir=str(temp_cache_dir),
        memory_cache_size=50,
        memory_cache_mb=128,
    )


@pytest.fixture
def checker():
    """Create DataQualityChecker instance."""
    return DataQualityChecker()


@pytest.fixture
def updater():
    """Create IncrementalUpdater instance (no cache parameter)."""
    return IncrementalUpdater()


@pytest.fixture
def monitor(data_cache):
    """Get CacheMonitor from DataCache."""
    return data_cache.get_monitor()


class TestDataCacheIntegration:
    """Integration tests for DataCache with all components."""

    def test_full_cache_workflow(self, data_cache, sample_data):
        """Test complete cache workflow: set, get, monitor."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        # Cache the data
        data_cache.set(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            data=sample_data,
        )

        # Should be able to retrieve it
        cached_data = data_cache.get(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
        )

        assert cached_data is not None
        assert len(cached_data) == len(sample_data)

    def test_cache_with_fields(self, data_cache, sample_data):
        """Test cache with fields filter."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)
        fields = ["close", "volume"]

        # Cache data with specific fields
        data_cache.set(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            data=sample_data,
            fields=fields,
        )

        # Should be able to retrieve with same fields
        cached = data_cache.get(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            fields=fields,
        )
        assert cached is not None

    def test_get_stats(self, data_cache, sample_data):
        """Test cache statistics."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        # Initial stats
        stats = data_cache.get_stats()
        # Stats have nested structure with 'hits', 'memory', 'disk'
        assert "hits" in stats
        assert "memory" in stats
        assert "disk" in stats

        # Cache data
        data_cache.set(symbol, timeframe, start_time, end_time, sample_data)

        # After caching
        cached = data_cache.get(symbol, timeframe, start_time, end_time)
        assert cached is not None


class TestCacheMonitorIntegration:
    """Integration tests for CacheMonitor with DataCache."""

    def test_monitor_collects_metrics(self, data_cache, monitor, sample_data):
        """Test that monitor collects performance metrics."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        # Cache some data
        data_cache.set(symbol, timeframe, start_time, end_time, sample_data)

        # Collect metrics - get_report returns a string
        report = monitor.get_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_monitor_detects_health_issues(self, data_cache, monitor, sample_data):
        """Test that monitor detects cache health issues."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        # Add data
        data_cache.set(symbol, timeframe, start_time, end_time, sample_data)

        # Create health check
        alerts = monitor.check_health()
        assert isinstance(alerts, list)

    def test_monitor_generates_report(self, data_cache, monitor, sample_data):
        """Test that monitor generates comprehensive report."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        data_cache.set(symbol, timeframe, start_time, end_time, sample_data)

        report = monitor.get_report()
        assert isinstance(report, str)
        assert len(report) > 0
        # Report should contain key sections
        assert "Cache" in report or "缓存" in report


class TestDataQualityCheckerIntegration:
    """Integration tests for DataQualityChecker."""

    def test_check_valid_data(self, checker):
        """Test checking valid OHLCV data."""
        df = create_sample_ohlcv(
            symbol="ETH-USDT",
            start_date=datetime(2024, 2, 1),
            end_date=datetime(2024, 2, 7),
            freq="1h",
        )

        report = checker.check(df, symbol="ETH-USDT")

        # QualityReport is a dataclass with dict fields using 'status' key
        # Check core fields - timeliness may warn for old test data
        assert report.symbol == "ETH-USDT"
        # completeness and consistency should pass
        assert report.completeness.get("status") == "passed"
        assert report.consistency.get("status") == "passed"

    def test_check_with_issues(self, checker):
        """Test checking data with quality issues."""
        df = create_sample_ohlcv(
            symbol="ETH-USDT",
            start_date=datetime(2024, 2, 1),
            end_date=datetime(2024, 2, 7),
            freq="1h",
        )

        # Introduce quality issues - set close to NaN
        df.iloc[10, df.columns.get_loc("close")] = np.nan

        report = checker.check(df, symbol="ETH-USDT")

        # Should detect issues - completeness should have warning
        assert report.completeness.get("status") == "warning"
        # There should be at least one issue
        assert len(report.issues) >= 1

    def test_auto_fix(self, checker):
        """Test auto-fix functionality."""
        df = create_sample_ohlcv(
            symbol="ETH-USDT",
            start_date=datetime(2024, 2, 1),
            end_date=datetime(2024, 2, 7),
            freq="1h",
        )

        # Introduce issues
        df.iloc[10, df.columns.get_loc("close")] = np.nan

        # Auto-fix returns (DataFrame, fix_count)
        fixed_df, fix_count = checker.auto_fix(df)

        # Check that issues are fixed
        assert fixed_df.isnull().sum().sum() == 0  # No missing values
        # OHLC should be consistent
        assert (fixed_df["high"] >= fixed_df["low"]).all()

    def test_check_with_duplicates(self, checker):
        """Test detection of duplicate timestamps."""
        df = create_sample_ohlcv(
            symbol="ETH-USDT",
            start_date=datetime(2024, 2, 1),
            end_date=datetime(2024, 2, 7),
            freq="1h",
        )

        # Add duplicate index (force it with a duplicate row first)
        dup_idx = df.index[5]
        df.loc[dup_idx] = df.iloc[6]
        # Now we have a true duplicate index
        df = pd.concat([df, df.iloc[[5]]])  # Add another row with same index

        report = checker.check(df, symbol="ETH-USDT")
        # uniqueness should have warning for duplicates
        assert report.uniqueness.get("status") == "warning"

    def test_get_summary(self, checker):
        """Test report summary generation."""
        df = create_sample_ohlcv(
            symbol="ETH-USDT",
            start_date=datetime(2024, 2, 1),
            end_date=datetime(2024, 2, 7),
            freq="1h",
        )

        report = checker.check(df, symbol="ETH-USDT")
        summary = report.get_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "ETH-USDT" in summary


class TestIncrementalUpdaterIntegration:
    """Integration tests for IncrementalUpdater."""

    def test_needs_update_first_fetch(self, updater):
        """Test that first fetch always needs update."""
        # needs_update returns (bool, reason)
        needs, reason = updater.needs_update(
            symbol="BTC-USDT",
            timeframe="1h",
        )
        assert needs is True
        assert reason == "no_metadata"

    def test_needs_update_after_metadata(self, updater):
        """Test update detection with existing metadata."""
        symbol = "BTC-USDT"
        timeframe = "1h"

        # Save some metadata
        metadata = UpdateMetadata(
            symbol=symbol,
            timeframe=timeframe,
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-01-07",
            row_count=100,
        )
        updater.save_metadata(metadata)

        # Should not need update immediately (check_frequency is 24 hours)
        needs, reason = updater.needs_update(
            symbol=symbol,
            timeframe=timeframe,
        )
        # Recent update should not need another
        assert needs is False

    def test_needs_update_force(self, updater):
        """Test force update."""
        needs, reason = updater.needs_update(
            symbol="BTC-USDT",
            timeframe="1h",
            force=True,
        )
        assert needs is True
        assert reason == "forced"

    def test_get_stats(self, updater):
        """Test updater statistics."""
        stats = updater.get_stats()
        assert isinstance(stats, dict)
        assert "metadata_count" in stats

    def test_save_and_get_metadata(self, updater):
        """Test saving and retrieving metadata."""
        metadata = UpdateMetadata(
            symbol="BTC-USDT",
            timeframe="1d",
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-01-31",
            row_count=30,
        )
        updater.save_metadata(metadata)

        retrieved = updater.get_metadata("BTC-USDT", "1d")
        assert retrieved is not None
        assert retrieved.symbol == "BTC-USDT"
        assert retrieved.row_count == 30

    def test_clear_metadata(self, updater):
        """Test clearing metadata."""
        metadata = UpdateMetadata(
            symbol="BTC-USDT",
            timeframe="1h",
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-01-07",
            row_count=100,
        )
        updater.save_metadata(metadata)

        # Verify it exists
        assert updater.get_metadata("BTC-USDT", "1h") is not None

        # Clear it
        updater.clear_metadata("BTC-USDT", "1h")

        # Should be gone
        assert updater.get_metadata("BTC-USDT", "1h") is None


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    def test_complete_data_pipeline(self, data_cache, checker, updater, sample_data):
        """Test complete data pipeline: fetch -> cache -> validate -> update."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        # Step 1: Initial fetch and cache
        data_cache.set(symbol, timeframe, start_time, end_time, sample_data)

        # Step 2: Retrieve and validate
        cached_data = data_cache.get(symbol, timeframe, start_time, end_time)
        assert cached_data is not None

        quality_report = checker.check(cached_data, symbol)
        # completeness and consistency should pass (timeliness may warn for old test data)
        assert quality_report.completeness.get("status") == "passed"
        assert quality_report.consistency.get("status") == "passed"

        # Step 3: Check update status - needs_update returns (bool, reason)
        needs, reason = updater.needs_update(symbol, timeframe)
        # First time, should need update (no metadata)
        assert needs is True

    def test_multi_symbol_cache(self, data_cache):
        """Test caching multiple symbols."""
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 3)

        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

        for symbol in symbols:
            data = create_sample_ohlcv(
                symbol=symbol,
                start_date=start_time,
                end_date=end_time,
                freq="1h",
            )
            data_cache.set(symbol, timeframe, start_time, end_time, data)

        # All symbols should be retrievable
        for symbol in symbols:
            cached = data_cache.get(symbol, timeframe, start_time, end_time)
            assert cached is not None

    def test_monitor_alerts_after_operations(self, data_cache, monitor, checker):
        """Test that monitor generates alerts based on operations."""
        symbol = "BTC-USDT"
        timeframe = "1h"
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 7)

        # Create data with issues
        data = create_sample_ohlcv(
            symbol=symbol,
            start_date=start_time,
            end_date=end_time,
            freq="1h",
        )
        # Add some issues
        data.iloc[10] = np.nan

        # Cache and retrieve
        data_cache.set(symbol, timeframe, start_time, end_time, data)
        cached = data_cache.get(symbol, timeframe, start_time, end_time)

        # Check quality
        quality = checker.check(cached, symbol)

        # Monitor should still work
        report = monitor.get_report()
        assert isinstance(report, str)

        # Check alerts
        alerts = monitor.check_health()
        assert isinstance(alerts, list)
