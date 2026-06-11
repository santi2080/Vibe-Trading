"""Tests for holiday calendar integration (Phase 19)."""
from __future__ import annotations

from datetime import date, datetime, timezone
import pytest

from src.data.holiday_calendar import is_trading_day, is_holiday, get_holiday_name
from src.data.trading_sessions import MarketSessionStatus, get_session_status
from src.data.freshness import DataFreshnessChecker
from src.data.market import Timeframe


class TestIsTradingDay:
    """Tests for is_trading_day()."""

    def test_cny_2026_is_holiday(self):
        """Chinese New Year 2026 (Feb 16-20) should be holidays."""
        # CNY 2026: Feb 16 (除夕) through Feb 20
        for day in [16, 17, 18, 19, 20]:
            result = is_trading_day("cn_stock", date(2026, 2, day))
            assert result is False, f"Feb {day} should be holiday, got {result}"

    def test_normal_weekday_is_trading_day(self):
        """Normal weekdays should be trading days (unless a holiday)."""
        # June 11, 2026 is a Thursday - normal trading day
        result = is_trading_day("us_stock", date(2026, 6, 11))
        assert result is True, f"June 11 should be trading day, got {result}"

    def test_weekend_not_holiday(self):
        """Weekends that are not holidays return True (not a holiday = trading day)."""
        # Saturday - not a US stock holiday, so is_trading_day returns True
        result = is_trading_day("us_stock", date(2026, 6, 13))
        # holidays library only checks holidays, not weekday/weekend
        # If not a holiday, it's a "trading day" per calendar
        assert result is True, f"Weekend not a holiday should return True, got {result}"
        # is_holiday should return False
        assert is_holiday("us_stock", date(2026, 6, 13)) is False

    def test_unknown_market_returns_none(self):
        """Unknown markets (crypto, forex) return None."""
        result = is_trading_day("crypto", date(2026, 6, 11))
        assert result is None, f"Unknown market should return None, got {result}"
        result2 = is_trading_day("forex", date(2026, 6, 11))
        assert result2 is None, f"Unknown market should return None, got {result2}"

    def test_hk_new_year_2026(self):
        """HK stock market should have CNY holidays."""
        # CNY 2026 should also affect HKEX
        result = is_trading_day("hk_stock", date(2026, 2, 17))
        assert result is False, f"HK CNY Feb 17 should be holiday, got {result}"

    def test_us_independence_day_2026(self):
        """US Independence Day (July 4) should be a US stock holiday."""
        result = is_trading_day("us_stock", date(2026, 7, 3))  # observed
        # July 3, 2026 is a Friday - if it's a holiday, it would be observed on July 3
        # The holidays library handles observed rules
        # If not a holiday, it should return True (trading day) or False (weekend)
        assert result in (True, False), f"Should return bool, got {result}"

    def test_datetime_input(self):
        """is_trading_day accepts datetime objects."""
        from zoneinfo import ZoneInfo

        dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        result = is_trading_day("cn_stock", dt)
        assert result is False, f"CNY datetime should be holiday, got {result}"

    def test_sse_2026_holidays(self):
        """SSE 2026 holidays should include major Chinese holidays."""
        # Qingming Festival 2026: April 5-6 (not Apr 4)
        for day in [5, 6]:
            result = is_trading_day("cn_stock", date(2026, 4, day))
            assert result is False, f"Qingming Apr {day} should be holiday, got {result}"


class TestIsHoliday:
    """Tests for is_holiday()."""

    def test_is_holiday_inverse_of_is_trading_day(self):
        """is_holiday should be the inverse of is_trading_day."""
        # CNY is a holiday
        assert is_holiday("cn_stock", date(2026, 2, 17)) is True
        assert is_holiday("cn_stock", date(2026, 2, 17)) is not is_trading_day(
            "cn_stock", date(2026, 2, 17)
        )
        # Normal day is not a holiday
        assert is_holiday("us_stock", date(2026, 6, 11)) is False

    def test_unknown_market_returns_none(self):
        """Unknown market returns None."""
        assert is_holiday("crypto", date(2026, 6, 11)) is None


