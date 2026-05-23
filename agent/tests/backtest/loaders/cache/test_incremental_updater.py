"""Tests for incremental updater."""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backtest.loaders.cache.incremental_updater import (
    IncrementalUpdater,
    UpdateMetadata,
)


class MockLoader:
    """Mock data loader for testing."""

    name = "mock"

    def __init__(self, data_generator=None):
        self.fetch_count = 0
        self.data_generator = data_generator or self._default_generator

    def _default_generator(self, codes, start, end, **kwargs):
        # Use default dates if None
        if start is None:
            start = "2024-01-01"
        if end is None:
            end = "2024-12-31"
        dates = pd.date_range(start, end, freq="D")
        return {
            code: pd.DataFrame({
                "open": [100 + i * 0.5 for i in range(len(dates))],
                "high": [101 + i * 0.5 for i in range(len(dates))],
                "low": [99 + i * 0.5 for i in range(len(dates))],
                "close": [100.5 + i * 0.5 for i in range(len(dates))],
                "volume": [1000000 for _ in range(len(dates))],
            }, index=dates)
            for code in codes
        }

    def fetch(self, codes, start=None, end=None, **kwargs):
        self.fetch_count += 1
        return self.data_generator(codes, start, end, **kwargs)


class TestUpdateMetadata:
    """Tests for UpdateMetadata dataclass."""

    def test_to_dict(self):
        """Test metadata serialization."""
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime(2024, 1, 1, 12, 0, 0),
            start_date="2020-01-01",
            end_date="2024-01-01",
            row_count=1000,
        )

        data = metadata.to_dict()

        assert data["symbol"] == "AAPL.US"
        assert data["timeframe"] == "1D"
        assert "2024-01-01" in data["last_update"]
        assert data["start_date"] == "2020-01-01"
        assert data["end_date"] == "2024-01-01"
        assert data["row_count"] == 1000

    def test_from_dict(self):
        """Test metadata deserialization."""
        data = {
            "symbol": "AAPL.US",
            "timeframe": "1D",
            "last_update": "2024-01-01T12:00:00",
            "start_date": "2020-01-01",
            "end_date": "2024-01-01",
            "row_count": 1000,
        }

        metadata = UpdateMetadata.from_dict(data)

        assert metadata.symbol == "AAPL.US"
        assert metadata.timeframe == "1D"
        assert metadata.start_date == "2020-01-01"
        assert metadata.end_date == "2024-01-01"
        assert metadata.row_count == 1000


