"""China Futures Trading Sessions - Trading hours and session filtering.

China futures markets have specific trading sessions:
- Day session (日盘): 9:00-10:15, 10:30-11:30, 13:30-15:00
- Night session (夜盘): 21:00-23:00 (next day morning delivery)

Common symbols:
- RB: Steel rebar futures
- HC: Hot rolled coil
- IF: CSI 300 Index futures
- IC: CSI 500 Index futures
- IM: CSI 1000 Index futures
- T: 10-year Treasury Bond futures
- TF: 5-year Treasury Bond futures

Usage:
    from agent.backtest.strategies.sessions import ChinaFuturesSession

    session = ChinaFuturesSession()
    df = session.filter_trading_hours(df)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd


class TradingSessionType(Enum):
    """Trading session types."""

    DAY = "day"  # Day session (日盘)
    NIGHT = "night"  # Night session (夜盘)
    CONTINUOUS = "continuous"  # 24/7 markets (crypto)


@dataclass
class TradingSession:
    """A single trading session time range."""

    start_time: time
    end_time: time
    session_type: TradingSessionType


class ChinaFuturesSessions:
    """China futures trading sessions configuration.

    Trading hours (Beijing time, UTC+8):
    - Day session (日盘): 9:00-10:15, 10:30-11:30, 13:30-15:00
    - Night session (夜盘): 21:00-23:00 (previous day)
    """

    # Day session time slots
    DAY_SLOTS = [
        (time(9, 0), time(10, 15)),   # 9:00-10:15
        (time(10, 30), time(11, 30)),  # 10:30-11:30
        (time(13, 30), time(15, 0)),  # 13:30-15:00
    ]

    # Night session time slots
    NIGHT_SLOTS = [
        (time(21, 0), time(23, 0)),  # 21:00-23:00
    ]

    # Combined all slots
    ALL_SLOTS = DAY_SLOTS + NIGHT_SLOTS

    # Exchange closed periods (lunch break, etc.)
    CLOSED_PERIODS = [
        (time(10, 15), time(10, 30)),  # Morning break
        (time(11, 30), time(13, 30)),  # Lunch break
        (time(23, 0), time(9, 0)),    # Night closed (crosses midnight)
    ]

    @classmethod
    def is_trading_time(cls, dt: pd.Timestamp) -> bool:
        """Check if a given timestamp is within trading hours.

        Args:
            dt: Timestamp to check (should be in Beijing time)

        Returns:
            True if within trading hours
        """
        t = dt.time()

        for start, end in cls.ALL_SLOTS:
            if start <= t < end:
                return True

        return False

    @classmethod
    def filter_trading_hours(
        cls, df: pd.DataFrame, tz: str = "Asia/Shanghai"
    ) -> pd.DataFrame:
        """Filter DataFrame to only include trading hours.

        Args:
            df: DataFrame with DatetimeIndex
            tz: Timezone for the timestamps

        Returns:
            Filtered DataFrame
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            return df

        # Convert to Beijing time if needed
        idx = df.index
        if idx.tz is None:
            idx = idx.tz_localize(tz)

        # Create mask
        mask = idx.to_series().apply(cls.is_trading_time)

        return df.loc[mask]

    @classmethod
    def get_session_type(cls, dt: pd.Timestamp) -> TradingSessionType:
        """Get the session type for a timestamp.

        Args:
            dt: Timestamp to check

        Returns:
            Session type (DAY, NIGHT, or CONTINUOUS)
        """
        t = dt.time()

        # Check day session
        for start, end in cls.DAY_SLOTS:
            if start <= t < end:
                return TradingSessionType.DAY

        # Check night session
        for start, end in cls.NIGHT_SLOTS:
            if start <= t < end:
                return TradingSessionType.NIGHT

        return TradingSessionType.CONTINUOUS


