"""Data caching system for Vibe-Trading

Three-level cache architecture inspired by Qlib:
1. L1: Memory cache (LRU, fast)
2. L2: Disk cache (Parquet, persistent)
3. L3: Raw data cache (original data files)

Usage:
    from agent.backtest.loaders.cache import DataCache

    cache = DataCache()

    # Try to get cached data
    df = cache.get(symbol='BTC-USDT', timeframe='1h', start='2024-01-01', end='2024-12-31')

    # Save data to cache
    cache.set(symbol='BTC-USDT', timeframe='1h', start='2024-01-01', end='2024-12-31', data=df)
"""

from .cache_key import CacheKey
from .memory_cache import MemoryCache
from .disk_cache import DiskCache
from .data_cache import DataCache

__all__ = [
    'CacheKey',
    'MemoryCache',
    'DiskCache',
    'DataCache',
]
