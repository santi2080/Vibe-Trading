"""交易时段配置

从 trading-assistant 移植
支持多个市场的交易时间定义
"""

from dataclasses import dataclass
from datetime import datetime, time, timezone
from enum import Enum
from typing import List, Optional
from zoneinfo import ZoneInfo


class MarketSessionStatus(Enum):
    """Trading session status for a market at a given UTC time."""

    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"
    HOLIDAY = "holiday"
    CONTINUOUS = "continuous"


MARKET_TZ: dict[str, str] = {
    "cn_stock": "Asia/Shanghai",
    "cn_stocks": "Asia/Shanghai",
    "cn_futures": "Asia/Shanghai",
    "us_stock": "America/New_York",
    "us_stocks": "America/New_York",
    "us_futures": "America/Chicago",
    "hk_stock": "Asia/Hong_Kong",
    "hk_stocks": "Asia/Hong_Kong",
}


def _ensure_utc(utc_dt: Optional[datetime]) -> datetime:
    if utc_dt is None:
        return datetime.now(timezone.utc)
    if utc_dt.tzinfo is None:
        return utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(timezone.utc)


def get_session_status(
    market_code: str, utc_dt: Optional[datetime] = None
) -> MarketSessionStatus:
    """Return session status for a market at the given UTC time."""
    code = market_code.lower()
    tz_name = MARKET_TZ.get(code)
    if tz_name is None:
        return MarketSessionStatus.CONTINUOUS

    market_dt = _ensure_utc(utc_dt).astimezone(ZoneInfo(tz_name))
    market_date = market_dt.date()
    t = market_dt.time()

    # Phase 19: Check if it's a market holiday (before session windows)
    from .holiday_calendar import is_trading_day

    trading = is_trading_day(code, market_date)
    if trading is False:
        return MarketSessionStatus.HOLIDAY

    if code in ("cn_stock", "cn_stocks"):
        if time(9, 30) <= t < time(11, 30) or time(13, 0) <= t < time(15, 0):
            return MarketSessionStatus.REGULAR
        if time(8, 30) <= t < time(9, 30):
            return MarketSessionStatus.PRE_MARKET
        if time(15, 0) <= t < time(16, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    if code == "cn_futures":
        if (
            time(9, 0) <= t < time(10, 15)
            or time(10, 30) <= t < time(11, 30)
            or time(13, 30) <= t < time(15, 0)
            or time(21, 0) <= t < time(23, 0)
        ):
            return MarketSessionStatus.REGULAR
        if time(8, 30) <= t < time(9, 0) or time(15, 0) <= t < time(21, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    if code in ("us_stock", "us_stocks"):
        if time(9, 30) <= t < time(16, 0):
            return MarketSessionStatus.REGULAR
        if time(4, 0) <= t < time(9, 30):
            return MarketSessionStatus.PRE_MARKET
        if time(16, 0) <= t < time(20, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    if code == "us_futures":
        if time(17, 0) <= t or t < time(16, 0):
            return MarketSessionStatus.REGULAR
        if time(16, 0) <= t < time(17, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    if code in ("hk_stock", "hk_stocks"):
        if time(9, 30) <= t < time(12, 0) or time(13, 0) <= t < time(16, 0):
            return MarketSessionStatus.REGULAR
        if time(9, 0) <= t < time(9, 30):
            return MarketSessionStatus.PRE_MARKET
        if time(16, 0) <= t < time(17, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    return MarketSessionStatus.CLOSED


def is_session_time(market_code: str, utc_dt: Optional[datetime] = None) -> bool:
    """Check if market is in an active session (pre-market, regular, or post-market).

    Returns True for PRE_MARKET, REGULAR, POST_MARKET, or CONTINUOUS (24/7 markets).
    Returns False for CLOSED or HOLIDAY.
    """
    status = get_session_status(market_code, utc_dt)
    return status not in (
        MarketSessionStatus.CLOSED,
        MarketSessionStatus.HOLIDAY,
    )


@dataclass
class TradingSession:
    """单个交易时段"""

    start: time
    end: time

    def contains(self, t: time) -> bool:
        """检查时间是否在时段内"""
        if self.start <= self.end:
            return self.start <= t <= self.end
        # 跨日夜盘
        return t >= self.start or t <= self.end


@dataclass
class TradingSessions:
    """交易日历定义"""

    day_sessions: List[TradingSession]
    night_sessions: Optional[List[TradingSession]] = None

    def is_trading_time(self, t: time) -> bool:
        """检查时间是否是交易时段"""
        for session in self.day_sessions:
            if session.contains(t):
                return True
        if self.night_sessions:
            for session in self.night_sessions:
                if session.contains(t):
                    return True
        return False


# 中国期货交易时段
CN_FUTURES_SESSIONS = TradingSessions(
    day_sessions=[
        TradingSession(time(9, 0), time(10, 15)),
        TradingSession(time(10, 30), time(11, 30)),
        TradingSession(time(13, 30), time(15, 0)),
    ],
    night_sessions=[
        TradingSession(time(21, 0), time(23, 0)),
    ],
)

# 美国期货交易时段 (CME Globex)
US_FUTURES_SESSIONS = TradingSessions(
    day_sessions=[
        TradingSession(time(8, 30), time(15, 0)),
    ],
    night_sessions=[
        TradingSession(time(17, 0), time(23, 59)),
    ],
)

# A股交易时段
CN_STOCK_SESSIONS = TradingSessions(
    day_sessions=[
        TradingSession(time(9, 30), time(11, 30)),
        TradingSession(time(13, 0), time(15, 0)),
    ],
    night_sessions=[],
)

# 港股交易时段
HK_STOCK_SESSIONS = TradingSessions(
    day_sessions=[
        TradingSession(time(9, 30), time(12, 0)),
        TradingSession(time(13, 0), time(16, 0)),
    ],
    night_sessions=[],
)

# 美股交易时段
US_STOCK_SESSIONS = TradingSessions(
    day_sessions=[
        TradingSession(time(9, 30), time(16, 0)),
    ],
    night_sessions=[],
)


def get_trading_sessions(market_code: str) -> Optional[TradingSessions]:
    """获取市场的交易时段"""
    sessions_map = {
        "cn_futures": CN_FUTURES_SESSIONS,
        "us_futures": US_FUTURES_SESSIONS,
        "cn_stocks": CN_STOCK_SESSIONS,
        "cn_stock": CN_STOCK_SESSIONS,
        "hk_stocks": HK_STOCK_SESSIONS,
        "hk_stock": HK_STOCK_SESSIONS,
        "us_stocks": US_STOCK_SESSIONS,
        "us_stock": US_STOCK_SESSIONS,
    }
    return sessions_map.get(market_code.lower())
