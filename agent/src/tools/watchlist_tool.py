"""Watchlist analysis tools for the agent registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agent.tools import BaseTool


_AGENT_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _AGENT_DIR.parent
_WATCHLIST_DIR = _REPO_DIR / "watchlist"


def _resolve_watchlist_path(watchlist_path: str) -> Path:
    raw_path = Path(watchlist_path).expanduser()
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    elif raw_path.parts and raw_path.parts[0] == "watchlist":
        candidate = (_REPO_DIR / raw_path).resolve()
    else:
        candidate = (_WATCHLIST_DIR / raw_path).resolve()

    watchlist_root = _WATCHLIST_DIR.resolve()
    try:
        candidate.relative_to(watchlist_root)
    except ValueError as exc:
        raise ValueError(f"Watchlist path {watchlist_path!r} escapes the watchlist directory") from exc

    return candidate


class ListWatchlistTool(BaseTool):
    """List configured securities from a watchlist CSV."""

    name = "list_watchlist"
    description = "List securities in a watchlist CSV with symbol, market, exchange, sector, timeframes, and ATR metadata."
    parameters = {
        "type": "object",
        "properties": {
            "watchlist_path": {
                "type": "string",
                "description": "Path to watchlist CSV, defaults to watchlist/us_futures_watchlist.csv.",
            },
        },
        "required": [],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        from src.data.watchlist import WatchlistReader

        watchlist_path = kwargs.get("watchlist_path", "watchlist/us_futures_watchlist.csv")
        try:
            path = _resolve_watchlist_path(watchlist_path)
        except ValueError as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
        if not path.exists():
            return json.dumps({"status": "error", "error": f"Watchlist not found: {watchlist_path}"}, ensure_ascii=False)

        items = WatchlistReader(str(path)).load_raw()
        return json.dumps(
            {"status": "ok", "watchlist": str(path), "count": len(items), "securities": items},
            ensure_ascii=False,
            indent=2,
        )


class AnalyzeSecurityTool(BaseTool):
    """Analyze one security from a watchlist-compatible data source."""

    name = "analyze_security"
    description = "Analyze one security's trend, pullback status, signal direction, price, stop loss, and ATR."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Security symbol, e.g. GC=F."},
            "market": {"type": "string", "description": "Market type, e.g. us_futures."},
            "primary_tf": {"type": "string", "description": "Primary timeframe, defaults to 1D."},
            "watchlist_path": {"type": "string", "description": "Watchlist CSV path."},
        },
        "required": ["symbol"],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        from src.analysis.watchlist_analyzer import WatchlistAnalyzer

        try:
            path = _resolve_watchlist_path(kwargs.get("watchlist_path", "watchlist/us_futures_watchlist.csv"))
        except ValueError as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
        analyzer = WatchlistAnalyzer(watchlist_path=str(path))
        result = analyzer.analyze_single(
            symbol=kwargs["symbol"],
            market=kwargs.get("market", "us_futures"),
            primary_tf=kwargs.get("primary_tf", "1D"),
        )
        return json.dumps(
            {"status": "ok" if not result.error else "error", "result": result.__dict__},
            ensure_ascii=False,
            indent=2,
        )


class AnalyzeWatchlistTool(BaseTool):
    """Batch analyze all securities in a watchlist."""

    name = "analyze_watchlist"
    description = "Analyze all securities in a watchlist and return trend, signal, and summary information."
    parameters = {
        "type": "object",
        "properties": {
            "watchlist_path": {"type": "string", "description": "Watchlist CSV path."},
            "market_filter": {"type": "string", "description": "Optional market filter such as US_FUTURES."},
            "format": {"type": "string", "description": "summary or full."},
        },
        "required": [],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        from src.analysis.report_generator import ReportGenerator
        from src.analysis.watchlist_analyzer import WatchlistAnalyzer

        watchlist_path = kwargs.get("watchlist_path", "watchlist/us_futures_watchlist.csv")
        try:
            path = _resolve_watchlist_path(watchlist_path)
        except ValueError as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
        if not path.exists():
            return json.dumps({"status": "error", "error": f"Watchlist not found: {watchlist_path}"}, ensure_ascii=False)

        analyzer = WatchlistAnalyzer(watchlist_path=str(path))
        results = analyzer.analyze_all(
            watchlist_path=str(path),
            market_filter=kwargs.get("market_filter") or None,
            verbose=False,
        )

        if kwargs.get("format", "summary") == "full":
            return json.dumps(
                {"status": "ok", "watchlist": str(path), "count": len(results), "results": [r.__dict__ for r in results]},
                ensure_ascii=False,
                indent=2,
            )

        summary = ReportGenerator().generate_summary(results)
        valid_signals = [
            {
                "symbol": r.symbol,
                "name": r.name,
                "direction": r.signal_direction,
                "trend": r.trend,
                "price": r.signal_price,
                "stop_loss": r.stop_loss,
                "atr": r.atr_1n,
                "confidence": r.confidence,
            }
            for r in results
            if not r.error and r.signal_direction in ("LONG", "SHORT")
        ]
        mtes_results = [
            {
                "symbol": r.symbol,
                "asset_class": r.mtes.get("asset_class") if r.mtes else None,
                "trend_score": r.mtes.get("trend_score") if r.mtes else None,
                "trend_state": r.mtes.get("trend_state") if r.mtes else None,
                "direction": r.mtes.get("direction") if r.mtes else None,
                "confidence": r.mtes.get("confidence") if r.mtes else None,
                "regime": r.mtes.get("regime") if r.mtes else None,
                "sub_scores": r.mtes.get("sub_scores") if r.mtes else {},
                "top_drivers": r.mtes.get("top_drivers") if r.mtes else [],
            }
            for r in results
            if not r.error
        ]
        return json.dumps(
            {
                "status": "ok",
                "watchlist": str(path),
                "total": summary["total"],
                "success": summary["success"],
                "trends": summary["trends"],
                "signals": summary["signals"],
                "valid_signals": valid_signals,
                "mtes": mtes_results,
            },
            ensure_ascii=False,
            indent=2,
        )
