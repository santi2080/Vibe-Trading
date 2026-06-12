"""Tests for session-aware freshness detection (CAL-03).

Covers:
- 20-01: stale_after_for() session-adjusted thresholds
- 20-02: _updated_on_date() helper
- 20-03: get_session_aware_report() and FreshnessReport dataclass
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.data.freshness import (
    DataFreshnessChecker,
    FreshnessReport,
    get_session_aware_report,
)
from src.data.market import Timeframe


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv_df(index_dates):
    return pd.DataFrame(
        {"open": [190.0] * len(index_dates),
         "high": [195.0] * len(index_dates),
         "low": [188.0] * len(index_dates),
         "close": [193.0] * len(index_dates),
         "volume": [1_000_000] * len(index_dates)},
        index=pd.to_datetime(index_dates),
    )


# ---------------------------------------------------------------------------
# 20-01: stale_after_for session adjustment
# ---------------------------------------------------------------------------

class TestStaleAfterForSessionAdjustment:
    """stale_after_for() returns session-adjusted thresholds."""

    def test_continuous_market_unchanged_threshold(self):
        """US futures (continuous) always returns base threshold regardless of time."""
        from src.data.data_refresh import stale_after_for

        # Any time, continuous market → base threshold
        utc_any = datetime(2026, 6, 12, 3, 0, tzinfo=timezone.utc)
        assert stale_after_for("us_futures", "1d", utc_now=utc_any) == timedelta(days=2)

        utc_late = datetime(2026, 6, 12, 23, 0, tzinfo=timezone.utc)
        assert stale_after_for("us_futures", "1d", utc_now=utc_late) == timedelta(days=2)

    def test_ushare_postmarket_no_today_data_extends_threshold(self):
        """US equity after close with no today's data → 1.5x threshold."""
        from src.data.data_refresh import stale_after_for

        # US equity POST_MARKET (16:00-20:00 EST) → no update today expected → 1.5x
        utc_post = datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc)  # 16:00 EST
        threshold = stale_after_for("us_stock", "1d", utc_now=utc_post)
        assert threshold == timedelta(days=3), f"Expected 3 days (1.5x), got {threshold}"

    def test_ushare_regular_hours_base_threshold(self):
        """US equity during REGULAR hours → base threshold."""
        from src.data.data_refresh import stale_after_for

        utc_reg = datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc)  # 09:30 EST
        threshold = stale_after_for("us_stock", "1d", utc_now=utc_reg)
        assert threshold == timedelta(days=2), f"Expected 2 days (base), got {threshold}"

    def test_ushare_holiday_extends_threshold(self):
        """US equity on a holiday → 2x threshold."""
        from src.data.data_refresh import stale_after_for

        utc_hol = datetime(2026, 12, 25, 14, 0, tzinfo=timezone.utc)  # Dec 25
        threshold = stale_after_for("us_stock", "1d", utc_now=utc_hol)
        assert threshold == timedelta(days=4), f"Expected 4 days (2x holiday), got {threshold}"

    def test_ashare_postmarket_no_today_data_extends_threshold(self):
        """A-share after close with no today's data → 1.5x threshold."""
        from src.data.data_refresh import stale_after_for

        # A-share after market close (POST_MARKET 15:00-16:00 Shanghai)
        utc_closed = datetime(2026, 6, 12, 7, 0, tzinfo=timezone.utc)  # 15:00 CST
        threshold = stale_after_for("cn_stock", "1d", utc_now=utc_closed)
        assert threshold == timedelta(days=3), f"Expected 3 days (1.5x), got {threshold}"

    def test_ashare_regular_hours_base_threshold(self):
        """A-share during REGULAR hours → base threshold."""
        from src.data.data_refresh import stale_after_for

        utc_reg = datetime(2026, 6, 12, 2, 30, tzinfo=timezone.utc)  # 10:30 CST
        threshold = stale_after_for("cn_stock", "1d", utc_now=utc_reg)
        assert threshold == timedelta(days=2), f"Expected 2 days (base), got {threshold}"

    def test_unknown_market_base_threshold(self):
        """Unknown market code → base threshold (no session info)."""
        from src.data.data_refresh import stale_after_for

        utc_any = datetime(2026, 6, 12, 14, 0, tzinfo=timezone.utc)
        threshold = stale_after_for("unknown_market", "1d", utc_now=utc_any)
        assert threshold == timedelta(days=2)

    def test_hk_stock_postmarket_extends_threshold(self):
        """HK stock after close → 1.5x threshold."""
        from src.data.data_refresh import stale_after_for

        utc_closed = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)  # 17:00 HKT
        threshold = stale_after_for("hk_stock", "1d", utc_now=utc_closed)
        assert threshold == timedelta(days=3), f"Expected 3 days (1.5x), got {threshold}"


# ---------------------------------------------------------------------------
# 20-02: _updated_on_date helper
# ---------------------------------------------------------------------------