class USFuturesSessions:
    """US futures trading sessions.

    Regular trading hours (Chicago time):
    - Equities (ES, NQ): 8:30-15:00 CT
    - Crude Oil (CL): 8:00-14:30 CT
    - Gold (GC): 7:00-14:30 CT
    - Treasury (ZN): 7:00-14:00 CT

    Electronic hours (GLOBEX):
    - Equities: 17:00-8:30 CT (next day)
    - Energy: 17:00-8:30 CT
    """

    # Regular trading hours (CT, i.e., Chicago time)
    REGULAR_HOURS = [
        (time(8, 30), time(15, 0)),   # Equities (ES, NQ)
    ]

    # Electronic hours (extends beyond regular)
    ELECTRONIC_HOURS = [
        (time(17, 0), time(8, 30)),  # Crosses midnight
    ]

    @classmethod
    def is_trading_time(cls, dt: pd.Timestamp, market: str = "equity") -> bool:
        """Check if a given timestamp is within trading hours.

        Args:
            dt: Timestamp to check
            market: Market type (equity, energy, metal)

        Returns:
            True if within trading hours
        """
        t = dt.time()

        if market == "equity":
            slots = cls.REGULAR_HOURS + [cls.ELECTRONIC_HOURS[0]]
        else:
            slots = cls.REGULAR_HOURS

        for start, end in slots:
            # Handle overnight sessions (crosses midnight)
            if end < start:
                if t >= start or t < end:
                    return True
            else:
                if start <= t < end:
                    return True

        return False


class CryptoSessions:
    """Cryptocurrency 24/7 trading sessions."""

    @staticmethod
    def is_trading_time(dt: pd.Timestamp) -> bool:
        """Crypto trades 24/7.

        Args:
            dt: Timestamp to check

        Returns:
            Always True for crypto
        """
        return True


class SessionManager:
    """Unified session manager for multiple markets."""

    SESSION_CONFIGS = {
        "china_futures": ChinaFuturesSessions,
        "us_futures": USFuturesSessions,
        "crypto": CryptoSessions,
    }

    @classmethod
    def get_session(cls, market: str) -> type:
        """Get session class for a market.

        Args:
            market: Market identifier

        Returns:
            Session class with is_trading_time method
        """
        return cls.SESSION_CONFIGS.get(market, CryptoSessions)

    @classmethod
    def is_trading_time(cls, dt: pd.Timestamp, market: str = "crypto") -> bool:
        """Check if a given timestamp is within trading hours.

        Args:
            dt: Timestamp to check
            market: Market type

        Returns:
            True if within trading hours
        """
        session_class = cls.get_session(market)
        return session_class.is_trading_time(dt)

    @classmethod
    def filter_by_session(
        cls,
        df: pd.DataFrame,
        market: str = "crypto",
    ) -> pd.DataFrame:
        """Filter DataFrame by trading session.

        Args:
            df: DataFrame with DatetimeIndex
            market: Market type

        Returns:
            Filtered DataFrame
        """
        if market == "crypto":
            return df  # No filtering needed

        session_class = cls.get_session(market)

        if hasattr(session_class, "filter_trading_hours"):
            return session_class.filter_trading_hours(df)

        # Fallback: use is_trading_time
        if not isinstance(df.index, pd.DatetimeIndex):
            return df

        mask = df.index.to_series().apply(session_class.is_trading_time)
        return df.loc[mask]

    @classmethod
    def add_session_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Add session-related columns to DataFrame.

        Args:
            df: DataFrame with DatetimeIndex

        Returns:
            DataFrame with session columns added
        """
        result = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            return result

        # Session type
        result["session_type"] = df.index.to_series().apply(
            lambda x: cls.get_session_type(x).value
        )

        # Is trading hour
        result["is_trading"] = df.index.to_series().apply(
            lambda x: cls.is_trading_time(x)
        )

        return result

    @classmethod
    def get_session_type(cls, dt: pd.Timestamp) -> TradingSessionType:
        """Get session type for a timestamp.

        Args:
            dt: Timestamp to check

        Returns:
            Session type
        """
        return ChinaFuturesSessions.get_session_type(dt)
