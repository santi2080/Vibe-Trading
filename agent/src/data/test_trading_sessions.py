"""Tests for timezone-aware trading session status."""

from datetime import datetime, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

AGENT_DIR = Path(__file__).resolve().parents[2]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from src.data.freshness import DataFreshnessChecker
from src.data.market import Timeframe
from src.data.trading_sessions import (
    MARKET_TZ,
    MarketSessionStatus,
    get_session_status,
    is_session_time,
)


def market_time(year: int, month: int, day: int, hour: int, minute: int, tz_name: str) -> datetime:
    """Create a timezone-aware UTC datetime from local market time."""
    local_dt = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(timezone.utc)


def test_market_session_status_enum_values() -> None:
    assert MarketSessionStatus.PRE_MARKET.value == "pre_market"
    assert MarketSessionStatus.REGULAR.value == "regular"
    assert MarketSessionStatus.POST_MARKET.value == "post_market"
    assert MarketSessionStatus.CLOSED.value == "closed"
    assert MarketSessionStatus.CONTINUOUS.value == "continuous"


def test_market_tz_has_required_markets() -> None:
    assert MARKET_TZ["cn_stock"] == "Asia/Shanghai"
    assert MARKET_TZ["cn_futures"] == "Asia/Shanghai"
    assert MARKET_TZ["us_stock"] == "America/New_York"
    assert MARKET_TZ["us_futures"] == "America/Chicago"
    assert MARKET_TZ["hk_stock"] == "Asia/Hong_Kong"


def test_unknown_market_is_continuous() -> None:
    status = get_session_status("crypto", market_time(2026, 6, 11, 3, 0, "UTC"))

    assert status == MarketSessionStatus.CONTINUOUS
    assert is_session_time("crypto", market_time(2026, 6, 11, 3, 0, "UTC")) is True


def test_us_stock_session_statuses() -> None:
    tz_name = "America/New_York"

    assert get_session_status("us_stock", market_time(2026, 6, 11, 4, 0, tz_name)) == MarketSessionStatus.PRE_MARKET
    assert get_session_status("us_stock", market_time(2026, 6, 11, 9, 30, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("us_stock", market_time(2026, 6, 11, 16, 0, tz_name)) == MarketSessionStatus.POST_MARKET
    assert get_session_status("us_stock", market_time(2026, 6, 11, 20, 0, tz_name)) == MarketSessionStatus.CLOSED


def test_a_share_session_statuses() -> None:
    tz_name = "Asia/Shanghai"

    assert get_session_status("cn_stock", market_time(2026, 6, 11, 8, 30, tz_name)) == MarketSessionStatus.PRE_MARKET
    assert get_session_status("cn_stock", market_time(2026, 6, 11, 9, 30, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("cn_stock", market_time(2026, 6, 11, 11, 30, tz_name)) == MarketSessionStatus.CLOSED
    assert get_session_status("cn_stock", market_time(2026, 6, 11, 13, 0, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("cn_stock", market_time(2026, 6, 11, 15, 0, tz_name)) == MarketSessionStatus.POST_MARKET
    assert get_session_status("cn_stock", market_time(2026, 6, 11, 16, 0, tz_name)) == MarketSessionStatus.CLOSED


def test_china_futures_session_statuses() -> None:
    tz_name = "Asia/Shanghai"

    assert get_session_status("cn_futures", market_time(2026, 6, 11, 9, 0, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("cn_futures", market_time(2026, 6, 11, 10, 15, tz_name)) == MarketSessionStatus.CLOSED
    assert get_session_status("cn_futures", market_time(2026, 6, 11, 10, 30, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("cn_futures", market_time(2026, 6, 11, 13, 30, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("cn_futures", market_time(2026, 6, 11, 21, 0, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("cn_futures", market_time(2026, 6, 11, 23, 0, tz_name)) == MarketSessionStatus.CLOSED


def test_us_futures_cross_midnight_session_statuses() -> None:
    tz_name = "America/Chicago"

    assert get_session_status("us_futures", market_time(2026, 6, 11, 17, 0, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("us_futures", market_time(2026, 6, 11, 23, 59, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("us_futures", market_time(2026, 6, 12, 0, 0, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("us_futures", market_time(2026, 6, 12, 15, 59, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("us_futures", market_time(2026, 6, 12, 16, 0, tz_name)) == MarketSessionStatus.POST_MARKET
    assert get_session_status("us_futures", market_time(2026, 6, 12, 16, 59, tz_name)) == MarketSessionStatus.POST_MARKET


def test_hk_stock_session_statuses() -> None:
    tz_name = "Asia/Hong_Kong"

    assert get_session_status("hk_stock", market_time(2026, 6, 11, 9, 0, tz_name)) == MarketSessionStatus.PRE_MARKET
    assert get_session_status("hk_stock", market_time(2026, 6, 11, 9, 30, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("hk_stock", market_time(2026, 6, 11, 12, 0, tz_name)) == MarketSessionStatus.CLOSED
    assert get_session_status("hk_stock", market_time(2026, 6, 11, 13, 0, tz_name)) == MarketSessionStatus.REGULAR
    assert get_session_status("hk_stock", market_time(2026, 6, 11, 16, 0, tz_name)) == MarketSessionStatus.POST_MARKET
    assert get_session_status("hk_stock", market_time(2026, 6, 11, 17, 0, tz_name)) == MarketSessionStatus.CLOSED


def test_is_session_time_convenience_function() -> None:
    assert is_session_time("us_stock", market_time(2026, 6, 11, 8, 0, "America/New_York")) is True
    assert is_session_time("us_stock", market_time(2026, 6, 11, 10, 0, "America/New_York")) is True
    assert is_session_time("us_stock", market_time(2026, 6, 11, 17, 0, "America/New_York")) is True
    assert is_session_time("us_stock", market_time(2026, 6, 11, 21, 0, "America/New_York")) is False


def test_freshness_checker_remains_backward_compatible() -> None:
    checker = DataFreshnessChecker()
    now = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)

    assert checker.is_fresh(datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc), Timeframe.H1, now) is True
    assert checker.is_fresh(datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc), Timeframe.H1, now) is False


def test_freshness_checker_suppresses_staleness_while_session_closed() -> None:
    checker = DataFreshnessChecker()
    now = market_time(2026, 6, 11, 21, 0, "America/New_York")
    last_update = market_time(2026, 6, 11, 15, 30, "America/New_York")

    assert get_session_status("us_stock", now) == MarketSessionStatus.CLOSED
    assert checker.is_fresh(last_update, Timeframe.H1, now, session_context="us_stock") is True
    assert checker.get_freshness_status(last_update, Timeframe.H1, now, session_context="us_stock") == "session_closed"


def test_freshness_checker_pre_post_market_grace_period() -> None:
    checker = DataFreshnessChecker()
    now = market_time(2026, 6, 11, 8, 0, "America/New_York")
    last_update = market_time(2026, 6, 11, 3, 30, "America/New_York")

    assert get_session_status("us_stock", now) == MarketSessionStatus.PRE_MARKET
    assert checker.is_fresh(last_update, Timeframe.H1, now, session_context="us_stock") is True