class TestIncrementalUpdater:
    """Tests for IncrementalUpdater."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def updater(self, temp_dir):
        """Create updater with temp directory."""
        return IncrementalUpdater(
            metadata_dir=temp_dir,
            max_gap_days=30,
            check_frequency_hours=1,
        )

    def test_first_update_full_fetch(self, updater):
        """Test first update triggers full fetch."""
        loader = MockLoader()
        cached_df = None

        result, is_incremental = updater.update(
            cached_df, loader, "AAPL.US", "1D"
        )

        assert is_incremental is False
        assert not result.empty
        assert loader.fetch_count == 1

    def test_second_update_incremental(self, updater, temp_dir):
        """Test second update is incremental."""
        # Create initial data
        dates1 = pd.date_range("2024-01-01", "2024-06-30", freq="D")
        initial_df = pd.DataFrame({
            "open": [100 + i * 0.1 for i in range(len(dates1))],
            "high": [101 + i * 0.1 for i in range(len(dates1))],
            "low": [99 + i * 0.1 for i in range(len(dates1))],
            "close": [100.5 + i * 0.1 for i in range(len(dates1))],
            "volume": [1000000 for _ in range(len(dates1))],
        }, index=dates1)

        # Save metadata to simulate previous update
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now() - timedelta(hours=2),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=len(initial_df),
            source="mock",
        )
        updater.save_metadata(metadata)

        # Create mock that returns only new data
        def new_data_generator(codes, start, end, **kwargs):
            dates2 = pd.date_range(start, end, freq="D")
            return {
                code: pd.DataFrame({
                    "open": [105 + i * 0.1 for i in range(len(dates2))],
                    "high": [106 + i * 0.1 for i in range(len(dates2))],
                    "low": [104 + i * 0.1 for i in range(len(dates2))],
                    "close": [105.5 + i * 0.1 for i in range(len(dates2))],
                    "volume": [1000000 for _ in range(len(dates2))],
                }, index=dates2)
                for code in codes
            }

        loader = MockLoader(data_generator=new_data_generator)

        # Second update
        result, is_incremental = updater.update(
            initial_df, loader, "AAPL.US", "1D"
        )

        assert is_incremental is True
        assert len(result) >= len(initial_df)
        assert loader.fetch_count == 1

    def test_force_update(self, updater, temp_dir):
        """Test force update ignores cache."""
        # Create metadata
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        loader = MockLoader()

        # Force update should always fetch
        result, is_incremental = updater.update(
            pd.DataFrame(), loader, "AAPL.US", "1D", force=True
        )

        assert loader.fetch_count >= 1

    def test_large_gap_triggers_full_update(self, updater, temp_dir):
        """Test large gap triggers full update instead of incremental."""
        # Create metadata with large gap
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now() - timedelta(days=60),
            start_date="2023-01-01",
            end_date="2023-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        # Initial data
        dates = pd.date_range("2023-01-01", "2023-06-30", freq="D")
        cached_df = pd.DataFrame({
            "open": [100 for _ in range(len(dates))],
            "high": [101 for _ in range(len(dates))],
            "low": [99 for _ in range(len(dates))],
            "close": [100 for _ in range(len(dates))],
            "volume": [1000 for _ in range(len(dates))],
        }, index=dates)

        loader = MockLoader()

        # Update should fetch from original start date
        result, is_incremental = updater.update(
            cached_df, loader, "AAPL.US", "1D"
        )

        # Should have fetched new data
        assert not result.empty

    def test_needs_update_checks_frequency(self, updater, temp_dir):
        """Test needs_update respects check frequency."""
        # Recent metadata
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now() - timedelta(minutes=30),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        needs, reason = updater.needs_update("AAPL.US", "1D")

        assert needs is False
        assert "recent_update" in reason

    def test_needs_update_stale_data(self, updater, temp_dir):
        """Test needs_update detects stale data."""
        # Old metadata
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now() - timedelta(hours=2),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        needs, reason = updater.needs_update("AAPL.US", "1D")

        assert needs is True

    def test_clear_metadata(self, updater, temp_dir):
        """Test clearing metadata."""
        # Create metadata
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        # Verify it exists
        assert updater.get_metadata("AAPL.US", "1D") is not None

        # Clear it
        updater.clear_metadata("AAPL.US", "1D")

        # Verify it's gone
        assert updater.get_metadata("AAPL.US", "1D") is None

    def test_get_stats(self, updater, temp_dir):
        """Test getting statistics."""
        # Add some metadata
        metadata = UpdateMetadata(
            symbol="AAPL.US",
            timeframe="1D",
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        stats = updater.get_stats()

        assert stats["metadata_count"] == 1
        assert stats["max_gap_days"] == 30
        assert stats["check_frequency_hours"] == 1

    def test_update_with_empty_cached_df(self, updater):
        """Test update with empty cached DataFrame."""
        loader = MockLoader()

        result, is_incremental = updater.update(
            pd.DataFrame(), loader, "AAPL.US", "1D"
        )

        assert not result.empty
        assert is_incremental is False
        assert loader.fetch_count == 1

    def test_special_characters_in_symbol(self, updater, temp_dir):
        """Test handling special characters in symbol."""
        metadata = UpdateMetadata(
            symbol="BTC/USDT",
            timeframe="1D",
            last_update=datetime.now(),
            start_date="2024-01-01",
            end_date="2024-06-30",
            row_count=100,
            source="mock",
        )
        updater.save_metadata(metadata)

        # Should load without error
        loaded = updater.get_metadata("BTC/USDT", "1D")
        assert loaded is not None
        assert loaded.symbol == "BTC/USDT"


class TestIncrementalUpdaterIntegration:
    """Integration tests for incremental updater."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_realistic_update_workflow(self, temp_dir):
        """Test realistic update workflow."""
        updater = IncrementalUpdater(
            metadata_dir=temp_dir,
            max_gap_days=30,
            check_frequency_hours=1,
        )

        # Simulate data generator
        def data_gen(codes, start, end, **kwargs):
            if start is None:
                start = "2024-01-01"
            if end is None:
                end = "2024-12-31"
            dates = pd.date_range(start, end, freq="D")
            return {
                code: pd.DataFrame({
                    "open": [100 + i for i in range(len(dates))],
                    "high": [101 + i for i in range(len(dates))],
                    "low": [99 + i for i in range(len(dates))],
                    "close": [100 + i for i in range(len(dates))],
                    "volume": [1000 for _ in range(len(dates))],
                }, index=dates)
                for code in codes
            }

        loader = MockLoader(data_generator=data_gen)

        # First update: full fetch
        df1, is_inc1 = updater.update(None, loader, "TEST.US", "1D")
        assert not is_inc1
        assert len(df1) > 0
        initial_rows = len(df1)

        # Second update (after 2 hours): should be incremental
        # Manually set metadata to simulate time passage
        metadata = updater.get_metadata("TEST.US", "1D")
        metadata.last_update = datetime.now() - timedelta(hours=2)
        updater.save_metadata(metadata)

        df2, is_inc2 = updater.update(df1, loader, "TEST.US", "1D")
        assert is_inc2
        # Should have same or more rows
        assert len(df2) >= initial_rows

    def test_no_data_returns_empty(self, temp_dir):
        """Test handling of no data."""
        updater = IncrementalUpdater(metadata_dir=temp_dir)

        def empty_gen(codes, start, end, **kwargs):
            # Use default dates if None
            if start is None:
                start = "2024-01-01"
            if end is None:
                end = "2024-12-31"
            return {code: pd.DataFrame() for code in codes}

        loader = MockLoader(data_generator=empty_gen)

        result, is_incremental = updater.update(None, loader, "EMPTY.US", "1D")

        assert result.empty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
