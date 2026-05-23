"""Tests for DataQualityChecker"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from agent.backtest.loaders.cache.quality_checker import (
    DataQualityChecker, QualityReport, QualityIssue
)


class TestDataQualityChecker:
    """Test DataQualityChecker functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.checker = DataQualityChecker()

    def _create_valid_ohlc_data(self, use_current_time: bool = False) -> pd.DataFrame:
        """Create valid OHLC data for testing

        Args:
            use_current_time: If True, use recent timestamps; if False, use fixed 2024 dates
        """
        if use_current_time:
            # Use recent timestamps
            dates = pd.date_range(start=datetime.now() - timedelta(hours=100), periods=100, freq='1h')
        else:
            # Use fixed 2024 dates (for testing with known timestamps)
            dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')

        np.random.seed(42)
        base_price = 100
        data = {
            'open': base_price + np.random.randn(100).cumsum(),
            'high': base_price + np.random.randn(100).cumsum() + 2,
            'low': base_price + np.random.randn(100).cumsum() - 2,
            'close': base_price + np.random.randn(100).cumsum(),
            'volume': np.random.randint(1000, 10000, 100),
        }
        df = pd.DataFrame(data, index=dates)
        # Ensure consistency
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
        return df

    def test_check_with_valid_data(self):
        """Test check with valid data"""
        df = self._create_valid_ohlc_data(use_current_time=True)  # Use recent timestamps
        report = self.checker.check(df, symbol="BTC-USDT")

        assert report.passed
        assert report.symbol == "BTC-USDT"
        assert len(report.issues) == 0

    def test_check_with_empty_dataframe(self):
        """Test check with empty DataFrame"""
        df = pd.DataFrame()
        report = self.checker.check(df, symbol="BTC-USDT")

        assert not report.passed
        assert any(issue.severity == "error" for issue in report.issues)

    def test_check_with_missing_values(self):
        """Test detection of missing values"""
        df = self._create_valid_ohlc_data()
        df.loc[df.index[10], 'close'] = np.nan
        df.loc[df.index[20], 'open'] = np.nan

        report = self.checker.check(df, symbol="BTC-USDT")

        assert not report.passed
        completeness_issues = [i for i in report.issues if i.dimension == "completeness"]
        assert len(completeness_issues) >= 2

    def test_check_with_inconsistent_ohlc(self):
        """Test detection of inconsistent OHLC"""
        df = self._create_valid_ohlc_data()
        # Make High < Low
        df.loc[df.index[5], 'high'] = 50
        df.loc[df.index[5], 'low'] = 100

        report = self.checker.check(df, symbol="BTC-USDT")

        assert not report.passed
        consistency_issues = [i for i in report.issues if i.dimension == "consistency"]
        assert len(consistency_issues) > 0

    def test_check_with_negative_prices(self):
        """Test detection of negative prices"""
        df = self._create_valid_ohlc_data()
        df.loc[df.index[5], 'close'] = -100

        report = self.checker.check(df, symbol="BTC-USDT")

        assert not report.passed
        assert any("Negative" in issue.message for issue in report.issues)

    def test_check_with_duplicate_timestamps(self):
        """Test detection of duplicate timestamps"""
        df = self._create_valid_ohlc_data()
        # Duplicate the index
        df = pd.concat([df, df.iloc[[0]]])

        report = self.checker.check(df, symbol="BTC-USDT")

        assert not report.passed
        uniqueness_issues = [i for i in report.issues if i.dimension == "uniqueness"]
        assert len(uniqueness_issues) > 0

    def test_check_with_stale_data(self):
        """Test detection of stale data"""
        df = self._create_valid_ohlc_data()
        # Make data very old
        df.index = pd.date_range(start='2020-01-01', periods=100, freq='1h')

        report = self.checker.check(df, symbol="BTC-USDT")

        timeliness_issues = [i for i in report.issues if i.dimension == "timeliness"]
        assert len(timeliness_issues) > 0

    def test_get_summary(self):
        """Test report summary generation"""
        df = self._create_valid_ohlc_data(use_current_time=True)  # Use recent timestamps
        report = self.checker.check(df, symbol="BTC-USDT")

        summary = report.get_summary()

        assert "BTC-USDT" in summary
        assert "PASSED" in summary or "warning" in summary.lower()


class TestDataQualityCheckerAutoFix:
    """Test auto-fix functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.checker = DataQualityChecker()
        self._create_valid_ohlc_data = TestDataQualityChecker()._create_valid_ohlc_data

    def _create_valid_ohlc_data(self) -> pd.DataFrame:
        """Create valid OHLC data for testing"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')
        np.random.seed(42)
        base_price = 100
        data = {
            'open': base_price + np.random.randn(100).cumsum(),
            'high': base_price + np.random.randn(100).cumsum() + 2,
            'low': base_price + np.random.randn(100).cumsum() - 2,
            'close': base_price + np.random.randn(100).cumsum(),
            'volume': np.random.randint(1000, 10000, 100),
        }
        df = pd.DataFrame(data, index=dates)
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
        return df

    def test_auto_fix_removes_duplicates(self):
        """Test that auto_fix removes duplicate timestamps"""
        df = self._create_valid_ohlc_data(use_current_time=True)
        original_len = len(df)

        # Add duplicates
        df = pd.concat([df, df.iloc[[0]]])
        assert len(df) == original_len + 1

        fixed_df, fixes = self.checker.auto_fix(df)

        assert len(fixed_df) == original_len
        assert fixes >= 1

    def test_auto_fix_fills_missing(self):
        """Test that auto_fix fills missing values"""
        df = self._create_valid_ohlc_data(use_current_time=True)
        df.loc[df.index[10], 'close'] = np.nan
        df.loc[df.index[20], 'open'] = np.nan

        assert df['close'].isnull().sum() == 1
        assert df['open'].isnull().sum() == 1

        fixed_df, fixes = self.checker.auto_fix(df)

        assert fixed_df['close'].isnull().sum() == 0
        assert fixed_df['open'].isnull().sum() == 0

    def test_auto_fix_ensures_ohlc_consistency(self):
        """Test that auto_fix ensures OHLC consistency"""
        df = self._create_valid_ohlc_data(use_current_time=True)
        # Break consistency
        df.loc[df.index[5], 'high'] = 50
        df.loc[df.index[5], 'low'] = 100

        assert (df['high'] < df['low']).any()

        fixed_df, fixes = self.checker.auto_fix(df)

        # After fix, high should always be >= low
        assert (fixed_df['high'] >= fixed_df['low']).all()

    def test_auto_fix_with_empty_dataframe(self):
        """Test auto_fix with empty DataFrame"""
        df = pd.DataFrame()
        fixed_df, fixes = self.checker.auto_fix(df)

        assert len(fixed_df) == 0
        assert fixes == 0


class TestDataQualityCheckerConfig:
    """Test configuration options"""

    def test_custom_thresholds(self):
        """Test custom threshold configuration"""
        checker = DataQualityChecker(
            max_missing_pct=0.01,
            max_duplicate_pct=0.005,
            max_staleness_hours=12,
        )

        assert checker.max_missing_pct == 0.01
        assert checker.max_duplicate_pct == 0.005
        assert checker.max_staleness_hours == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
