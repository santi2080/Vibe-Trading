"""市场和时间周期枚举定义

从 trading-assistant 移植的核心数据模型
"""

from enum import Enum, auto


class Market(Enum):
    """市场枚举 (Phase 11 canonical)"""

    US_STOCK = auto()  # 美股 / 加密货币 / 外汇（通过不同 vendor）
    US_FUTURES = auto()  # 美国期货
    US_ETF = auto()  # 美国ETF
    CN_STOCK = auto()  # A股
    CN_FUTURES = auto()  # 中国期货
    CN_ETF = auto()  # 中国ETF
    HK_STOCK = auto()  # 港股
    HK_FUTURES = auto()  # 港期

    # 虚拟市场类型（用于数据源路由）
    US_FUTURES_INTRADAY = auto()  # 美国期货日内数据（H4/H1）
    US_FUTURES_DAILY = auto()  # 美国期货日线数据（D1/W1）


class Timeframe(Enum):
    """时间周期枚举"""

    W1 = "1w"  # 周线
    D1 = "1d"  # 日线
    H4 = "4h"  # 4小时
    H1 = "1h"  # 1小时


class TrendDirection(Enum):
    """趋势方向"""

    UP = "up"  # 上涨
    DOWN = "down"  # 下跌
    SIDEWAYS = "sideways"  # 震荡


# 支持 H4 周期的市场
MARKETS_WITH_H4 = {Market.CN_FUTURES, Market.US_FUTURES, Market.US_FUTURES_INTRADAY}

# 可重采样周期映射（不需要下载，从依赖周期实时计算）
RESAMPLABLE_TIMEFRAMES = {
    Timeframe.W1: Timeframe.D1,  # W1 从 D1 重采样
    Timeframe.H4: Timeframe.H1,  # H4 从 H1 重采样
}


# 字符串到枚举的转换
MARKET_STR_TO_ENUM = {
    "us_stock": Market.US_STOCK,
    "us_futures": Market.US_FUTURES,
    "us_etf": Market.US_ETF,
    "cn_stock": Market.CN_STOCK,
    "cn_stocks": Market.CN_STOCK,
    "cn_futures": Market.CN_FUTURES,
    "cn_etf": Market.CN_ETF,
    "hk_stock": Market.HK_STOCK,
    "hk_futures": Market.HK_FUTURES,
    # Uppercase variants
    "US_STOCK": Market.US_STOCK,
    "US_FUTURES": Market.US_FUTURES,
    "US_ETF": Market.US_ETF,
    "CN_STOCK": Market.CN_STOCK,
    "CN_STOCKS": Market.CN_STOCK,
    "CN_FUTURES": Market.CN_FUTURES,
    "CN_ETF": Market.CN_ETF,
    "HK_STOCK": Market.HK_STOCK,
    "HK_FUTURES": Market.HK_FUTURES,
}

TIMEFRAME_STR_TO_ENUM = {
    "1w": Timeframe.W1,
    "w1": Timeframe.W1,
    "weekly": Timeframe.W1,
    "1d": Timeframe.D1,
    "d1": Timeframe.D1,
    "daily": Timeframe.D1,
    "4h": Timeframe.H4,
    "h4": Timeframe.H4,
    "1h": Timeframe.H1,
    "h1": Timeframe.H1,
    "hourly": Timeframe.H1,
}


def parse_market(market_str: str) -> Market:
    """解析市场字符串到枚举"""
    key = market_str.lower().strip()
    if key not in MARKET_STR_TO_ENUM:
        raise ValueError(f"Unknown market: {market_str}")
    return MARKET_STR_TO_ENUM[key]


def parse_timeframe(tf_str: str) -> Timeframe:
    """解析时间周期字符串到枚举"""
    key = tf_str.lower().strip()
    if key not in TIMEFRAME_STR_TO_ENUM:
        raise ValueError(f"Unknown timeframe: {tf_str}")
    return TIMEFRAME_STR_TO_ENUM[key]