class TestUpdatedOnDate:
    """_updated_on_date() checks parquet last-update date in market timezone."""

    def test_returns_false_for_missing_file(self):
        """When no parquet exists, _updated_on_date returns False."""
        from src.data.data_refresh import _updated_on_date

        result = _updated_on_date("cn_stock", "1d", date(2026, 6, 12), data_dir=Path("/tmp/nonexistent"))
        assert result is False

    def test_returns_false_for_unknown_market(self):
        """Unknown market → False (no timezone mapping)."""
        from src.data.data_refresh import _updated_on_date

        result = _updated_on_date("unknown", "1d", date(2026, 6, 12))
        assert result is False

    def test_returns_true_when_parquet_updated_today(self, tmp_path):
        """When parquet was last updated today (market timezone), returns True."""
        from src.data.data_refresh import _updated_on_date

        market_dir = tmp_path / "cn_stocks" / "600519.SH"
        market_dir.mkdir(parents=True)

        # Parquet updated today (June 12 in Shanghai = June 12 UTC)
        df = _make_ohlcv_df([datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc)])
        df.to_parquet(market_dir / "1d.parquet", index=True)

        result = _updated_on_date("cn_stock", "1d", date(2026, 6, 12), data_dir=tmp_path)
        assert result is True

    def test_returns_false_when_parquet_updated_yesterday(self, tmp_path):
        """When parquet was last updated yesterday, returns False for today."""
        from src.data.data_refresh import _updated_on_date

        market_dir = tmp_path / "cn_stocks" / "600519.SH"
        market_dir.mkdir(parents=True)

        # Parquet updated yesterday
        df = _make_ohlcv_df([datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)])
        df.to_parquet(market_dir / "1d.parquet", index=True)

        result = _updated_on_date("cn_stock", "1d", date(2026, 6, 12), data_dir=tmp_path)
        assert result is False


# ---------------------------------------------------------------------------
# 20-03: FreshnessReport and get_session_aware_report
# ---------------------------------------------------------------------------

class TestFreshnessReportDataclass:
    """FreshnessReport dataclass has correct fields and to_dict()."""

    def test_freshness_report_fields(self):
        """FreshnessReport has all required fields."""
        report = FreshnessReport(
            status="fresh",
            age_hours=2.0,
            session_status="regular",
            threshold_hours=24.0,
            freshness_reason="Data is fresh",
            last_update=datetime.now(timezone.utc),
            check_time=datetime.now(timezone.utc),
        )
        assert report.status == "fresh"
        assert report.age_hours == 2.0
        assert report.session_status == "regular"

    def test_freshness_report_to_dict(self):
        """FreshnessReport.to_dict() returns JSON-serializable dict."""
        now = datetime.now(timezone.utc)
        report = FreshnessReport(
            status="fresh",
            age_hours=2.0,
            session_status="regular",
            threshold_hours=24.0,
            freshness_reason="Data is fresh",
            last_update=now,
            check_time=now,
        )
        d = report.to_dict()
        assert d["status"] == "fresh"
        assert d["age_hours"] == 2.0
        assert d["session_status"] == "regular"
        assert "freshness_reason" in d
        assert "last_update" in d
        assert "check_time" in d


