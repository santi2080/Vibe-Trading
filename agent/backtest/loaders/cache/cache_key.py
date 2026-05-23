"""Cache key generation for Vibe-Trading data cache

Generates unique hash keys for caching data requests based on:
- Symbol (e.g., 'BTC-USDT', 'rb0', 'AAPL')
- Timeframe (e.g., '1h', '1d', '1w')
- Time range (start_date, end_date)
- Optional fields (e.g., ['open', 'high', 'low', 'close', 'volume'])
- Optional expression (e.g., 'ts_mean(close, 20)', 'EMA(close, 50)')

Expression Cache Support:
    When expression is provided, the cache key represents a computed result
    rather than raw data. This enables caching of indicator calculations,
    feature engineering results, and other derived data.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class CacheKey:
    """Cache key for uniquely identifying a data request

    Attributes:
        symbol: Security symbol (e.g., 'BTC-USDT', 'rb0', 'AAPL')
        timeframe: Time interval (e.g., '1h', '1d', '1w')
        start_time: Start datetime
        end_time: End datetime
        fields: Optional list of fields (e.g., ['open', 'high', 'low', 'close', 'volume'])
        expression: Optional expression for computed results (e.g., 'ts_mean(close, 20)')
    """

    symbol: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    fields: List[str] = field(default_factory=list)
    expression: Optional[str] = None

    def to_hash(self) -> str:
        """Generate SHA256 hash for this cache key

        Returns:
            16-character hash string suitable for filenames
        """
        # Normalize content for consistent hashing
        content = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "fields": sorted(self.fields) if self.fields else [],
            "expression": self.expression or "",  # Include expression in hash
        }

        # Generate hash
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Convert to dictionary for metadata storage

        Returns:
            Dictionary representation of the cache key
        """
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "fields": self.fields,
            "expression": self.expression,  # Include expression in metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CacheKey':
        """Create CacheKey from dictionary

        Args:
            data: Dictionary with cache key data

        Returns:
            CacheKey instance
        """
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            fields=data.get("fields", []),
            expression=data.get("expression"),  # Support expression field
        )

    def __str__(self) -> str:
        """Human-readable string representation"""
        return f"CacheKey({self.symbol}, {self.timeframe}, {self.start_time.date()} to {self.end_time.date()})"
