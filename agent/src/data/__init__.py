"""数据层模块

从 trading-assistant 移植的核心数据功能

主要组件:
- market: 市场和时间周期枚举
- security: 证券标的模型
- symbol_translator: 代码格式转换
- trading_sessions: 交易时段配置
- base: 数据获取器基类
- freshness: 数据新鲜度检查
- quality: 数据质量监控
- watchlist: Watchlist 读取器
"""

from .market import Market, Timeframe, TrendDirection, parse_market, parse_timeframe
from .security import Security, OHLCV
from .symbol_translator import SymbolTranslator, DataVendor
from .trading_sessions import (
    TradingSession,
    TradingSessions,
    get_trading_sessions,
    MarketSessionStatus,
    get_session_status,
    is_session_time,
    MARKET_TZ,
    CN_FUTURES_SESSIONS,
    CN_STOCK_SESSIONS,
    US_FUTURES_SESSIONS,
    US_STOCK_SESSIONS,
    HK_STOCK_SESSIONS,
)
from .base import BaseFetcher, FetchResult
from .freshness import DataFreshnessChecker
from .quality import DataQualityMonitor, QualityReport, QualityIssue
from .watchlist import WatchlistReader
from .holiday_calendar import is_trading_day, is_holiday, get_holiday_name

__all__ = [
    # 市场
    "Market",
    "Timeframe",
    "TrendDirection",
    "parse_market",
    "parse_timeframe",
    # 证券
    "Security",
    "OHLCV",
    # 代码转换
    "SymbolTranslator",
    "DataVendor",
    # 交易时段
    "TradingSession",
    "TradingSessions",
    "get_trading_sessions",
    "CN_FUTURES_SESSIONS",
    "CN_STOCK_SESSIONS",
    "US_FUTURES_SESSIONS",
    "US_STOCK_SESSIONS",
    "HK_STOCK_SESSIONS",
    "MarketSessionStatus",
    "get_session_status",
    "is_session_time",
    "MARKET_TZ",
    # 基类
    "BaseFetcher",
    "FetchResult",
    # 质量检查
    "DataFreshnessChecker",
    "DataQualityMonitor",
    "QualityReport",
    "QualityIssue",
    # Watchlist
    "WatchlistReader",
    # Holiday calendar
    "is_trading_day",
    "is_holiday",
    "get_holiday_name",
]
