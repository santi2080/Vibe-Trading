"""AKShare loader: free, no-auth data for A-shares, US, US futures, HK, futures, forex, macro.

AKShare (https://github.com/akfamily/akshare) is a completely free financial
data aggregator covering Chinese and global markets.  No API token required.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

from agent.backtest.loaders.base import validate_date_range
from agent.backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_INTERVAL_MAP_DAILY = {
    "1D": "daily",
    "1W": "weekly",
    "1M": "monthly",
}


def _is_a_share(code: str) -> bool:
    return code.upper().endswith((".SZ", ".SH", ".BJ"))


def _is_hk(code: str) -> bool:
    return code.upper().endswith(".HK")


def _is_us(code: str) -> bool:
    return code.upper().endswith(".US")


def _is_crypto(code: str) -> bool:
    return "-USDT" in code.upper() or "/USDT" in code.upper()


# Exchange-listed ETF / LOF prefix codes:
#   SH: 50/51/52/56/58 (ETFs), SZ: 15/16 (ETFs + LOFs).
# Issue #50 — these symbols look like A-shares (.SH / .SZ) but stock_zh_a_hist
# can't price them; route through fund_etf_hist_sina instead.
_ETF_PREFIXES = frozenset({"15", "16", "50", "51", "52", "56", "58"})


# CN Futures symbol mapping: al0 -> AL0
# AKShare uses uppercase codes like 'RB0', 'AL0' instead of 'rb0', 'al0'
_CN_FUTURES_MAP = {
    "al0": "AL0",   # 铝
    "rb0": "RB0",   # 螺纹钢
    "ru0": "RU0",   # 天然橡胶
    "ta0": "TA0",   # PTA
    "hc0": "HC0",   # 热卷
    "cu0": "CU0",   # 铜
    "zn0": "ZN0",   # 锌
    "pb0": "PB0",   # 铅
    "ni0": "NI0",   # 镍
    "sn0": "SN0",   # 锡
    "ag0": "AG0",   # 白银
    "au0": "AU0",   # 黄金
    "bu0": "BU0",   # 沥青
    "fu0": "FU0",   # 燃油
    "ma0": "MA0",   # 甲醇
    "pp0": "PP0",   # 聚丙烯
    "l0": "L0",     # 塑料
    "v0": "V0",     # PVC
    "p0": "P0",     # 棕榈油
    "y0": "Y0",     # 豆油
    "m0": "M0",     # 豆粕
    "jm0": "JM0",   # 焦煤
    "j0": "J0",     # 焦炭
    "zc0": "ZC0",   # 动力煤
    "cs0": "CS0",   # 玉米淀粉
    "cf0": "CF0",   # 棉花
    "sr0": "SR0",   # 白糖
    "sc0": "SC0",   # 原油
}


def _is_cn_futures(code: str) -> bool:
    """Detect CN futures symbols (al0, rb0, ru0, etc.)"""
    return code.lower() in _CN_FUTURES_MAP or code.lower().rstrip("0") in _CN_FUTURES_MAP


def _is_etf_listed(code: str) -> bool:
    """Detect exchange-listed ETF / LOF symbols (e.g. 518880.SH, 159915.SZ)."""
    upper = code.upper()
    if not upper.endswith((".SH", ".SZ")):
        return False
    digits = upper.split(".")[0]
    if len(digits) != 6 or not digits.isdigit():
        return False
    return digits[:2] in _ETF_PREFIXES


def _is_forex(code: str) -> bool:
    """Detect forex pairs by matching against AKShare's symbol_market_map.

    Issue #54 — forex symbols (EURUSD, GBPUSD, etc.) have no exchange suffix
    and previously fell through to the A-share endpoint.
    """
    upper = code.upper().removesuffix(".FX")
    try:
        from akshare.forex.cons import symbol_market_map
    except Exception:
        return False
    return upper in symbol_market_map


# US Futures symbols (akshare format: GC, SI, CL, HG, ES, NQ)
_US_FUTURES_SYMBOLS = frozenset({"GC", "SI", "CL", "HG", "ES", "NQ", "NG", "ZC", "ZS", "ZW", "ZS"})


def _is_us_futures(code: str) -> bool:
    """Detect US futures symbols (e.g. GC=F, SI=F, CL=F).

    AKShare uses simple symbols like 'GC' for gold, 'SI' for silver.
    """
    # Remove common suffixes like =F, =P
    base = code.upper().replace("=F", "").replace("=P", "").replace("=U", "")
    return base in _US_FUTURES_SYMBOLS


@register
class DataLoader:
    """AKShare universal OHLCV loader (free, no auth)."""

    name = "akshare"
    markets = {"a_share", "us_equity", "hk_equity", "us_futures", "cn_futures", "futures", "fund", "macro", "forex"}
    requires_auth = False

    def is_available(self) -> bool:
        """Available if akshare is installed."""
        try:
            import akshare  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self) -> None:
        pass

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data via AKShare.

        Args:
            codes: Symbol list.
            start_date: YYYY-MM-DD.
            end_date: YYYY-MM-DD.
            interval: Bar size (only 1D supported currently).
            fields: Ignored.

        Returns:
            Mapping symbol -> OHLCV DataFrame.
        """
        validate_date_range(start_date, end_date)

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                df = self._fetch_one(code, start_date, end_date, interval)
                if df is not None and not df.empty:
                    result[code] = df
            except Exception as exc:
                logger.warning("akshare failed for %s: %s", code, exc)
        return result

    def _fetch_one(
        self, code: str, start_date: str, end_date: str, interval: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch a single symbol."""
        import akshare as ak

        # Check for CN futures first (before US futures)
        if _is_cn_futures(code):
            return self._fetch_cn_futures(ak, code, start_date, end_date, interval)
        # Check for US futures
        if _is_us_futures(code):
            return self._fetch_us_futures(ak, code, start_date, end_date, interval)
        # ETF check must precede A-share — 518880.SH ends with .SH but is an ETF.
        if _is_etf_listed(code):
            return self._fetch_etf(ak, code, start_date, end_date)
        if _is_a_share(code):
            return self._fetch_a_share(ak, code, start_date, end_date, interval)
        if _is_us(code):
            return self._fetch_us(ak, code, start_date, end_date)
        if _is_hk(code):
            return self._fetch_hk(ak, code, start_date, end_date)
        if _is_forex(code):
            return self._fetch_forex(ak, code, start_date, end_date)
        # Default: try A-share
        return self._fetch_a_share(ak, code, start_date, end_date, interval)

    def _fetch_a_share(
        self, ak, code: str, start_date: str, end_date: str, interval: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch A-share via stock_zh_a_daily (Sina, more reliable than Eastmoney).

        Sina format is 'sh600519' or 'sz000001'.
        Note: '大量抓取容易封 IP' - rate limiting may apply for bulk requests.
        """
        parts = code.upper().split(".")
        symbol_raw = parts[0]
        suffix = parts[1] if len(parts) > 1 else ""

        # Convert to Sina format: 600519.SH -> sh600519, 000001.SZ -> sz000001
        if suffix == "SH":
            symbol = f"sh{symbol_raw}"
        elif suffix == "SZ":
            symbol = f"sz{symbol_raw}"
        else:
            # Fallback: assume Shanghai
            symbol = f"sh{symbol_raw}"

        df = ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",  # forward-adjusted prices
        )
        if df is None or df.empty:
            return None
        return self._normalize(df, date_col="date")

    def _fetch_us(self, ak, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch US stock via stock_us_hist."""
        symbol = code.replace(".US", "")
        # akshare uses the format like "105.AAPL" for NASDAQ
        # Try common prefixes
        for prefix in ["105.", "106.", ""]:
            try:
                df = ak.stock_us_hist(
                    symbol=f"{prefix}{symbol}",
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="qfq",
                )
                if df is not None and not df.empty:
                    return self._normalize(df, date_col="日期")
            except Exception:
                continue
        return None

    def _fetch_etf(self, ak, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch exchange-listed ETF / LOF via fund_etf_hist_sina.

        Sina symbol format is ``sh518880`` / ``sz159915``. The endpoint returns
        the full history; we filter to the requested window after fetching.
        """
        digits, _, suffix = code.upper().partition(".")
        symbol = f"{suffix.lower()}{digits}"
        df = ak.fund_etf_hist_sina(symbol=symbol)
        if df is None or df.empty:
            return None
        df = self._normalize(df, date_col="date")
        # fund_etf_hist_sina returns full history — clip to window.
        return df.loc[start_date:end_date]

    def _fetch_forex(self, ak, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch forex pair via forex_hist_em.

        Columns returned are 日期 / 代码 / 名称 / 今开 / 最新价 / 最高 / 最低 / 振幅
        — note ``最新价`` (latest) plays the role of close. Volume isn't reported,
        so we synthesize a zero column to satisfy the OHLCV contract.
        """
        symbol = code.upper().removesuffix(".FX")
        df = ak.forex_hist_em(symbol=symbol)
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            "日期": "trade_date",
            "今开": "open",
            "最新价": "close",
            "最高": "high",
            "最低": "low",
        })
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date").sort_index()
        df["volume"] = 0.0
        for col in ("open", "high", "low", "close"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]
        )
        return df.loc[start_date:end_date]

    def _fetch_hk(self, ak, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch HK stock via stock_hk_hist."""
        symbol = code.replace(".HK", "").zfill(5)
        df = ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        if df is None or df.empty:
            return None
        return self._normalize(df, date_col="日期")

    def _fetch_us_futures(
        self, ak, code: str, start_date: str, end_date: str, interval: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch US futures via futures_foreign_hist.

        AKShare uses simple symbols like 'GC' for gold, 'SI' for silver, 'CL' for crude oil.
        Converts from formats like GC=F to GC.

        Returns daily data only (akshare doesn't support intraday for foreign futures).
        """
        # Convert GC=F to GC
        symbol = code.upper().replace("=F", "").replace("=P", "")

        try:
            df = ak.futures_foreign_hist(symbol=symbol)
            if df is None or df.empty:
                return None

            # Normalize columns
            if "date" in df.columns:
                df = df.rename(columns={"date": "trade_date"})
            if "s" in df.columns:
                df = df.drop(columns=["s"], errors="ignore")
            if "settlement" in df.columns:
                df = df.drop(columns=["settlement"], errors="ignore")

            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date").sort_index()

            # Filter to date range
            df = df.loc[start_date:end_date]

            # Ensure volume is numeric (akshare may return 0 for non-trading hours)
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

            return df[["open", "high", "low", "close", "volume"]]

        except Exception as e:
            logger.warning("US futures fetch failed for %s: %s", code, e)
            return None

    def _fetch_cn_futures(
        self, ak, code: str, start_date: str, end_date: str, interval: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch CN futures via futures_zh_daily_sina.

        AKShare uses uppercase codes like 'RB0', 'AL0' instead of 'rb0', 'al0'.
        Maps from simple codes (al0, rb0) to AKShare format (AL0, RB0).

        Returns daily data only.
        """
        # Convert al0 -> AL0, rb0 -> RB0
        code_lower = code.lower()
        if code_lower in _CN_FUTURES_MAP:
            symbol = _CN_FUTURES_MAP[code_lower]
        else:
            # Try uppercase without 0
            symbol = code.upper().rstrip("0")
            if not symbol:
                symbol = code.upper()

        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df is None or df.empty:
                return None

            # Normalize columns (akshare returns: date, open, high, low, close, volume, hold, settle)
            col_map = {
                "date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }

            # Rename available columns
            for old, new in col_map.items():
                if old in df.columns and new not in df.columns:
                    df = df.rename(columns={old: new})

            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date").sort_index()

            # Filter to date range
            df = df.loc[start_date:end_date]

            # Ensure volume is numeric
            if "volume" in df.columns:
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

            return df[["open", "high", "low", "close", "volume"]]

        except Exception as e:
            logger.warning("CN futures fetch failed for %s: %s", code, e)
            return None

    @staticmethod
    def _normalize(df: pd.DataFrame, date_col: str = "日期") -> pd.DataFrame:
        """Normalize AKShare DataFrame to standard OHLCV schema.

        AKShare Chinese column names: 日期, 开盘, 最高, 最低, 收盘, 成交量
        AKShare English column names: date, open, high, low, close, volume
        """
        col_map_cn = {"开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"}
        col_map_en = {"date": "trade_date", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}

        if date_col in df.columns:
            df = df.rename(columns={date_col: "trade_date"})
        elif "date" in df.columns:
            df = df.rename(columns={"date": "trade_date"})

        # Try Chinese column names first, then English
        if "开盘" in df.columns:
            df = df.rename(columns=col_map_cn)
        else:
            df = df.rename(columns=col_map_en)

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date").sort_index()

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        ohlcv_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[ohlcv_cols].dropna(subset=["open", "high", "low", "close"])
        if "volume" not in df.columns:
            df["volume"] = 0.0
        return df
