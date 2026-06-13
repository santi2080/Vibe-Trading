"""Watchlist local data health checks.

This module checks local parquet data for watchlist symbols before backtesting.
V1 intentionally uses fixed staleness windows instead of exchange calendars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .watchlist import WatchlistReader

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")
BLOCKING_TIMEFRAMES = ("1d", "1h")
AUXILIARY_STALE_AFTER = timedelta(days=7)

STALE_AFTER: dict[str, timedelta] = {
    "1d": timedelta(days=2),
    "1h": timedelta(hours=6),
    "4h": timedelta(hours=12),
}

MARKET_TIMEFRAME_STALE_AFTER: dict[tuple[str, str], timedelta] = {
    ("us_futures", "1h"): timedelta(hours=24),
}

MARKET_DIRS = {
    "us_futures": "us_futures",
    "us_future": "us_futures",
    "cn_futures": "cn_futures",
    "cn_future": "cn_futures",
    "us_etf": "etf",
    "etf": "etf",
    "us_stock": "us_stocks",
    "us_stocks": "us_stocks",
    "hk_stock": "hk_stocks",
    "hk_stocks": "hk_stocks",
}

TIMEFRAME_ALIASES = {
    "d1": "1d",
    "day": "1d",
    "daily": "1d",
    "1day": "1d",
    "h1": "1h",
    "hour": "1h",
    "hourly": "1h",
    "1hour": "1h",
    "h4": "4h",
    "4hour": "4h",
    "w1": "1w",
    "week": "1w",
    "weekly": "1w",
}


@dataclass
class TimeframeDataHealth:
    """Health result for one symbol/timeframe local data file."""

    watchlist: str
    symbol: str
    name: str
    market: str
    timeframe: str
    required: bool
    cache_file: str
    exists: bool
    status: str
    reason: str
    rows: int | None = None
    start: str | None = None
    end: str | None = None
    age_hours: float | None = None
    max_gap_hours: float | None = None
    missing_recent: bool = False
    gap_warning: bool = False
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "watchlist": self.watchlist,
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "timeframe": self.timeframe,
            "required": self.required,
            "cache_file": self.cache_file,
            "exists": self.exists,
            "status": self.status,
            "reason": self.reason,
            "rows": self.rows,
            "start": self.start,
            "end": self.end,
            "age_hours": self.age_hours,
            "max_gap_hours": self.max_gap_hours,
            "missing_recent": self.missing_recent,
            "gap_warning": self.gap_warning,
            "issues": self.issues,
        }


@dataclass
class WatchlistDataHealthReport:
    """Aggregated watchlist data health report."""

    watchlist: str
    checked_at: datetime
    data_dir: str
    items: list[TimeframeDataHealth]
    calendar_adjusted: bool = False

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0

    @property
    def blocking_failures(self) -> int:
        return sum(1 for item in self.items if item.status == "FAIL")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.items if item.status == "WARN")

    @property
    def can_backtest(self) -> bool:
        return not self.is_empty and self.blocking_failures == 0

    @property
    def gate_status(self) -> str:
        if self.is_empty or self.blocking_failures:
            return "FAIL"
        if self.warnings:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "watchlist": self.watchlist,
            "checked_at": self.checked_at.isoformat(),
            "data_dir": self.data_dir,
            "calendar_adjusted": self.calendar_adjusted,
            "gate": {
                "empty_watchlist": self.is_empty,
                "status": self.gate_status,
                "can_backtest": self.can_backtest,
                "blocking_failures": self.blocking_failures,
                "warnings": self.warnings,
                "total_checks": len(self.items),
            },
            "rules": {
                "blocking_timeframes": list(BLOCKING_TIMEFRAMES),
                "staleness_thresholds": {
                    timeframe: format_timedelta(delta)
                    for timeframe, delta in STALE_AFTER.items()
                },
                "market_overrides": {
                    f"{market}:{timeframe}": format_timedelta(delta)
                    for (market, timeframe), delta in MARKET_TIMEFRAME_STALE_AFTER.items()
                },
                "calendar_adjusted": False,
            },
            "items": [item.to_dict() for item in self.items],
        }


def normalize_timeframe(timeframe: str) -> str:
    """Normalize timeframe strings like 1D, D1, 1H, H4 to lower-case canonical form."""
    normalized = timeframe.strip().lower().replace("_", "")
    return TIMEFRAME_ALIASES.get(normalized, normalized)


def parse_timeframes(timeframes: str) -> list[str]:
    """Parse watchlist timeframe field into normalized unique timeframes."""
    raw_parts = timeframes.replace("/", "-").replace("|", "-").split("-")
    parsed: list[str] = []
    for part in raw_parts:
        normalized = normalize_timeframe(part)
        if normalized and normalized not in parsed:
            parsed.append(normalized)
    return parsed or ["1d", "1h"]


def required_and_declared_timeframes(timeframes: str) -> list[str]:
    """Return v1 check set: required 1d/1h plus declared auxiliary timeframes."""
    ordered = ["1d", "1h"]
    for timeframe in parse_timeframes(timeframes):
        if timeframe not in ordered:
            ordered.append(timeframe)
    return ordered


def resolve_market_dir(market: str) -> str:
    """Resolve a watchlist market value to the local data directory name."""
    key = market.strip().lower()
    return MARKET_DIRS.get(key, key)


def resolve_cache_file(data_dir: Path, market: str, symbol: str, timeframe: str) -> Path:
    """Resolve the expected local parquet file path."""
    return data_dir / resolve_market_dir(market) / symbol / f"{normalize_timeframe(timeframe)}.parquet"


def check_watchlist_data(
    watchlist_path: str | Path,
    data_dir: str | Path = "data",
    now: datetime | None = None,
) -> WatchlistDataHealthReport:
    """Check local parquet data for every symbol/timeframe in a watchlist."""
    checked_at = now or datetime.now(timezone.utc)
    data_path = Path(data_dir)
    watchlist = Path(watchlist_path)
    reader = WatchlistReader(str(watchlist))
    items: list[TimeframeDataHealth] = []

    for raw_item in reader.load_raw():
        symbol = raw_item.get("symbol", "").strip()
        if not symbol or symbol.lower() in {"symbol", "code", "name"}:
            continue

        name = raw_item.get("name") or symbol
        market = raw_item.get("market") or "us_futures"
        timeframes = raw_item.get("timeframes") or "1D-1H"

        for timeframe in required_and_declared_timeframes(timeframes):
            cache_file = resolve_cache_file(data_path, market, symbol, timeframe)
            items.append(check_timeframe_data(str(watchlist), symbol, name, market, timeframe, cache_file, checked_at))

    return WatchlistDataHealthReport(
        watchlist=str(watchlist),
        checked_at=checked_at,
        data_dir=str(data_path),
        items=items,
    )


def check_timeframe_data(
    watchlist: str,
    symbol: str,
    name: str,
    market: str,
    timeframe: str,
    cache_file: Path,
    now: datetime,
) -> TimeframeDataHealth:
    """Check one local parquet file."""
    normalized_timeframe = normalize_timeframe(timeframe)
    required = normalized_timeframe in BLOCKING_TIMEFRAMES

    if not cache_file.exists():
        return build_issue_result(
            watchlist,
            symbol,
            name,
            market,
            normalized_timeframe,
            cache_file,
            exists=False,
            required=required,
            reason="missing required file" if required else "missing auxiliary file",
            issues=["file_missing"],
            missing_recent=required,
        )

    df, read_error = read_local_parquet(cache_file)
    if read_error:
        return build_issue_result(
            watchlist,
            symbol,
            name,
            market,
            normalized_timeframe,
            cache_file,
            exists=True,
            required=required,
            reason=f"read failed: {read_error}",
            issues=["read_failed"],
        )

    if df is None or df.empty:
        return build_issue_result(
            watchlist,
            symbol,
            name,
            market,
            normalized_timeframe,
            cache_file,
            exists=True,
            required=required,
            reason="empty data",
            issues=["empty_data"],
            rows=0,
        )

    df = normalize_datetime_index(df)
    if not isinstance(df.index, pd.DatetimeIndex):
        return build_issue_result(
            watchlist,
            symbol,
            name,
            market,
            normalized_timeframe,
            cache_file,
            exists=True,
            required=required,
            reason="missing datetime index",
            issues=["missing_datetime_index"],
            rows=len(df),
        )

    return build_loaded_result(watchlist, symbol, name, market, normalized_timeframe, cache_file, required, df, now)


def read_local_parquet(cache_file: Path) -> tuple[pd.DataFrame | None, str | None]:
    try:
        return pd.read_parquet(cache_file), None
    except Exception as exc:  # pragma: no cover - engine errors vary by environment
        return None, str(exc)


def build_issue_result(
    watchlist: str,
    symbol: str,
    name: str,
    market: str,
    timeframe: str,
    cache_file: Path,
    *,
    exists: bool,
    required: bool,
    reason: str,
    issues: list[str],
    rows: int | None = None,
    missing_recent: bool = False,
) -> TimeframeDataHealth:
    return TimeframeDataHealth(
        watchlist=watchlist,
        symbol=symbol,
        name=name,
        market=market,
        timeframe=timeframe,
        required=required,
        cache_file=str(cache_file),
        exists=exists,
        status="FAIL" if required else "WARN",
        reason=reason,
        rows=rows,
        missing_recent=missing_recent,
        issues=issues,
    )


def build_loaded_result(
    watchlist: str,
    symbol: str,
    name: str,
    market: str,
    timeframe: str,
    cache_file: Path,
    required: bool,
    df: pd.DataFrame,
    now: datetime,
) -> TimeframeDataHealth:
    df = df.sort_index()
    # Normalize timestamps: parquet index may be tz-aware or tz-naive
    end_ts = pd.Timestamp(df.index.max())
    if end_ts.tzinfo is not None:
        end_ts = end_ts.tz_convert("UTC").tz_localize(None)
    start_ts = pd.Timestamp(df.index.min())
    if start_ts.tzinfo is not None:
        start_ts = start_ts.tz_convert("UTC").tz_localize(None)
    # Normalize now to UTC naive for comparison
    now_for_calc = now
    if hasattr(now_for_calc, "tzinfo") and now_for_calc.tzinfo is not None:
        now_utc = now_for_calc.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        now_utc = now_for_calc
    age_hours = max((now_utc - end_ts.to_pydatetime()).total_seconds() / 3600, 0.0)
    max_gap_hours = calculate_max_gap_hours(df.index)
    status_issues = health_issues(df, market, timeframe, age_hours, max_gap_hours)
    status = status_for(status_issues, required)

    return TimeframeDataHealth(
        watchlist=watchlist,
        symbol=symbol,
        name=name,
        market=market,
        timeframe=timeframe,
        required=required,
        cache_file=str(cache_file),
        exists=True,
        status=status,
        reason=reason_for(status_issues),
        rows=len(df),
        start=format_datetime(start_ts),
        end=format_datetime(end_ts),
        age_hours=round(age_hours, 2),
        max_gap_hours=round(max_gap_hours, 2) if max_gap_hours is not None else None,
        missing_recent="stale_data" in status_issues,
        gap_warning="large_gap" in status_issues,
        issues=status_issues,
    )


def health_issues(
    df: pd.DataFrame,
    market: str,
    timeframe: str,
    age_hours: float,
    max_gap_hours: float | None,
) -> list[str]:
    issues = validate_ohlcv(df)
    stale_after = stale_after_for(market, timeframe)
    if age_hours > stale_after.total_seconds() / 3600:
        issues.append("stale_data")
    if has_gap_warning(timeframe, max_gap_hours):
        issues.append("large_gap")
    return unique(issues)


def status_for(issues: list[str], required: bool) -> str:
    if not issues:
        return "PASS"
    if required and any(issue != "large_gap" for issue in issues):
        return "FAIL"
    return "WARN"


def reason_for(issues: list[str]) -> str:
    if "missing_required_columns" in issues:
        return "missing required columns"
    if "invalid_ohlc" in issues:
        return "invalid OHLC values"
    if "invalid_volume" in issues:
        return "invalid volume values"
    if "missing_values" in issues:
        return "missing OHLCV values"
    if "stale_data" in issues:
        return "recent data missing"
    if "large_gap" in issues:
        return "large internal gap"
    return "ok"



def normalize_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with a DatetimeIndex if possible."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df
    if "timestamp" in df.columns:
        normalized = df.copy()
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"])
        return normalized.set_index("timestamp")
    if "datetime" in df.columns:
        normalized = df.copy()
        normalized["datetime"] = pd.to_datetime(normalized["datetime"])
        return normalized.set_index("datetime")
    return df


def validate_ohlcv(df: pd.DataFrame) -> list[str]:
    """Validate required OHLCV fields."""
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        return ["missing_required_columns"]

    issues: list[str] = []
    if df[list(REQUIRED_COLUMNS)].isna().any(axis=None):
        issues.append("missing_values")

    price_columns = ["open", "high", "low", "close"]
    if (df[price_columns] <= 0).any(axis=None):
        issues.append("invalid_ohlc")
    if ((df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"])).any(axis=None):
        issues.append("invalid_ohlc")
    if ((df["low"] > df["open"]) | (df["low"] > df["close"])).any(axis=None):
        issues.append("invalid_ohlc")
    if (df["volume"] < 0).any(axis=None):
        issues.append("invalid_volume")

    return unique(issues)


def stale_after_for(market: str, timeframe: str) -> timedelta:
    normalized_market = resolve_market_dir(market)
    normalized_timeframe = normalize_timeframe(timeframe)
    override = MARKET_TIMEFRAME_STALE_AFTER.get((normalized_market, normalized_timeframe))
    if override is not None:
        return override
    return STALE_AFTER.get(normalized_timeframe, AUXILIARY_STALE_AFTER)


def calculate_max_gap_hours(index: pd.DatetimeIndex) -> float | None:
    if len(index) < 2:
        return None
    gaps = index.to_series().sort_values().diff().dropna()
    if gaps.empty:
        return None
    return gaps.max().total_seconds() / 3600


def has_gap_warning(timeframe: str, max_gap_hours: float | None) -> bool:
    if max_gap_hours is None:
        return False
    thresholds = {
        "1d": 7 * 24,
        "1h": 48,
        "4h": 72,
    }
    return max_gap_hours > thresholds.get(normalize_timeframe(timeframe), 7 * 24)


def format_report_table(report: WatchlistDataHealthReport) -> str:
    """Format a readable fixed-width table."""
    lines = [
        f"Watchlist Data Health: {report.watchlist}",
        f"Gate: {report.gate_status} — {report.blocking_failures} blocking issue(s), {report.warnings} warning(s)",
        f"Data dir: {report.data_dir}",
        "",
    ]
    headers = [
        "watchlist",
        "symbol",
        "name",
        "market",
        "timeframe",
        "required",
        "cache_file",
        "exists",
        "start",
        "end",
        "rows",
        "age",
        "max_gap",
        "missing_recent",
        "gap_warning",
        "status",
        "reason",
    ]
    rows = [headers]

    for item in report.items:
        rows.append([
            report.watchlist,
            item.symbol,
            item.name,
            item.market,
            item.timeframe,
            "yes" if item.required else "no",
            item.cache_file,
            "yes" if item.exists else "no",
            short_datetime(item.start),
            short_datetime(item.end),
            str(item.rows) if item.rows is not None else "-",
            format_hours(item.age_hours),
            format_hours(item.max_gap_hours),
            "yes" if item.missing_recent else "no",
            "yes" if item.gap_warning else "no",
            item.status,
            item.reason,
        ])

    widths = [max(len(str(row[column])) for row in rows) for column in range(len(headers))]
    for index, row in enumerate(rows):
        lines.append("  ".join(str(cell).ljust(widths[column]) for column, cell in enumerate(row)))
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def format_datetime(value: datetime) -> str:
    if value.hour == 0 and value.minute == 0 and value.second == 0:
        return value.strftime("%Y-%m-%d")
    return value.isoformat(timespec="seconds")


def short_datetime(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ")[:16]


def format_hours(value: float | None) -> str:
    if value is None:
        return "-"
    if value >= 24:
        return f"{value / 24:.1f}d"
    return f"{value:.1f}h"


def format_timedelta(value: timedelta) -> str:
    seconds = int(value.total_seconds())
    if seconds % 3600 == 0 and seconds < 2 * 86400:
        return f"{seconds // 3600}h"
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    return f"{seconds}s"


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
