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

from __future__ import annotations

import importlib
import logging
import sys
from typing import Any

sys.modules["agent.backtest.loaders"] = sys.modules[__name__]
sys.modules["backtest.loaders"] = sys.modules[__name__]

from .base import DataLoaderProtocol, NoAvailableSourceError
from .registry import (
    FALLBACK_CHAINS,
    LOADER_REGISTRY,
    get_loader_cls_with_fallback,
    register,
    resolve_loader,
)

logger = logging.getLogger(__name__)

# Lazy import loaders to avoid import errors when dependencies are missing.
# Use ensure_loaders() to trigger all @register decorators.
_loaders_ensured = False

_LOADER_MODULES = [
    ("tushare", "agent.backtest.loaders.tushare"),
    ("tqsdk_loader", "agent.backtest.loaders.tqsdk_loader"),
    ("okx", "agent.backtest.loaders.okx"),
    ("yfinance_loader", "agent.backtest.loaders.yfinance_loader"),
    ("akshare_loader", "agent.backtest.loaders.akshare_loader"),
    ("ccxt_loader", "agent.backtest.loaders.ccxt_loader"),
    ("futu", "agent.backtest.loaders.futu"),
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "CachedDataLoader": ("cached_loader", "CachedDataLoader"),
    "EnhancedCachedLoader": ("enhanced_loader", "EnhancedCachedLoader"),
    "DataClient": ("client", "DataClient"),
    "get_client": ("client", "get_client"),
    "reset_client": ("client", "reset_client"),
    "HybridDataFetcher": ("hybrid_fetcher", "HybridDataFetcher"),
    "get_fetcher": ("hybrid_fetcher", "get_fetcher"),
}


def ensure_loaders() -> None:
    """Ensure all loaders are imported and registered."""
    global _loaders_ensured
    if _loaders_ensured:
        return

    _loaders_ensured = True

    for name, module in _LOADER_MODULES:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            logger.debug("Loader %s not available: %s", name, exc)


def __getattr__(name: str) -> Any:
    """Lazily expose heavy loader helpers without importing them at package load."""
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = importlib.import_module(f"{__name__}.{module_name}")
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
