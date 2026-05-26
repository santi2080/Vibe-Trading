"""Loader registry with market-level fallback chains.

Loaders self-register via the ``@register`` decorator when their module is
first imported.  The ``_ensure_registered()`` helper lazily imports every
known loader module so that callers of ``resolve_loader`` /
``get_loader_cls_with_fallback`` never see an empty registry — regardless
of import order.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Type

from agent.backtest.loaders.base import NoAvailableSourceError

logger = logging.getLogger(__name__)

if __name__ == "agent.backtest.loaders.registry":
    sys.modules.setdefault("backtest.loaders.registry", sys.modules[__name__])
elif __name__ == "backtest.loaders.registry":
    sys.modules.setdefault("agent.backtest.loaders.registry", sys.modules[__name__])

# ---------------------------------------------------------------------------
# Global registry: source_name -> loader class
# ---------------------------------------------------------------------------

LOADER_REGISTRY: dict[str, Type[Any]] = {}

_registered = False


def register(cls: Type[Any]) -> Type[Any]:
    """Class decorator: register a loader into the global registry.

    The class must have a ``name`` class attribute.
    """
    LOADER_REGISTRY[cls.name] = cls
    return cls


def _ensure_registered() -> None:
    """Import every known loader module so ``@register`` decorators fire.

    Safe to call multiple times — only runs the imports once.
    Loaders whose dependencies are missing (e.g. ``akshare`` not installed)
    are silently skipped.
    """
    global _registered
    if _registered:
        return
    _registered = True

    _loader_modules = [
        "agent.backtest.loaders.tushare",
        "agent.backtest.loaders.tqsdk_loader",
        "agent.backtest.loaders.okx",
        "agent.backtest.loaders.yfinance_loader",
        "agent.backtest.loaders.akshare_loader",
        "agent.backtest.loaders.ccxt_loader",
        "agent.backtest.loaders.futu",
    ]
    import importlib
    for mod in _loader_modules:
        try:
            importlib.import_module(mod)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fallback chains: market_type -> ordered list of source names
# ---------------------------------------------------------------------------

FALLBACK_CHAINS: dict[str, list[str]] = {
    "a_share":   ["tushare", "akshare"],
    "us_equity": ["yfinance", "akshare"],
    "hk_equity": ["futu", "yfinance", "akshare"],
    "crypto":    ["okx", "ccxt"],
    "futures":   ["tqsdk", "tushare", "akshare"],  # TqSdk for Chinese futures
    "cn_futures": ["tqsdk", "tushare", "akshare"],  # Alias for Chinese futures

    # US Futures - 按时间周期分离
    # 日线 (1D/W1): akshare 主（直连，不需要代理）
    # 日内 (1H/1m): yfinance 主（需要代理）
    "us_futures_daily": ["akshare", "yfinance"],  # 1D/W1 - akshare 主
    "us_futures_intraday": ["yfinance", "akshare"],  # 1H/1m - yfinance 主

    # 保留兼容性（默认使用 akshare 日线，不需要代理）
    "us_futures": ["akshare", "yfinance"],  # akshare 主，yfinance 备选（需要代理）

    "fund":      ["tushare", "akshare"],
    "macro":     ["akshare", "tushare"],
    "forex":     ["akshare", "yfinance"],
}


def resolve_loader(market: str, enable_cache: bool = True) -> Any:
    """Return the first *available* loader instance for *market*.

    Walks the fallback chain and returns the first loader whose
    ``is_available()`` returns ``True``.

    Args:
        market: Market type key (e.g. ``"a_share"``, ``"crypto"``).
        enable_cache: Whether to wrap the loader with caching (default True).

    Returns:
        A loader instance (optionally wrapped with CachedDataLoader).

    Raises:
        NoAvailableSourceError: If every candidate is unavailable.
    """
    _ensure_registered()
    chain = FALLBACK_CHAINS.get(market, [])
    tried: list[str] = []
    for name in chain:
        if name not in LOADER_REGISTRY:
            continue
        tried.append(name)
        # Issue #50 — some loaders (e.g. Tushare) call into the SDK during
        # __init__ and raise on missing credentials. Treat that the same as
        # is_available()=False so the fallback chain keeps walking.
        try:
            loader = LOADER_REGISTRY[name]()
        except Exception as exc:
            logger.debug("loader %s failed to construct: %s", name, exc)
            continue
        if loader.is_available():
            return _wrap_with_cache(loader, enable_cache)
    raise NoAvailableSourceError(
        f"No available data source for market '{market}'. "
        f"Tried: {tried or chain}. Check network and API token config."
    )


def get_loader_cls_with_fallback(source: str, enable_cache: bool = True) -> Type[Any]:
    """Return a loader *class* for *source*, falling back if unavailable.

    Args:
        source: Requested data source name.
        enable_cache: Whether to wrap the loader with caching (default True).

    Returns:
        A DataLoader class (not instance).

    Raises:
        NoAvailableSourceError: If the source and all fallbacks are unavailable.
    """
    _ensure_registered()
    if source not in LOADER_REGISTRY:
        raise NoAvailableSourceError(f"Unknown data source: {source}")

    loader_cls = LOADER_REGISTRY[source]
    try:
        instance = loader_cls()
    except Exception as exc:
        logger.debug("loader %s failed to construct: %s", source, exc)
        instance = None
    if instance is not None and instance.is_available():
        return loader_cls

    # Source unavailable — try same-market fallback
    for market in loader_cls.markets:
        try:
            fallback = resolve_loader(market, enable_cache=enable_cache)
            logger.warning(
                "%s is unavailable, falling back to %s for market %s",
                source, fallback.name, market,
            )
            return type(fallback)
        except NoAvailableSourceError:
            continue

    raise NoAvailableSourceError(
        f"Data source '{source}' is unavailable and no fallback found."
    )


def _wrap_with_cache(loader: Any, enable_cache: bool) -> Any:
    """Wrap a loader instance with CachedDataLoader if caching is enabled.

    Args:
        loader: The original loader instance.
        enable_cache: Whether to enable caching.

    Returns:
        CachedDataLoader wrapping the original loader, or the original loader if caching is disabled.
    """
    if not enable_cache:
        return loader

    # Check environment variable to allow global cache disable
    if os.getenv("VIBE_DISABLE_CACHE", "").lower() in ("1", "true", "yes"):
        return loader

    try:
        from agent.backtest.loaders.cached_loader import CachedDataLoader
        cache_dir = os.getenv("VIBE_CACHE_DIR", ".cache/data")
        return CachedDataLoader(loader, cache_dir=cache_dir, enable_cache=True)
    except Exception as exc:
        logger.warning("Failed to wrap loader with cache: %s", exc)
        return loader
