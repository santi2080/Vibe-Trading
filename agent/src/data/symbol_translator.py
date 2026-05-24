"""代码格式翻译器 - 实现不同数据源之间的代码格式转换

从 trading-assistant 移植的核心模块

设计理念：
1. 统一标准格式：项目内部使用标准格式
   - 美国期货: Yahoo Finance 格式（如 SI=F）
   - 中国期货: Akshare 格式（如 ag0, rb0）
   - A股: 6位数字（如 600036）
   - 港股: 5位数字（如 00700）
2. 实时翻译：调用各数据源 API 时自动转换为对应格式
3. 可扩展：易于添加新的数据源和代码映射
"""

import logging
from enum import Enum
from typing import Dict, Optional

from .market import Market

logger = logging.getLogger(__name__)


class DataVendor(Enum):
    """数据供应商枚举"""

    YAHOO_FINANCE = "yahoo"
    TWELVEDATA = "twelvedata"
    AKSHARE = "akshare"
    ITICK = "itick"
    TUSHARE = "tushare"
    QUANDL = "quandl"
    ALPHAVANTAGE = "alphavantage"
    TQSDK = "tqsdk"
    DATABENTO = "databento"


class SymbolTranslator:
    """证券代码翻译器

    负责在不同数据源的代码格式之间进行转换
    """

    # TqSdk 交易所代码映射
    TQSDK_EXCHANGE_MAP = {
        # 金融期货
        "IF": "CFFEX", "IC": "CFFEX", "IH": "CFFEX",
        "TS": "CFFEX", "TF": "CFFEX", "T": "CFFEX",
        # 上海期货交易所
        "cu": "SHFE", "al": "SHFE", "zn": "SHFE", "pb": "SHFE",
        "ni": "SHFE", "sn": "SHFE", "au": "SHFE", "ag": "SHFE",
        "rb": "SHFE", "wr": "SHFE", "hc": "SHFE", "ss": "SHFE",
        # 大连商品交易所
        "c": "DCE", "cs": "DCE", "a": "DCE", "b": "DCE",
        "m": "DCE", "y": "DCE", "p": "DCE", "jd": "DCE",
        "l": "DCE", "v": "DCE", "pp": "DCE", "j": "DCE",
        "jm": "DCE", "i": "DCE", "fb": "DCE", "bb": "DCE",
        "pg": "DCE", "eg": "DCE", "rr": "DCE",
        # 郑州商品交易所
        "WH": "CZCE", "PM": "CZCE", "CF": "CZCE", "CY": "CZCE",
        "SR": "CZCE", "TA": "CZCE", "OI": "CZCE", "MA": "CZCE",
        "FG": "CZCE", "RS": "CZCE", "RM": "CZCE", "ZC": "CZCE",
        "JR": "CZCE", "LR": "CZCE", "SF": "CZCE", "SM": "CZCE",
        "AP": "CZCE", "CJ": "CZCE", "UR": "CZCE", "SA": "CZCE",
        "PF": "CZCE", "PK": "CZCE",
        # 上海国际能源交易中心
        "sc": "INE", "lu": "INE", "nr": "INE", "bc": "INE",
    }

    # Tushare 交易所映射
    TUSHARE_EXCHANGE_MAP = {
        "SH": "SH", "SZ": "SZ",
        "SHFE": "SHF", "DCE": "DCE", "CZCE": "CZC", "CFFEX": "CFX", "INE": "INE",
    }

    # Yahoo Finance / RapidAPI 期货代码映射
    YAHOO_FUTURES_MAP = {
        "C": "ZC",  # 玉米: C=F -> ZC=F
        "S": "ZS",  # 大豆: S=F -> ZS=F
        "W": "ZW",  # 小麦: W=F -> ZW=F
    }

    # Databento 期货代码映射
    DATABENTO_FUTURES_MAP = {
        "GC": "GC.c.0", "SI": "SI.c.0", "CL": "CL.c.0",
        "NG": "NG.c.0", "HG": "HG.c.0",
        "ES": "ES.c.0", "NQ": "NQ.c.0", "YM": "YM.c.0",
        "6E": "6E.c.0", "6J": "6J.c.0", "6B": "6B.c.0", "6A": "6A.c.0",
    }

    @classmethod
    def to_vendor_format(cls, symbol: str, vendor: DataVendor, market: Market) -> str:
        """将标准格式转换为特定数据源的格式

        Args:
            symbol: 标准格式代码
            vendor: 目标数据源
            market: 市场类型

        Returns:
            数据源特定格式的代码
        """
        # 美国期货 - Yahoo Finance 需要 CBOT 农产品符号映射
        if market == Market.US_FUTURES and vendor == DataVendor.YAHOO_FINANCE:
            return cls._to_yahoo_finance_format(symbol)

        # 美国期货 - Databento 需要连续合约格式
        if market == Market.US_FUTURES and vendor == DataVendor.DATABENTO:
            return cls._to_databento_format(symbol)

        # 中国期货 - TqSdk 格式
        if market == Market.CN_FUTURES and vendor == DataVendor.TQSDK:
            return cls.to_tqsdk_format(symbol, market)

        # 中国期货 - Tushare 格式
        if market == Market.CN_FUTURES and vendor == DataVendor.TUSHARE:
            return symbol

        # A股 - Akshare 只需要纯数字
        if market == Market.CN_STOCK and vendor == DataVendor.AKSHARE:
            return symbol.replace(".", "")

        # A股 - Tushare 需要交易所后缀
        if market == Market.CN_STOCK and vendor == DataVendor.TUSHARE:
            return symbol  # 调用者需要添加交易所

        # 港股 - Yahoo Finance 需要 .HK 后缀
        if market == Market.HK_STOCK and vendor == DataVendor.YAHOO_FINANCE:
            return f"{symbol}.HK" if not symbol.endswith(".HK") else symbol

        # 港股 - Akshare 需要 5 位数字
        if market == Market.HK_STOCK and vendor == DataVendor.AKSHARE:
            return symbol.zfill(5)

        # 默认返回原始符号
        return symbol

    @classmethod
    def _to_yahoo_finance_format(cls, symbol: str) -> str:
        """转换为 Yahoo Finance / RapidAPI 格式"""
        if symbol.endswith("=F"):
            base = symbol[:-2]
        else:
            base = symbol

        yahoo_symbol = cls.YAHOO_FUTURES_MAP.get(base)
        if yahoo_symbol:
            return f"{yahoo_symbol}=F"
        return symbol

    @classmethod
    def _to_databento_format(cls, symbol: str) -> str:
        """转换为 Databento 连续合约格式"""
        if symbol.endswith("=F"):
            base = symbol[:-2]
        else:
            base = symbol

        return cls.DATABENTO_FUTURES_MAP.get(base, f"{base}.c.0")

    @classmethod
    def to_tqsdk_format(cls, symbol: str, market: Market) -> str:
        """转换为 TqSdk 格式

        Args:
            symbol: 标准格式代码（如 ag0, rb0, TA0）
            market: 市场类型

        Returns:
            TqSdk 格式（如 KQ.m@SHFE.ag）
        """
        if market != Market.CN_FUTURES:
            return symbol

        # 提取基础代码
        base = "".join(filter(str.isalpha, symbol))
        exchange = cls.TQSDK_EXCHANGE_MAP.get(base.upper(), "SHFE")

        # 主连合约
        if symbol.endswith("0"):
            if exchange == "CZCE":
                return f"KQ.m@{exchange}.{base.upper()}"
            return f"KQ.m@{exchange}.{base.lower()}"

        # 具体合约
        if exchange == "CZCE":
            return f"{exchange}.{symbol.upper()}"
        return f"{exchange}.{symbol}"

    @classmethod
    def is_supported_by_vendor(cls, symbol: str, vendor: DataVendor) -> bool:
        """检查代码是否被数据源支持"""
        return True  # 默认全部支持
