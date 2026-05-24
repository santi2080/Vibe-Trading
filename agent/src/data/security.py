"""证券标的模型

从 trading-assistant 移植
"""

from dataclasses import dataclass
from typing import Optional

from .market import Market


@dataclass(frozen=True)
class Security:
    """证券标的"""

    symbol: str  # 代码（标准格式）
    name: str  # 名称
    market: Market  # 市场
    exchange: str  # 交易所
    sector: Optional[str] = None  # 板块
    contract_type: Optional[str] = None  # 合约类型
    multiplier: Optional[float] = None  # 一手乘数
    atr: Optional[float] = None  # ATR (14日平均真实波幅)


@dataclass(frozen=True)
class OHLCV:
    """单个K线数据点"""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
