"""Watchlist analysis tools for the agent registry."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agent.tools import BaseTool
from src.data.watchlist_data_health import check_watchlist_data


def _to_plain_json(value: Any) -> Any:
    """Convert nested values to JSON-safe plain Python types."""
    if isinstance(value, dict):
        return {str(k): _to_plain_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain_json(v) for v in value]
    if isinstance(value, tuple):
        return [_to_plain_json(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _to_plain_json(value.item())
        except Exception:
            return str(value)
    return value


_AGENT_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _AGENT_DIR.parent
_WATCHLIST_DIR = _REPO_DIR / "watchlist"
_DATA_DIR = _REPO_DIR / "data"


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


def _parse_iso_now(now_value: Any) -> datetime | None:
    if now_value in (None, ""):
        return None
    if not isinstance(now_value, str):
        raise ValueError("now must be an ISO-8601 string")
    try:
        return datetime.fromisoformat(now_value)
    except ValueError as exc:
        raise ValueError(f"Invalid now timestamp: {now_value}") from exc




def _build_watchlist_data_health_payload(path: Path, now: datetime | None = None) -> dict[str, Any]:
    report = check_watchlist_data(watchlist_path=path, data_dir=_DATA_DIR, now=now)
    return _to_plain_json(report.to_dict())


def _filter_data_health_payload_by_market(
    payload: dict[str, Any], market_filter: str | None = None
) -> dict[str, Any]:
    """Limit gate evaluation to the requested market subset when provided."""
    if not market_filter:
        return payload

    normalized_filter = market_filter.upper()
    filtered_items = [
        item for item in payload["items"] if str(item.get("market", "")).upper() == normalized_filter
    ]
    blocking_failures = sum(1 for item in filtered_items if item.get("status") == "FAIL")
    warnings = sum(1 for item in filtered_items if item.get("status") == "WARN")
    can_backtest = blocking_failures == 0
    if blocking_failures:
        gate_status = "FAIL"
    elif warnings:
        gate_status = "WARN"
    else:
        gate_status = "PASS"

    filtered_payload = dict(payload)
    filtered_payload["items"] = filtered_items
    filtered_payload["gate"] = {
        **payload["gate"],
        "empty_watchlist": False,
        "status": gate_status,
        "can_backtest": can_backtest,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "total_checks": len(filtered_items),
    }
    return filtered_payload


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


class CheckWatchlistDataTool(BaseTool):
    """Expose the watchlist local parquet data-health gate as JSON."""

    name = "check_watchlist_data"
    description = "Check standard local parquet data health for a watchlist before analysis or backtesting."
    parameters = {
        "type": "object",
        "properties": {
            "watchlist_path": {
                "type": "string",
                "description": "Path to watchlist CSV, defaults to watchlist/us_futures_watchlist.csv.",
            },
            "now": {
                "type": "string",
                "description": "Optional ISO timestamp used for deterministic data-health checks.",
            },
        },
        "required": [],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        watchlist_path = kwargs.get("watchlist_path", "watchlist/us_futures_watchlist.csv")
        try:
            path = _resolve_watchlist_path(watchlist_path)
        except ValueError as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
        if not path.exists():
            return json.dumps({"status": "error", "error": f"Watchlist not found: {watchlist_path}"}, ensure_ascii=False)

        try:
            now = _parse_iso_now(kwargs.get("now"))
        except ValueError as exc:
            return json.dumps(
                {"status": "error", "error_type": "validation", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )

        payload = _build_watchlist_data_health_payload(path, now=now)
        return json.dumps({"status": "ok", **payload}, ensure_ascii=False, indent=2)


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

        data_health_gate = _filter_data_health_payload_by_market(
            _build_watchlist_data_health_payload(path),
            kwargs.get("market_filter") or None,
        )
        if not data_health_gate["gate"]["can_backtest"]:
            return json.dumps(
                {
                    "status": "error",
                    "error_type": "data_health_gate_blocked",
                    "message": "Watchlist data health blocked analysis execution",
                    "watchlist": data_health_gate["watchlist"],
                    "gate": data_health_gate["gate"],
                    "rules": data_health_gate["rules"],
                    "items": data_health_gate["items"],
                },
                ensure_ascii=False,
                indent=2,
            )

        analyzer = WatchlistAnalyzer(watchlist_path=str(path))
        results = analyzer.analyze_all(
            watchlist_path=str(path),
            market_filter=kwargs.get("market_filter") or None,
            verbose=False,
        )

        if kwargs.get("format", "summary") == "full":
            return json.dumps(
                {
                    "status": "ok",
                    "watchlist": str(path),
                    "count": len(results),
                    "data_health_gate": data_health_gate,
                    "results": [r.__dict__ for r in results],
                },
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
                "asset_class": _to_plain_json(r.mtes.get("asset_class") if r.mtes else None),
                "trend_score": _to_plain_json(r.mtes.get("trend_score") if r.mtes else None),
                "trend_state": _to_plain_json(r.mtes.get("trend_state") if r.mtes else None),
                "direction": _to_plain_json(r.mtes.get("direction") if r.mtes else None),
                "confidence": _to_plain_json(r.mtes.get("confidence") if r.mtes else None),
                "regime": _to_plain_json(r.mtes.get("regime") if r.mtes else None),
                "sub_scores": _to_plain_json(r.mtes.get("sub_scores") if r.mtes else {}),
                "top_drivers": _to_plain_json(r.mtes.get("top_drivers") if r.mtes else []),
            }
            for r in results
            if not r.error
        ]
        return json.dumps(
            {
                "status": "ok",
                "watchlist": str(path),
                "data_health_gate": data_health_gate,
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
