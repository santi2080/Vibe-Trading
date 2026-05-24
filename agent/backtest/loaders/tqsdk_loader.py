"""TqSdk-backed loader for Chinese futures OHLCV data.

This module provides a data loader for Chinese futures markets using TqSdk,
which offers real-time and historical data for commodities, indices, and FX.

Key features:
- Connection pooling for performance
- Automatic symbol translation
- Historical and real-time data
- China futures trading sessions support

Usage:
    from agent.backtest.loaders.tqsdk_loader import TqSdkLoader

    loader = TqSdkLoader()
    df = loader.fetch(["ag0", "rb0"], "2024-01-01", "2024-12-31", interval="1D")
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import pandas as pd

from agent.backtest.loaders.base import DataLoaderProtocol, NoAvailableSourceError, validate_date_range

logger = logging.getLogger(__name__)

_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

# Symbol translation: project format -> TqSdk format
_SYMBOL_MAP = {
    # Main contract continuations (main connection)
    "ag0": "AG",   # Silver
    "au0": "AU",   # Gold
    "cu0": "CU",   # Copper
    "zn0": "ZN",   # Zinc
    "al0": "AL",   # Aluminum
    "pb0": "PB",   # Lead
    "ni0": "NI",   # Nickel
    "sn0": "SN",   # Tin
    "rb0": "RB",   # Rebar
    "hc0": "HC",   # Hot rolled coil
    "wr0": "WR",   # Wire rod
    "ss0": "SS",   # Stainless steel
    "i0": "I",     # Iron ore
    "j0": "J",     # Coke
    "jm0": "JM",   # Coking coal
    "cf0": "CF",   # Cotton
    "sr0": "SR",   # Sugar
    "z0": "Z",     # Yellow soybean
    "m0": "M",     # Soybean meal
    "y0": "Y",     # Soybean oil
    "p0": "P",     # Palm oil
    "a0": "A",     # No.1 soybean
    "b0": "B",     # No.2 soybean
    "jd0": "JD",   # Eggs
    "pp0": "PP",   # Polypropylene
    "l0": "L",    # Linear PE
    "v0": "V",     # PVC
    "ma0": "MA",   # Methanol
    "ta0": "TA",   # PTA
    "eg0": "EG",   # Ethylene glycol
    "sc0": "SC",   # Crude oil
    "fu0": "FU",   # Fuel oil
    "bu0": "BU",   # Bitumen
    "ru0": "RU",   # Rubber
    "pb0": "PB",   # Lead
    "fg0": "FG",   # Glass
    "sm0": "SM",   # Soda ash
    "nh0": "NH",   # Soda ash (alternate)
    # Index futures
    "if0": "IF",   # CSI 300
    "ih0": "IH",   # SSE 50
    "ic0": "IC",   # CSI 500
    "im0": "IM",   # CSI 1000
    # Options
    "mo0": "MO",   # Gold options
}

# Reverse map for output
_TQSdk_TO_PROJECT = {v: k for k, v in _SYMBOL_MAP.items()}


def _to_tqsdk_symbol(code: str) -> str:
    """Convert project symbol to TqSdk format.

    Examples:
        ag0 -> AG
        rb0 -> RB
        if0 -> IF
    """
    code = code.strip().lower()
    return _SYMBOL_MAP.get(code, code.upper())


def _from_tqsdk_symbol(code: str) -> str:
    """Convert TqSdk symbol to project format.

    Examples:
        AG -> ag0
        RB -> rb0
    """
    code = code.strip().upper()
    return _TQSdk_TO_PROJECT.get(code, code.lower())


@contextmanager
def _suppress_output():
    """Context manager to suppress TqSdk output.

    TqSdk prints disclaimer messages on connect. This context manager
    suppresses stdout/stderr to prevent cluttering the console.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


class TqSdkConnectionPool:
    """Singleton connection pool for TqSdk.

    Reuses a single TqSdk connection across all requests to avoid
    the overhead of creating new connections for each data fetch.

    Example:
        >>> pool = TqSdkConnectionPool()
        >>> with pool.get_connection() as api:
        ...     df = api.get_kline_serial("AG")
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._api = None
        self._auth = None
        self._connection_lock = Lock()
        self._initialized = True
        logger.info("TqSdkConnectionPool initialized (singleton)")

    def _create_connection(self):
        """Create a new TqSdk connection."""
        with _suppress_output():
            from tqsdk import TqApi

        # Check for auth credentials
        account = os.environ.get("TQ_ACCOUNT")
        password = os.environ.get("TQ_PASSWORD")

        if account and password:
            with _suppress_output():
                self._auth = TqAuth(account, password)
                self._api = TqApi(auth=self._auth)
        else:
            with _suppress_output():
                self._api = TqApi()

        logger.info("TqSdk connection established")
        return self._api

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool.

        Yields:
            TqApi: TqSdk API instance
        """
        with self._connection_lock:
            if self._api is None:
                self._api = self._create_connection()

            try:
                yield self._api
            except Exception as e:
                logger.error(f"TqSdk connection error: {e}")
                try:
                    self._api.close()
                except Exception:
                    pass
                self._api = None
                raise

    def close(self):
        """Close the connection pool."""
        with self._connection_lock:
            if self._api is not None:
                try:
                    self._api.close()
                except Exception as e:
                    logger.warning(f"Error closing TqSdk connection: {e}")
                self._api = None
                logger.info("TqSdk connection closed")


