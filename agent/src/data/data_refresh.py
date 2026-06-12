"""Incremental data refresh for scan loop.

Fetches only stale/missing parquet data using the HybridDataFetcher pipeline,
then writes results back to the same paths the scan health gate reads from.
Non-blocking: refresh failures are logged but do not stop the scan.

RF-01: scan --run --refresh triggers pre-gate fetch
RF-02: Routes to yfinance for US futures, appropriate loaders for others
RF-03: Respects 429 rate-limit errors with exponential backoff
RF-04: Writes to same parquet paths used by scan
RF-05: Refresh failures are non-blocking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .freshness import DataFreshnessChecker, Timeframe
from .watchlist_data_health import (
    BLOCKING_TIMEFRAMES,
    REQUIRED_COLUMNS,
    normalize_timeframe,
    read_local_parquet,
)

# Duplicate these here to avoid circular import with watchlist_data_health.
# They must stay in sync with watchlist_data_health.py.
_STALE_AFTER: dict[str, timedelta] = {
    "1d": timedelta(days=2),
    "1h": timedelta(hours=6),
    "4h": timedelta(hours=12),
}

_MARKET_TIMEFRAME_STALE_AFTER: dict[tuple[str, str], timedelta] = {
    ("us_futures", "1h"): timedelta(hours=24),
    ("us_future", "1h"): timedelta(hours=24),
    ("cn_futures", "1h"): timedelta(hours=24),
    ("cn_future", "1h"): timedelta(hours=24),
}

# Duplicate MARKET_DIRS to avoid circular import.
_MARKET_DIRS: dict[str, str] = {
    "us_futures": "us_futures",
    "us_future": "us_futures",
    "cn_futures": "cn_futures",
    "cn_future": "cn_futures",
    "us_etf": "etf",
    "etf": "etf",
    "us_stock": "us_stocks",
    "us_stocks": "us_stocks",
    "us_equity": "us_stocks",
    "hk_stock": "hk_stocks",
    "hk_stocks": "hk_stocks",
    "a_share": "a_shares",
    "a_shares": "a_shares",
    # Phase 20: add missing mappings
    "cn_stock": "cn_stocks",
    "cn_stocks": "cn_stocks",
    "hk_futures": "hk_futures",
}


def _resolve_market_dir(market: str) -> str:
    """Resolve a watchlist market value to the local data directory name."""
    return _MARKET_DIRS.get(market.strip().lower(), market.strip().lower())


def _resolve_cache_file(data_dir: Path, market: str, symbol: str, timeframe: str) -> Path:
    """Resolve the expected local parquet file path (mirrors watchlist_data_health.resolve_cache_file)."""
    return data_dir / _resolve_market_dir(market) / symbol / f"{normalize_timeframe(timeframe)}.parquet"

logger = logging.getLogger(__name__)

# Maximum retries for 429 (rate-limit) errors
MAX_RETRIES = 3
# Base delay for exponential backoff (seconds)
BACKOFF_BASE_SECS = 4.0
# yfinance historical data limits
YFINANCE_1H_LIMIT = timedelta(days=730)   # ~2 years
YFINANCE_1D_LIMIT = timedelta(days=365)   # ~1 year


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class RefreshItemResult:
    """Result for one symbol/timeframe refresh."""
    symbol: str
    timeframe: str
    cache_path: Path
    action: str          # "skipped_fresh" | "fetched" | "created" | "failed"
    rows: int | None
    error: str | None
    latency_ms: float
    source: str | None


@dataclass
class RefreshStats:
    """Aggregate statistics for a full refresh run."""
    total: int = 0
    skipped_fresh: int = 0
    fetched: int = 0
    created: int = 0
    failed: int = 0
    total_latency_ms: float = 0.0
    by_action: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    rate_limited: int = 0

    @property
    def success(self) -> int:
        return self.fetched + self.created

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "skipped_fresh": self.skipped_fresh,
            "fetched": self.fetched,
            "created": self.created,
            "failed": self.failed,
            "total_latency_ms": self.total_latency_ms,
            "by_action": self.by_action,
            "by_source": self.by_source,
            "rate_limited": self.rate_limited,
            "errors": self.errors[-10:],   # last 10
        }


@dataclass
class RefreshReport:
    """Full report returned by run_data_refresh()."""
    scan_date: str
    watchlist: str
    started_at: datetime
    finished_at: datetime
    items: list[RefreshItemResult]
    stats: RefreshStats
    blocking_failures: int = 0    # count of failed required (1d/1h) items
    blocking_warnings: int = 0

    def to_dict(self) -> dict:
        return {
            "scan_date": self.scan_date,
            "watchlist": self.watchlist,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_sec": (self.finished_at - self.started_at).total_seconds(),
            "stats": self.stats.to_dict(),
            "blocking_failures": self.blocking_failures,
            "blocking_warnings": self.blocking_warnings,
            "items": [
                {
                    "symbol": r.symbol,
                    "timeframe": r.timeframe,
                    "cache_path": str(r.cache_path),
                    "action": r.action,
                    "rows": r.rows,
                    "error": r.error,
                    "source": r.source,
                }
                for r in self.items
            ],
        }


# ---------------------------------------------------------------------------
# Session-aware helpers
# ---------------------------------------------------------------------------

def _updated_on_date(
    market: str,
    timeframe: str,
    market_date: date,
    data_dir: Path | None = None,
) -> bool:
    """Return True if the parquet for market/timeframe was last-updated on market_date.

    Checks the latest timestamp in the parquet index against the market-local date,
    accounting for market timezone.

    Returns False if the parquet doesn't exist or can't be read.

    Args:
        market: Market code (e.g., 'cn_stock', 'us_stock')
        timeframe: Normalized timeframe string ('1d', '1h', '4h')
        market_date: Market-local date to check
        data_dir: Data directory path (default from watchlist_data_health.DEFAULT_DATA_DIR)
    """
    from zoneinfo import ZoneInfo

    if data_dir is None:
        # Default to ./data relative to project root
        import os
        project_root = Path(__file__).resolve().parents[3]
        data_dir = project_root / "data"

    # Resolve the cache directory for this market/timeframe
    # _resolve_cache_file(data_dir, market, "*", timeframe) uses market literally
    # but actual directories use resolved market names (e.g., "cn_stocks" not "cn_stock")
    norm_market = market.strip().lower()
    market_dir_name = _resolve_market_dir(norm_market)
    timeframe_dir = data_dir / market_dir_name
    timeframe_file_glob = f"{normalize_timeframe(timeframe)}.parquet"

    # Find any parquet in the market directory matching the timeframe
    matches = list(timeframe_dir.glob(f"*/{timeframe_file_glob}"))
    if not matches:
        return False
    cache_path = matches[0]

    try:
        df, _ = read_local_parquet(cache_path)
        if df is None or df.empty:
            return False
        latest_ts = pd.Timestamp(df.index.max())
        # Normalize to UTC (parquet may contain tz-naive timestamps in pandas 3.x)
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.tz_localize("UTC")
        # Convert to market-local date
        norm_market = market.strip().lower()
        from .trading_sessions import MARKET_TZ
        tz_name = MARKET_TZ.get(norm_market)
        if tz_name:
            latest_date = latest_ts.tz_convert(tz_name).date()
        else:
            latest_date = latest_ts.tz_localize(None).date()
        return latest_date == market_date
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core refresh logic
# ---------------------------------------------------------------------------

def _stale_after_for_base(market: str, timeframe: str) -> timedelta:
    """Return the base staleness threshold for a market/timeframe combination.

    This is the raw threshold without session-aware adjustment.
    Used internally and by callers that need the base value.
    """
    norm_market = market.strip().lower()
    norm_tf = normalize_timeframe(timeframe)
    # Market-specific override (keys use "us_futures", "cn_futures" etc.)
    override = _MARKET_TIMEFRAME_STALE_AFTER.get((norm_market, norm_tf))
    if override is not None:
        return override
    # Generic threshold
    return _STALE_AFTER.get(norm_tf, timedelta(days=7))


def stale_after_for(
    market: str,
    timeframe: str,
    utc_now: datetime | None = None,
) -> timedelta:
    """Return session-aware staleness threshold for a market/timeframe.

    Adjusts the base threshold based on the current market session status:
    - HOLIDAY: 2x base threshold (market closed for holiday)
    - CLOSED with no update today: 1.5x base threshold (after hours, no new data expected)
    - CLOSED with update today: base threshold (data is fresh)
    - PRE_MARKET / REGULAR / POST_MARKET / CONTINUOUS: base threshold

    CAL-03: Session-aware freshness detection.
    """
    from zoneinfo import ZoneInfo

    utc_now = utc_now or datetime.now(timezone.utc)
    base = _stale_after_for_base(market, timeframe)

    norm_market = market.strip().lower()

    # Try to get session status (returns CONTINUOUS for unknown markets)
    try:
        from .trading_sessions import get_session_status, MARKET_TZ
        session_status = get_session_status(norm_market, utc_now)
    except Exception:
        session_status = None

    # Continuous markets (US futures, unknown): no session adjustment
    if session_status is None or session_status.value == "continuous":
        return base

    # Import here to avoid circular imports at module load time
    try:
        from .trading_sessions import MarketSessionStatus
    except Exception:
        MarketSessionStatus = None

    if MarketSessionStatus is None:
        return base

    if session_status == MarketSessionStatus.HOLIDAY:
        return base * 2
    elif session_status in (MarketSessionStatus.CLOSED, MarketSessionStatus.POST_MARKET):
        # CLOSED and POST_MARKET: no new data expected until next session.
        # Check if data was updated today in market timezone.
        # If updated today → base threshold (data from today's session is fresh).
        # If NOT updated today → 1.5x threshold (market closed, no opportunity to update).
        # Note: POST_MARKET is treated as closed for staleness — after-hours data
        # arrivals are optional and not guaranteed. This covers both A-share
        # (no after-hours) and US equity (after-hours data is sparse).
        tz_name = MARKET_TZ.get(norm_market)
        if tz_name:
            market_tz = ZoneInfo(tz_name)
            market_now = utc_now.astimezone(market_tz)
            market_date = market_now.date()
            if _updated_on_date(norm_market, timeframe, market_date):
                return base  # updated today, base threshold applies
            return base * 1.5  # closed/post-market, not updated today — lenient
        return base * 1.5
    else:
        # PRE_MARKET, REGULAR, CONTINUOUS — base threshold
        return base


def _data_age_hours(cache_path: Path) -> float | None:
    """Return the age in hours of the data in a parquet file, or None if unreadable."""
    if not cache_path.exists():
        return None
    df, _ = read_local_parquet(cache_path)
    if df is None or df.empty:
        return None
    try:
        latest = pd.Timestamp(df.index.max())
        age = (datetime.now() - latest.to_pydatetime()).total_seconds() / 3600.0
        return age
    except Exception:
        return None


def _is_fresh(cache_path: Path, market: str, timeframe: str) -> bool:
    """Return True when the local parquet is fresh enough to skip fetching."""
    norm_tf = normalize_timeframe(timeframe)
    age_hours = _data_age_hours(cache_path)
    if age_hours is None:
        # File missing or unreadable — not fresh
        return False
    threshold_hours = stale_after_for(market, timeframe).total_seconds() / 3600.0
    return age_hours < threshold_hours


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to parquet, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=True)


def _call_yfinance_with_backoff(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: str,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Call yfinance with exponential backoff on 429 errors (RF-03)."""
    import yfinance as yf

    for attempt in range(MAX_RETRIES):
        try:
            df = yf.download(
                symbol,
                start=start,
                end=end,
                interval=interval,
                auto_adjust=True,
                progress=False,
            )
            if df is not None and not df.empty:
                return df, None
            return None, "no data returned"
        except Exception as exc:
            err_str = str(exc)
            # Detect HTTP 429 (rate limit)
            if "429" in err_str or "Too Many Requests" in err_str:
                if attempt < MAX_RETRIES - 1:
                    delay = BACKOFF_BASE_SECS * (2 ** attempt)
                    logger.warning(
                        "yfinance 429 for %s (attempt %d/%d), backing off %.1fs",
                        symbol, attempt + 1, MAX_RETRIES, delay
                    )
                    time.sleep(delay)
                    continue
                return None, f"rate-limited after {MAX_RETRIES} retries"
            # Other errors
            return None, err_str
    return None, "unexpected exit after retries"