class TestGetSessionAwareReport:
    """get_session_aware_report() returns correct status for all session types."""

    def test_regular_hours_fresh(self):
        """US equity during REGULAR hours with recent data → status=fresh."""
        utc_reg = datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc)  # 09:30 EST
        # Data from 1 hour ago
        last = datetime(2026, 6, 12, 13, 30, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "us_stock", utc_reg)
        assert report.status == "fresh"
        assert report.session_status == "regular"

    def test_regular_hours_stale(self):
        """US equity during REGULAR hours with old data → status=stale."""
        utc_reg = datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc)
        # H4 threshold = 24h, 24h*2=48h
        # Data from 30 hours ago → stale (30h > 24h but < 48h)
        last = datetime(2026, 6, 11, 8, 30, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "us_stock", utc_reg)
        assert report.status == "stale"

    def test_regular_hours_very_stale(self):
        """US equity during REGULAR hours with very old data → status=very_stale."""
        utc_reg = datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc)
        # H4 threshold = 24h, 24h*2=48h
        # Data from 60 hours ago → very_stale (60h >= 48h)
        last = datetime(2026, 6, 10, 2, 30, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "us_stock", utc_reg)
        assert report.status == "very_stale"

    def test_postmarket_fresh_within_lenient_threshold(self):
        """A-share POST_MARKET with data within lenient 1.5x threshold → status=fresh."""
        utc_closed = datetime(2026, 6, 12, 7, 0, tzinfo=timezone.utc)  # 15:00 CST
        last = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)  # 21 hours ago

        report = get_session_aware_report(last, Timeframe.H4, "cn_stock", utc_closed)
        # H4 base=24h, POST_MARKET→1.5x=36h; data age=21h < 36h → fresh
        assert report.status == "fresh", f"Expected fresh (21h < 36h lenient), got {report.status}"
        assert report.session_status == "post_market"
        assert report.threshold_hours == 36.0

    def test_postmarket_stale_beyond_lenient_threshold(self):
        """A-share POST_MARKET with data beyond lenient 1.5x threshold → status=stale."""
        utc_closed = datetime(2026, 6, 12, 7, 0, tzinfo=timezone.utc)  # 15:00 CST
        # 48 hours ago: 48h >= 36h (lenient) but < 72h (very_stale) → stale
        last = datetime(2026, 6, 10, 7, 0, tzinfo=timezone.utc)

        report = get_session_aware_report(last, Timeframe.H4, "cn_stock", utc_closed)
        assert report.status == "stale", f"Expected stale (48h >= 36h lenient), got {report.status}"
        assert report.session_status == "post_market"

    def test_holiday_status(self):
        """US equity on holiday → status=holiday."""
        utc_hol = datetime(2026, 12, 25, 14, 0, tzinfo=timezone.utc)
        last = datetime(2026, 12, 24, 10, 0, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "us_stock", utc_hol)
        assert report.status == "holiday"
        assert report.session_status == "holiday"
        assert "holiday" in report.freshness_reason.lower()

    def test_continuous_ignores_session(self):
        """US futures (continuous) → status based on raw threshold, not session."""
        utc_any = datetime(2026, 6, 12, 3, 0, tzinfo=timezone.utc)
        # Very fresh data
        last = datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "us_futures", utc_any)
        assert report.status == "fresh"
        assert report.session_status == "continuous"
        # Continuous has no session adjustment
        assert report.threshold_hours == 4.0

    def test_premarket_fresh(self):
        """US equity pre-market with fresh data → status=fresh."""
        # Pre-market: 04:00-09:30 EST
        utc_pre = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)  # 07:00 EST
        last = datetime(2026, 6, 12, 11, 0, tzinfo=timezone.utc)  # 06:00 EST
        report = get_session_aware_report(last, Timeframe.H4, "us_stock", utc_pre)
        assert report.status == "fresh"
        assert report.session_status == "pre_market"

    def test_report_has_all_fields(self):
        """get_session_aware_report returns a report with all required fields."""
        utc_now = datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc)
        last = datetime(2026, 6, 12, 13, 30, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "us_stock", utc_now)

        assert hasattr(report, "status")
        assert hasattr(report, "age_hours")
        assert hasattr(report, "session_status")
        assert hasattr(report, "threshold_hours")
        assert hasattr(report, "freshness_reason")
        assert hasattr(report, "last_update")
        assert hasattr(report, "check_time")

        # Values are not None
        assert report.status is not None
        assert report.session_status is not None
        assert report.freshness_reason is not None

    def test_unknown_market_continuous(self):
        """Unknown market code → continuous (no session info available)."""
        utc_any = datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc)
        last = datetime(2026, 6, 12, 13, 30, tzinfo=timezone.utc)
        report = get_session_aware_report(last, Timeframe.H4, "unknown_market", utc_any)
        # Unknown → treated as continuous → threshold unchanged
        assert report.session_status == "continuous"
        assert report.threshold_hours == 4.0


# ---------------------------------------------------------------------------
# Integration: stale_after_for uses _updated_on_date result
# ---------------------------------------------------------------------------

class TestStaleAfterForWithTodayData:
    """When parquet was updated today, stale_after_for returns base threshold."""

    def test_ashare_closed_with_today_data_base_threshold(self, tmp_path):
        """A-share closed + parquet updated today → base threshold (not 1.5x)."""
        from src.data.data_refresh import stale_after_for

        # Create a parquet updated today
        market_dir = tmp_path / "cn_stocks" / "600519.SH"
        market_dir.mkdir(parents=True)
        df = _make_ohlcv_df([datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc)])
        df.to_parquet(market_dir / "1d.parquet", index=True)

        # Market closed at 15:00 CST, parquet updated at 10:00 CST today
        utc_closed = datetime(2026, 6, 12, 7, 0, tzinfo=timezone.utc)  # 15:00 CST
        threshold = stale_after_for("cn_stock", "1d", utc_now=utc_closed)

        # With today's data → base threshold (not 1.5x)
        assert threshold == timedelta(days=2), f"Expected base 2 days, got {threshold}"

    def test_ushare_closed_with_today_data_base_threshold(self, tmp_path):
        """US equity closed + parquet updated today → base threshold."""
        from src.data.data_refresh import stale_after_for

        market_dir = tmp_path / "us_stocks" / "AAPL"
        market_dir.mkdir(parents=True)
        df = _make_ohlcv_df([datetime(2026, 6, 12, 18, 0, tzinfo=timezone.utc)])  # 14:00 EST
        df.to_parquet(market_dir / "1d.parquet", index=True)

        # Market closed at 16:00 EST, parquet updated at 14:00 EST today
        utc_closed = datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc)  # 16:00 EST
        threshold = stale_after_for("us_stock", "1d", utc_now=utc_closed)

        assert threshold == timedelta(days=2), f"Expected base 2 days, got {threshold}"