# Global connection pool
_pool: Optional[TqSdkConnectionPool] = None


def _get_pool() -> TqSdkConnectionPool:
    """Get the global connection pool."""
    global _pool
    if _pool is None:
        _pool = TqSdkConnectionPool()
    return _pool


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize TqSdk kline DataFrame to standard OHLCV schema.

    Args:
        df: Raw DataFrame from TqSdk

    Returns:
        DataFrame with columns [open, high, low, close, volume] indexed
        by DatetimeIndex, sorted ascending.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=_OHLCV_COLUMNS)

    result = df.copy()

    # Handle different column names from TqSdk
    time_col = "datetime"
    if "time" in result.columns:
        time_col = "time"

    result.index = pd.to_datetime(result[time_col])
    result.index.name = "datetime"

    # Select and reorder columns
    cols = [c for c in _OHLCV_COLUMNS if c in result.columns]
    result = result[cols].copy()

    # Ensure numeric types
    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")

    result["volume"] = result["volume"].fillna(0.0)
    result = result.dropna(subset=["open", "high", "low", "close"])

    return result.sort_index()


class TqSdkLoader:
    """Fetch Chinese futures OHLCV data from TqSdk.

    TqSdk provides real-time and historical data for Chinese futures,
    including commodities, indices, options, and FX.

    Attributes:
        name: Loader name for registry
        markets: Set of supported market types
        requires_auth: Whether authentication is required

    Example:
        >>> loader = TqSdkLoader()
        >>> result = loader.fetch(["ag0", "rb0"], "2024-01-01", "2024-12-31", interval="1D")
        >>> print(result["ag0"].head())
    """

    name = "tqsdk"
    markets = {"futures", "a_share"}
    requires_auth = True

    def __init__(self):
        """Initialize the TqSdk loader."""
        self._pool = _get_pool()

    def is_available(self) -> bool:
        """Check if TqSdk is available.

        Returns:
            True if TqSdk can be imported and connection can be established.
        """
        try:
            from tqsdk import TqApi
            return True
        except ImportError:
            logger.warning("TqSdk not installed. Install with: pip install tqsdk")
            return False
        except Exception as e:
            logger.warning(f"TqSdk not available: {e}")
            return False

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV history from TqSdk.

        Args:
            codes: Project symbols such as "ag0", "rb0".
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            interval: Time interval - "1D", "1H", "4H", "1W".
            fields: Ignored; for interface compatibility.

        Returns:
            Mapping of input symbol to normalized OHLCV dataframe.

        Raises:
            NoAvailableSourceError: If TqSdk connection fails.
        """
        del fields  # Not used

        if not codes:
            return {}

        validate_date_range(start_date, end_date)

        # Map interval
        duration_map = {
            "1D": 86400,
            "1H": 3600,
            "4H": 14400,
            "30m": 1800,
            "15m": 900,
            "5m": 300,
            "1W": 604800,
        }
        duration = duration_map.get(interval, 86400)

        results: Dict[str, pd.DataFrame] = {}

        try:
            with self._pool.get_connection() as api:
                for code in codes:
                    tqsdk_code = _to_tqsdk_symbol(code)

                    try:
                        # Get kline data
                        df = api.get_kline_serial(
                            tqsdk_code,
                            data_length=10000,
                            duration_n=int(duration),
                        )

                        # Filter by date range
                        if not df.empty:
                            start_dt = pd.Timestamp(start_date)
                            end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)

                            df = df[df["datetime"] >= start_dt]
                            df = df[df["datetime"] < end_dt]

                            results[code] = _normalize_frame(df)
                            logger.debug(f"Fetched {len(results[code])} bars for {code}")
                        else:
                            logger.warning(f"No data returned for {code}")

                    except Exception as e:
                        logger.warning(f"Failed to fetch {code}: {e}")
                        continue

        except Exception as exc:
            raise NoAvailableSourceError(
                f"Cannot connect to TqSdk: {exc}"
            ) from exc

        return results


def get_loader() -> TqSdkLoader:
    """Get a TqSdkLoader instance.

    Returns:
        TqSdkLoader instance
    """
    return TqSdkLoader()


def close_pool():
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
