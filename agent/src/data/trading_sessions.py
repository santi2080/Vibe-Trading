"""交易时段配置

从 trading-assistant 移植
支持多个市场的交易时间定义
"""

from dataclasses import dataclass
from datetime import time
from typing import List, Optional


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
