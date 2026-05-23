"""Tests for trading sessions.

Run with: pytest agent/tests/backtest/strategies/test_sessions.py -v
"""

import pytest
from datetime import datetime, time

import pandas as pd

from agent.backtest.strategies.sessions import (
    ChinaFuturesSessions,
    USFuturesSessions,
    CryptoSessions,
    SessionManager,
    TradingSessionType,
)


class TestChinaFuturesSessions:
    """Tests for China futures trading sessions."""

    def test_is_trading_time_day_session(self):
        """Test day session trading hours."""
        from datetime import timezone
        from zoneinfo import ZoneInfo

        # Beijing time (UTC+8)
        beijing = ZoneInfo("Asia/Shanghai")

        # Test day session times
        day_time = datetime(2024, 1, 15, 9, 30, tzinfo=beijing)
        assert ChinaFuturesSessions.is_trading_time(day_time) is True

        # Test lunch break (should not be trading)
        lunch_time = datetime(2024, 1, 15, 11, 45, tzinfo=beijing)
        assert ChinaFuturesSessions.is_trading_time(lunch_time) is False

        # Test after market close
        close_time = datetime(2024, 1, 15, 15, 30, tzinfo=beijing)
        assert ChinaFuturesSessions.is_trading_time(close_time) is False

    def test_is_trading_time_night_session(self):
        """Test night session trading hours."""
        from zoneinfo import ZoneInfo

        beijing = ZoneInfo("Asia/Shanghai")

        # Test night session times
        night_time = datetime(2024, 1, 15, 21, 30, tzinfo=beijing)
        assert ChinaFuturesSessions.is_trading_time(night_time) is True

    def test_session_type(self):
        """Test session type detection."""
        from zoneinfo import ZoneInfo

        beijing = ZoneInfo("Asia/Shanghai")

        # Day session
        day_time = datetime(2024, 1, 15, 10, 0, tzinfo=beijing)
        assert ChinaFuturesSessions.get_session_type(day_time) == TradingSessionType.DAY

        # Night session
        night_time = datetime(2024, 1, 15, 22, 0, tzinfo=beijing)
        assert ChinaFuturesSessions.get_session_type(night_time) == TradingSessionType.NIGHT


class TestSessionManager:
    """Tests for unified session manager."""

    def test_get_session(self):
        """Test getting session for market."""
        china_session = SessionManager.get_session("china_futures")
        assert china_session == ChinaFuturesSessions

        crypto_session = SessionManager.get_session("crypto")
        assert crypto_session == CryptoSessions

    def test_filter_by_session_crypto(self):
        """Test crypto has no filtering."""
        dates = pd.date_range("2024-01-01", periods=10, freq="1h")
        df = pd.DataFrame({"close": range(10)}, index=dates)

        result = SessionManager.filter_by_session(df, "crypto")
        assert len(result) == 10  # No filtering for crypto


class TestCryptoSessions:
    """Tests for crypto sessions."""

    def test_is_always_trading(self):
        """Test crypto trades 24/7."""
        from zoneinfo import ZoneInfo

        utc = ZoneInfo("UTC")

        # Any time should be trading
        times = [
            datetime(2024, 1, 1, 0, 0, tzinfo=utc),
            datetime(2024, 1, 1, 12, 0, tzinfo=utc),
            datetime(2024, 1, 1, 23, 59, tzinfo=utc),
        ]

        for t in times:
            assert CryptoSessions.is_trading_time(t) is True
