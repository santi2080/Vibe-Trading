"""Integration tests for data quality monitoring system.

These tests validate the quality checker functionality.
Note: Some tests may be skipped due to API differences.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backtest.loaders.cache.quality_checker import (
    DataQualityChecker,
    QualityIssue,
    QualityReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_ohlcv_df() -> pd.DataFrame:
    """Create a valid OHLCV DataFrame."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    np.random.seed(42)

    base_price = 100.0
    returns = np.random.randn(100) * 0.02
    prices = base_price * np.exp(np.cumsum(returns))

    return pd.DataFrame(
        {
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.randint(1000, 10000, 100),
        },
        index=pd.DatetimeIndex(dates, name="datetime"),
    )


@pytest.fixture
def quality_checker() -> DataQualityChecker:
    """Create a DataQualityChecker instance."""
    return DataQualityChecker()


# ---------------------------------------------------------------------------
# Basic Tests
# ---------------------------------------------------------------------------


class TestQualityChecker:
    """Tests for DataQualityChecker."""

    def test_checker_creation(self, quality_checker: DataQualityChecker):
        """Test that checker can be created."""
        assert quality_checker is not None

    def test_valid_data_check(
        self, quality_checker: DataQualityChecker, valid_ohlcv_df: pd.DataFrame
    ):
        """Test checking valid data."""
        report = quality_checker.check(valid_ohlcv_df, symbol="TEST")

        assert report is not None
        assert isinstance(report, QualityReport)

    def test_report_structure(
        self, quality_checker: DataQualityChecker, valid_ohlcv_df: pd.DataFrame
    ):
        """Test that report has expected structure."""
        report = quality_checker.check(valid_ohlcv_df, symbol="TEST")

        assert hasattr(report, "symbol")
        assert hasattr(report, "timestamp")
        assert hasattr(report, "passed")
        assert hasattr(report, "issues")
        assert hasattr(report, "completeness")
        assert hasattr(report, "consistency")
