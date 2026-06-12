"""Holiday calendar for exchange trading days."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    pass

# Import holiday calendars lazily to avoid import-time overhead
_holiday_calendars: dict[str, object] = {}

# Map market codes to timezone names (shares with trading_sessions.py MARKET_TZ)
_MARKET_TZ: dict[str, str] = {
    "us_stock": "America/New_York",
    "us_stocks": "America/New_York",
    "cn_stock": "Asia/Shanghai",
    "cn_stocks": "Asia/Shanghai",
    "hk_stock": "Asia/Hong_Kong",
    "hk_stocks": "Asia/Hong_Kong",
}


def _get_calendar(market_code: str):
    """Lazily create and cache holiday calendar instances."""
    code = market_code.lower()
    if code in _holiday_calendars:
        return _holiday_calendars[code]

    # Import calendar classes
    try:
        from holidays.financial.ny_stock_exchange import NewYorkStockExchange
        from holidays.financial.shanghai_stock_exchange import ShanghaiStockExchange
        from holidays.financial.hong_kong_stock_exchange import HongKongStockExchange
    except ImportError:
        return None

    if code in ("us_stock", "us_stocks"):
        cal = NewYorkStockExchange()
    elif code in ("cn_stock", "cn_stocks"):
        cal = ShanghaiStockExchange()
    elif code in ("hk_stock", "hk_stocks"):
        cal = HongKongStockExchange()
    else:
        return None

    _holiday_calendars[code] = cal
    return cal


def is_trading_day(market_code: str, dt_or_date) -> Optional[bool]:
    """Return True if trading day, False if holiday, None if unknown market.

    Args:
        market_code: Market identifier (e.g., 'cn_stock', 'us_stock', 'hk_stock')
        dt_or_date: datetime or date object to check

    Returns:
        True if trading day, False if holiday, None if market not supported.
        Note: Half-day trading (e.g., NYSE Christmas Eve) returns True (still a trading day).
    """
    code = market_code.lower()

    # Get market timezone
    tz_name = _MARKET_TZ.get(code)
    if tz_name is None:
        return None  # Unknown market

    # Extract market-local date (critical — prevents UTC midnight date shift)
    if isinstance(dt_or_date, datetime):
        market_local_date = dt_or_date.astimezone(ZoneInfo(tz_name)).date()
    elif isinstance(dt_or_date, date):
        market_local_date = dt_or_date
    else:
        return None

    # Get or create calendar
    cal = _get_calendar(code)
    if cal is None:
        return None

    # Check if this is a holiday using .get() method
    # .get(date) returns holiday name string if holiday, None if not a holiday
    holiday_name = cal.get(market_local_date)
    return holiday_name is None  # None = not a holiday = trading day


def is_holiday(market_code: str, dt_or_date) -> Optional[bool]:
    """Return True if market is closed for a holiday on the given date.

    Args:
        market_code: Market identifier (e.g., 'cn_stock', 'us_stock')
        dt_or_date: datetime or date object to check

    Returns:
        True if holiday, False if trading day, None if unknown market.
    """
    trading = is_trading_day(market_code, dt_or_date)
    if trading is None:
        return None
    return not trading


def get_holiday_name(market_code: str, dt_or_date) -> Optional[str]:
    """Return the name of the holiday if the date is a holiday.

    Args:
        market_code: Market identifier
        dt_or_date: datetime or date object to check

    Returns:
        Holiday name string if holiday, None if trading day or unknown market.
    """
    code = market_code.lower()
    tz_name = _MARKET_TZ.get(code)
    if tz_name is None:
        return None

    if isinstance(dt_or_date, datetime):
        market_local_date = dt_or_date.astimezone(ZoneInfo(tz_name)).date()
    elif isinstance(dt_or_date, date):
        market_local_date = dt_or_date
    else:
        return None

    cal = _get_calendar(code)
    if cal is None:
        return None

    return cal.get(market_local_date)