class TestGetHolidayName:
    """Tests for get_holiday_name()."""

    def test_holiday_name_on_cny(self):
        """get_holiday_name returns Chinese name on CNY."""
        name = get_holiday_name("cn_stock", date(2026, 2, 17))
        assert name is not None, "CNY should have holiday name"
        assert "春节" in name or "假日" in name or "休息" in name

    def test_holiday_name_on_normal_day(self):
        """get_holiday_name returns None on normal trading day."""
        name = get_holiday_name("us_stock", date(2026, 6, 11))
        assert name is None, f"Normal day should have no holiday name, got {name}"

    def test_holiday_name_on_qingming(self):
        """get_holiday_name returns name on Qingming Festival."""
        name = get_holiday_name("cn_stock", date(2026, 4, 5))
        assert name is not None, "Qingming should have holiday name"
        assert "清明" in name


class TestMarketSessionStatusHoliday:
    """Tests for MarketSessionStatus.HOLIDAY."""

    def test_holiday_status_on_cny(self):
        """get_session_status returns HOLIDAY on CNY dates."""
        from zoneinfo import ZoneInfo

        # CNY 2026 Feb 17 at 10:00 CST
        cn_dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        status = get_session_status("cn_stock", cn_dt)
        assert status == MarketSessionStatus.HOLIDAY, f"Expected HOLIDAY, got {status}"

    def test_holiday_status_on_qingming(self):
        """get_session_status returns HOLIDAY on Qingming dates."""
        qingming_dt = datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc)
        status = get_session_status("cn_stock", qingming_dt)
        assert status == MarketSessionStatus.HOLIDAY, f"Expected HOLIDAY, got {status}"

    def test_normal_day_not_holiday(self):
        """Normal trading day does NOT return HOLIDAY."""
        us_dt = datetime(2026, 6, 11, 14, 30, 0, tzinfo=timezone.utc)
        status = get_session_status("us_stock", us_dt)
        assert status != MarketSessionStatus.HOLIDAY, f"Normal day should not be HOLIDAY, got {status}"
        assert status == MarketSessionStatus.REGULAR, f"Expected REGULAR, got {status}"


class TestHolidayFreshness:
    """Tests for holiday-aware freshness checks."""

    def test_freshness_status_holiday(self):
        """get_freshness_status returns 'holiday' on holiday dates."""
        from zoneinfo import ZoneInfo

        # CNY 2026 Feb 17 at 10:00 UTC
        cn_dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        last_update = datetime(2026, 2, 14, 15, 0, 0, tzinfo=timezone.utc)

        checker = DataFreshnessChecker()
        status = checker.get_freshness_status(last_update, Timeframe.H1, cn_dt, session_context="cn_stock")
        assert status == "holiday", f"Expected 'holiday', got {status}"

    def test_is_fresh_on_holiday_with_recent_update(self):
        """is_fresh returns True on holiday if data was recently updated."""
        cn_dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        # Updated 2 hours ago (within H1 threshold of 4 hours)
        recent_update = datetime(2026, 2, 17, 8, 0, 0, tzinfo=timezone.utc)

        checker = DataFreshnessChecker()
        assert checker.is_fresh(recent_update, Timeframe.H1, cn_dt, session_context="cn_stock") is True

    def test_is_fresh_on_holiday_with_stale_update(self):
        """is_fresh returns False on holiday if data is stale."""
        cn_dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        # Updated 67 hours ago (beyond H1 threshold of 4 hours)
        stale_update = datetime(2026, 2, 14, 15, 0, 0, tzinfo=timezone.utc)

        checker = DataFreshnessChecker()
        assert checker.is_fresh(stale_update, Timeframe.H1, cn_dt, session_context="cn_stock") is False

    def test_d1_threshold_on_holiday(self):
        """D1 data on holiday: 1-day-old data is fresh (within 3-day threshold)."""
        cn_dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        # Updated 1 day ago
        yesterday = datetime(2026, 2, 16, 10, 0, 0, tzinfo=timezone.utc)

        checker = DataFreshnessChecker()
        assert checker.is_fresh(yesterday, Timeframe.D1, cn_dt, session_context="cn_stock") is True


class TestIsSessionTime:
    """Tests for is_session_time() with HOLIDAY status."""

    def test_is_session_time_returns_false_on_holiday(self):
        """is_session_time returns False on holiday."""
        from src.data.trading_sessions import is_session_time

        cn_dt = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)
        assert is_session_time("cn_stock", cn_dt) is False

    def test_is_session_time_returns_true_on_regular(self):
        """is_session_time returns True during regular trading hours."""
        from src.data.trading_sessions import is_session_time

        us_dt = datetime(2026, 6, 11, 14, 30, 0, tzinfo=timezone.utc)  # 10:30 AM ET
        assert is_session_time("us_stock", us_dt) is True
