"""Data loaders for backtesting

This module provides a unified interface for data loading with:
- Multiple data source loaders with automatic fallback
- Three-level caching (memory, disk, API)
- Data quality validation
- Incremental updates

Usage:
    # Using registry with fallback chains
    from agent.backtest.loaders import resolve_loader, FALLBACK_CHAINS

    loader = resolve_loader("us_equity")
    df = loader.fetch(["AAPL.US"], "2024-01-01", "2024-12-31")

    # Using enhanced cached loader
    from agent.backtest.loaders import EnhancedCachedLoader

    loader = EnhancedCachedLoader(market="us_equity")
    df = loader.load("AAPL.US", "1D")

    # Using unified client
    from agent.backtest.loaders import DataClient, get_client

    client = DataClient(market="us_equity")
    df = client.load("AAPL.US", "1D")

    # Using HybridDataFetcher (recommended)
    from agent.backtest.loaders import HybridDataFetcher

    fetcher = HybridDataFetcher()
    result = fetcher.fetch(["600519.SH", "AAPL.US"], "2024-01-01", "2024-12-31")
"""

from .base import DataLoaderProtocol, NoAvailableSourceError
from .cached_loader import CachedDataLoader
from .client import DataClient, get_client, reset_client
from .enhanced_loader import EnhancedCachedLoader
from .hybrid_fetcher import HybridDataFetcher, get_fetcher
from .registry import (
    register,
    resolve_loader,
    get_loader_cls_with_fallback,
    LOADER_REGISTRY,
    FALLBACK_CHAINS,
)

# Lazy import loaders to avoid import errors when dependencies are missing
# Use ensure_loaders() to trigger all @register decorators
_loaders_ensured = False


def ensure_loaders():
    """Ensure all loaders are imported and registered."""
    global _loaders_ensured
    if _loaders_ensured:
        return

    _loaders_ensured = True

    # Import loaders with optional dependencies
    _loader_modules = [
        ("tushare", "agent.backtest.loaders.tushare"),
        ("okx", "agent.backtest.loaders.okx"),
        ("yfinance_loader", "agent.backtest.loaders.yfinance_loader"),
        ("akshare_loader", "agent.backtest.loaders.akshare_loader"),
        ("ccxt_loader", "agent.backtest.loaders.ccxt_loader"),
        ("futu", "agent.backtest.loaders.futu"),
    ]

    import importlib
    for name, module in _loader_modules:
        try:
            importlib.import_module(module)
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Loader {name} not available: {e}")


# Don't auto-import loaders to avoid import errors
# Call ensure_loaders() when needed

__all__ = [
    # protocols and base
    "DataLoaderProtocol",
    "NoAvailableSourceError",
    # Core classes
    "CachedDataLoader",
    "EnhancedCachedLoader",
    "DataClient",
    "get_client",
    "reset_client",
    # Hybrid Data Fetcher
    "HybridDataFetcher",
    "get_fetcher",
    # Registry utilities
    "register",
    "resolve_loader",
    "get_loader_cls_with_fallback",
    "LOADER_REGISTRY",
    "FALLBACK_CHAINS",
    "ensure_loaders",
]