def _fetch_timeframe(
    symbol: str,
    market: str,
    timeframe: str,
    cache_path: Path,
) -> RefreshItemResult:
    """Fetch fresh data for one symbol/timeframe, write to cache_path.

    Returns a RefreshItemResult. Non-blocking: errors are captured, not raised.
    """
    import yfinance as yf
    from agent.backtest.loaders.yfinance_loader import _to_yfinance_symbol

    norm_tf = normalize_timeframe(timeframe)
    now = datetime.now()
    start = None
    interval_map = {"1d": "1d", "1h": "1h", "4h": "1h"}
    interval_str = interval_map.get(norm_tf, "1d")

    # Determine start date based on timeframe data limits
    if interval_str == "1h":
        start = now - YFINANCE_1H_LIMIT
    else:
        start = now - YFINANCE_1D_LIMIT

    t0 = time.time()

    # Convert symbol to yfinance format
    yf_symbol = _to_yfinance_symbol(symbol)

    # For US futures (GC=F, CL=F, SI=F etc.), use yfinance directly
    # For US equities (AAPL), use yfinance directly
    # For other markets, attempt via yfinance first, then hybrid fetcher fallback
    if market.strip().lower() in {"us_futures", "us_future", "us_equity", "us_stock"}:
        df, err = _call_yfinance_with_backoff(yf_symbol, start, now, interval_str)
        source = "yfinance"
    else:
        # Fallback: use HybridDataFetcher
        try:
            from agent.backtest.loaders.hybrid_fetcher import HybridDataFetcher
            fetcher = HybridDataFetcher()
            results = fetcher.fetch([symbol], start.isoformat(), now.isoformat(), interval_str)
            df = results.get(symbol)
            err = None if df is not None else "HybridDataFetcher returned no data"
            source = "hybrid"
        except Exception as exc:
            df = None
            err = str(exc)
            source = "hybrid"

    latency_ms = (time.time() - t0) * 1000

    if df is None or df.empty:
        return RefreshItemResult(
            symbol=symbol,
            timeframe=norm_tf,
            cache_path=cache_path,
            action="failed",
            rows=None,
            error=err or "no data",
            latency_ms=latency_ms,
            source=source,
        )

    # Rename columns to canonical lowercase
    rename = {
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    }
    df = df.rename(columns=rename)
    # Keep only OHLCV columns present
    keep = [c for c in REQUIRED_COLUMNS if c in df.columns]
    df = df[keep]

    # Re-sample 1h -> 4h if needed
    if norm_tf == "4h" and interval_str == "1h":
        try:
            df = df.resample("4H").agg({
                "open": "first", "high": "max",
                "low": "min", "close": "last",
            }).dropna()
            if "volume" in df.columns:
                df["volume"] = df["volume"].fillna(0)
        except Exception as exc:
            logger.warning("4h resample failed for %s: %s", symbol, exc)

    # Write parquet
    try:
        _write_parquet(df, cache_path)
    except Exception as exc:
        return RefreshItemResult(
            symbol=symbol,
            timeframe=norm_tf,
            cache_path=cache_path,
            action="failed",
            rows=len(df),
            error=f"write failed: {exc}",
            latency_ms=latency_ms,
            source=source,
        )

    action = "created" if not cache_path.exists() else "fetched"
    return RefreshItemResult(
        symbol=symbol,
        timeframe=norm_tf,
        cache_path=cache_path,
        action=action,
        rows=len(df),
        error=None,
        latency_ms=latency_ms,
        source=source,
    )


