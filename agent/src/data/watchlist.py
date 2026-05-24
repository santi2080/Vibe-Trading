"""Watchlist 读取器

支持从 CSV 配置文件读取品种列表
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional

from .security import Security
from .market import Market, parse_market

logger = logging.getLogger(__name__)


class WatchlistReader:
    """Watchlist 读取器

    支持 CSV 格式:
    symbol,name,market,exchange,sector,timeframes,contract_type,multiplier,max_lots,ATR

    完整示例:
    GC=F,黄金,US_FUTURES,COMEX,贵金属,1D-4H,standard,1,4,70.0047
    SI=F,白银,US_FUTURES,COMEX,贵金属,1D-4H,standard,100,1,2.8134

    简化示例（兼容旧格式）:
    GC=F,黄金,us_futures,1D-1H,commodities
    """

    def __init__(self, watchlist_path: str = "watchlist/my_watchlist.csv"):
        """初始化

        Args:
            watchlist_path: watchlist 文件路径
        """
        self.watchlist_path = Path(watchlist_path)

    def load(self) -> List[Security]:
        """加载 watchlist

        Returns:
            Security 列表
        """
        securities = []

        if not self.watchlist_path.exists():
            logger.warning(f"Watchlist not found: {self.watchlist_path}")
            return securities

        with open(self.watchlist_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        # 找到数据行
        data_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "," in stripped:
                data_lines.append(stripped)

        # 解析 CSV
        for line in data_lines:
            try:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue

                symbol = parts[0]
                name = parts[1] if len(parts) > 1 else symbol
                market_str = parts[2] if len(parts) > 2 else "us_futures"
                exchange = parts[3] if len(parts) > 3 else ""
                sector = parts[4] if len(parts) > 4 else ""
                timeframes = parts[5] if len(parts) > 5 else "1D-1H"
                contract_type = parts[6] if len(parts) > 6 else ""
                # parts[7] is trade_contract_type (extra field, skip)
                try:
                    multiplier = float(parts[8]) if len(parts) > 8 and parts[8] else 1.0
                except ValueError:
                    multiplier = 1.0
                try:
                    max_lots = int(parts[9]) if len(parts) > 9 and parts[9] else 1
                except ValueError:
                    max_lots = 1
                try:
                    atr = float(parts[10]) if len(parts) > 10 and parts[10] else 0.0
                except ValueError:
                    atr = 0.0

                # 解析市场
                try:
                    market = parse_market(market_str)
                except ValueError:
                    logger.warning(f"Unknown market: {market_str}, skipping {symbol}")
                    continue

                # 如果没有指定交易所，使用默认值
                if not exchange:
                    exchange = self._get_default_exchange(market)

                security = Security(
                    symbol=symbol,
                    name=name,
                    market=market,
                    exchange=exchange,
                    sector=sector,
                    contract_type=contract_type if contract_type else None,
                    multiplier=multiplier if multiplier != 1.0 else None,
                    atr=atr if atr > 0 else None,
                )
                securities.append(security)

            except Exception as e:
                logger.warning(f"Failed to parse line: {line}, error: {e}")
                continue

        logger.info(f"Loaded {len(securities)} securities from watchlist")
        return securities

    def load_raw(self) -> List[dict]:
        """加载 watchlist（原始字典格式）

        Returns:
            字典列表，包含所有字段:
            - symbol, name, market, exchange, sector
            - timeframes, contract_type, multiplier, max_lots, atr
        """
        items = []

        if not self.watchlist_path.exists():
            logger.warning(f"Watchlist not found: {self.watchlist_path}")
            return items

        with open(self.watchlist_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            # 跳过注释、空行和表头
            if stripped and not stripped.startswith("#") and "," in stripped:
                # 跳过 CSV 表头
                if stripped.lower().startswith("symbol,") or stripped.lower().startswith("code,"):
                    continue
                parts = [p.strip() for p in stripped.split(",")]
                if len(parts) >= 2:
                    item = {
                        "symbol": parts[0],
                        "name": parts[1] if len(parts) > 1 else parts[0],
                        "market": parts[2] if len(parts) > 2 else "us_futures",
                        "exchange": parts[3] if len(parts) > 3 else "",
                        "sector": parts[4] if len(parts) > 4 else "",
                        "timeframes": parts[5] if len(parts) > 5 else "1D-1H",
                        "contract_type": parts[6] if len(parts) > 6 else "",
                        # parts[7] is trade_contract_type (extra field, skip)
                        "multiplier": float(parts[8]) if len(parts) > 8 and parts[8] else 1.0,
                        "max_lots": float(parts[9]) if len(parts) > 9 and parts[9] else 1,
                        "atr": float(parts[10]) if len(parts) > 10 and parts[10] else 0.0,
                    }
                    items.append(item)

        return items

    @staticmethod
    def _get_default_exchange(market: Market) -> str:
        """获取默认交易所"""
        exchange_map = {
            Market.US_STOCK: "NASDAQ",
            Market.US_FUTURES: "CME",
            Market.US_ETF: "NASDAQ",
            Market.CN_STOCK: "SSE",
            Market.CN_FUTURES: "SHFE",
            Market.CN_ETF: "SSE",
            Market.HK_STOCK: "HKEX",
            Market.HK_FUTURES: "HKEX",
        }
        return exchange_map.get(market, "UNKNOWN")

    def filter_by_market(self, securities: List[Security], market: Market) -> List[Security]:
        """按市场筛选"""
        return [s for s in securities if s.market == market]

    def filter_by_sector(self, securities: List[Security], sector: str) -> List[Security]:
        """按板块筛选"""
        return [s for s in securities if s.sector == sector]

    def get_symbols(self, securities: Optional[List[Security]] = None) -> List[str]:
        """获取所有代码"""
        if securities is None:
            securities = self.load()
        return [s.symbol for s in securities]

    def get_timeframes(self, symbol: str) -> tuple:
        """获取指定品种的时间周期配置

        Args:
            symbol: 品种代码

        Returns:
            (primary_timeframe, secondary_timeframe)
            例如: ("1D", "1H")
        """
        raw_items = self.load_raw()
        for item in raw_items:
            if item["symbol"] == symbol:
                timeframes = item.get("timeframes", "1D-1H")
                parts = timeframes.split("-")
                if len(parts) >= 2:
                    return parts[0].strip(), parts[1].strip()
                return "1D", "1H"
        return "1D", "1H"

    def get_trade_config(self, symbol: str) -> dict:
        """获取指定品种的交易配置

        Args:
            symbol: 品种代码

        Returns:
            交易配置字典:
            - primary_tf: 主周期
            - secondary_tf: 次周期
            - multiplier: 合约乘数
            - max_lots: 最大持仓手数
            - atr: ATR 值
        """
        raw_items = self.load_raw()
        for item in raw_items:
            if item["symbol"] == symbol:
                timeframes = item.get("timeframes", "1D-1H")
                parts = timeframes.split("-")
                primary_tf = parts[0].strip() if len(parts) >= 1 else "1D"
                secondary_tf = parts[1].strip() if len(parts) >= 2 else "1H"

                return {
                    "primary_tf": primary_tf,
                    "secondary_tf": secondary_tf,
                    "multiplier": item.get("multiplier", 1.0),
                    "max_lots": item.get("max_lots", 1),
                    "atr": item.get("atr", 0.0),
                    "contract_type": item.get("contract_type", ""),
                }
        return {
            "primary_tf": "1D",
            "secondary_tf": "1H",
            "multiplier": 1.0,
            "max_lots": 1,
            "atr": 0.0,
            "contract_type": "",
        }