def run_data_refresh(
    watchlist_path: str,
    data_dir: str,
    scan_date: datetime | None = None,
    scan_date_str: str | None = None,
    console_output: bool = False,
) -> RefreshReport:
    """Run incremental data refresh for all symbols in a watchlist.

    Only fetches symbols/timeframes that are stale or missing.
    Returns a RefreshReport with per-item results and aggregate stats.

    RF-01: Called before data-health gate when --refresh is set
    RF-02: yfinance for US markets, HybridDataFetcher fallback for others
    RF-03: 429 errors trigger exponential backoff
    RF-04: Writes to same parquet paths the scan health gate reads
    RF-05: Failures are captured in the report, never raised

    Args:
        watchlist_path: Path to watchlist CSV
        data_dir: Root directory for parquet data
        scan_date: Scan date (default now)
        scan_date_str: ISO date string for the scan (e.g. "2026-06-10")
        console_output: If True, log to console as well as logger
    """
    from .watchlist import WatchlistReader

    started_at = datetime.now()
    scan_dt_str = scan_date_str or scan_date.isoformat() if scan_date else started_at.date().isoformat()

    data_path = Path(data_dir)
    reader = WatchlistReader(watchlist_path)
    raw_rows = reader.load_raw()

    stats = RefreshStats()
    items: list[RefreshItemResult] = []

    if console_output:
        print(f"[refresh] Starting data refresh for watchlist: {watchlist_path}")

    for row in raw_rows:
        symbol = (row.get("symbol") or "").strip()
        if not symbol or symbol.lower() in {"symbol", "code", "name"}:
            continue

        market = (row.get("market") or "us_futures").strip()
        timeframes_raw = row.get("timeframes") or "1D-1H"
        timeframes = _parse_timeframes_for_refresh(timeframes_raw)

        for timeframe in timeframes:
            cache_path = _resolve_cache_file(data_path, market, symbol, timeframe)
            norm_tf = normalize_timeframe(timeframe)

            stats.total += 1

            # RF-02 / freshness check: skip if data is fresh (RF-02)
            if _is_fresh(cache_path, market, norm_tf):
                item = RefreshItemResult(
                    symbol=symbol,
                    timeframe=norm_tf,
                    cache_path=cache_path,
                    action="skipped_fresh",
                    rows=None,
                    error=None,
                    latency_ms=0.0,
                    source=None,
                )
                items.append(item)
                stats.skipped_fresh += 1
                if console_output:
                    print(f"  [skip] {symbol}/{norm_tf} — data is fresh")
                continue

            # Fetch
            item = _fetch_timeframe(symbol, market, norm_tf, cache_path)
            items.append(item)
            stats.total_latency_ms += item.latency_ms

            if item.action == "failed":
                stats.failed += 1
                stats.errors.append(f"{symbol}/{norm_tf}: {item.error}")
            elif item.action == "created":
                stats.created += 1
            elif item.action == "fetched":
                stats.fetched += 1

            if item.source:
                stats.by_source[item.source] = stats.by_source.get(item.source, 0) + 1

            stats.by_action[item.action] = stats.by_action.get(item.action, 0) + 1

            if console_output:
                icon = "OK" if item.action != "failed" else "FAIL"
                msg = f"  [{icon}] {symbol}/{norm_tf}"
                if item.rows:
                    msg += f" — {item.rows} rows"
                if item.error:
                    msg += f" — {item.error}"
                print(msg)

    finished_at = datetime.now()

    # Count blocking failures (required timeframes)
    blocking_failures = sum(
        1 for item in items
        if item.action == "failed"
        and normalize_timeframe(item.timeframe) in BLOCKING_TIMEFRAMES
    )
    blocking_warnings = sum(
        1 for item in items
        if item.action == "failed"
        and normalize_timeframe(item.timeframe) not in BLOCKING_TIMEFRAMES
    )

    report = RefreshReport(
        scan_date=scan_dt_str,
        watchlist=watchlist_path,
        started_at=started_at,
        finished_at=finished_at,
        items=items,
        stats=stats,
        blocking_failures=blocking_failures,
        blocking_warnings=blocking_warnings,
    )

    if console_output:
        print(
            f"[refresh] Done in {report.to_dict()['duration_sec']:.1f}s — "
            f"{stats.success}/{stats.total} succeeded "
            f"({stats.skipped_fresh} fresh, {stats.failed} failed)"
        )

    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_timeframes_for_refresh(raw: str) -> list[str]:
    """Parse a timeframes field like '1D-1H' or '1D|4H' into a list of normalized strings."""
    # Mirror the logic from watchlist_data_health.required_and_declared_timeframes
    separators = [",", "-", "|", "/"]
    parts = [raw]
    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts
    normalized = []
    for part in parts:
        norm = normalize_timeframe(part.strip())
        if norm and norm not in normalized:
            normalized.append(norm)
    return normalized
