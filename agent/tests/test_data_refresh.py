"""Tests for data_refresh module — RF-01 through RF-05 coverage.

Mocks are placed at the source module level, not at the local-import sites
inside _fetch_timeframe().
"""

from __future__ import annotations

import json
import time as time_mod
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Import the module under test
from src.data.data_refresh import (
    RefreshItemResult,
    RefreshReport,
    RefreshStats,
    _fetch_timeframe,
    _is_fresh,
    _parse_timeframes_for_refresh,
    _write_parquet,
    run_data_refresh,
    stale_after_for,
)


# ---------------------------------------------------------------------------
# Shared test data fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv_df(index_dates):
    """Create a minimal OHLCV DataFrame for test use."""
    n = len(index_dates)
    return pd.DataFrame(
        {
            "open": [190.0] * n,
            "high": [195.0] * n,
            "low": [188.0] * n,
            "close": [193.0] * n,
            "volume": [1_000_000] * n,
        },
        index=pd.to_datetime(index_dates),
    )


# ---------------------------------------------------------------------------
# RF-01: scan --run --refresh triggers pre-gate fetch
# ---------------------------------------------------------------------------

class TestRF01_RefreshTriggered:
    """RF-01: scan --run --refresh auto-fetches stale/missing data before health gate."""

    def test_run_data_refresh_attempts_fetch_for_missing_file(self, tmp_path):
        """When the parquet file is missing, run_data_refresh attempts to fetch it."""
        # Note: no CSV header row — WatchlistReader.load_raw() skips "symbol,..." lines
        wl = tmp_path / "wl.csv"
        wl.write_text("MISSING.ZZ,MISSING.ZZ,us_futures,,,1D\n")

        mock_df = _make_ohlcv_df([datetime.now()])

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=mock_df) as mock_dl:
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        # Should have tried to fetch (file was missing)
        mock_dl.assert_called()
        # Verify the item was not skipped as fresh
        assert report.stats.skipped_fresh == 0
        # Verify some fetch action was recorded (created or fetched or failed)
        assert report.stats.total >= 1

    def test_refresh_writes_parquet_to_expected_path(self, tmp_path):
        """Fetched data is written to the path resolve_cache_file() returns."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        fetched_df = _make_ohlcv_df([datetime.now()])

        # Patch _is_fresh so the mock parquet doesn't accidentally skip the fetch
        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=fetched_df):
                run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        expected = tmp_path / "us_futures" / "GC=F" / "1d.parquet"
        assert expected.exists(), f"Expected parquet at {expected}"

        written = pd.read_parquet(expected)
        assert "close" in written.columns
        assert len(written) == 1

# ---------------------------------------------------------------------------
# RF-02: Source routing
# ---------------------------------------------------------------------------

class TestRF02_SourceRouting:
    """RF-02: Refresh uses appropriate source per market (yfinance for US futures)."""

    def test_us_futures_uses_yfinance(self, tmp_path):
        """US futures symbols are fetched via yfinance.download."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        fetched_df = _make_ohlcv_df([datetime.now()])

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=fetched_df) as mock_dl:
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        mock_dl.assert_called()
        call_args = str(mock_dl.call_args)
        assert "GC=F" in call_args
        assert report.stats.by_source.get("yfinance", 0) >= 1

    def test_us_equity_uses_yfinance(self, tmp_path):
        """US equity symbols are fetched via yfinance.download."""
        wl = tmp_path / "wl.csv"
        wl.write_text("AAPL.US,AAPL.US,us_equity,,,1D\n")

        fetched_df = _make_ohlcv_df([datetime.now()])

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=fetched_df) as mock_dl:
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        mock_dl.assert_called()

    def test_a_share_uses_hybrid_fetcher(self, tmp_path):
        """A-share symbols fall back to HybridDataFetcher."""
        wl = tmp_path / "wl.csv"
        wl.write_text("600519.SH,600519.SH,a_share,,,1D\n")

        mock_df = _make_ohlcv_df([datetime.now()])

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("agent.backtest.loaders.hybrid_fetcher.HybridDataFetcher") as mock_cls:
                mock_instance = MagicMock()
                mock_instance.fetch.return_value = {"600519.SH": mock_df}
                mock_cls.return_value = mock_instance

                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

                mock_instance.fetch.assert_called()
                assert report.stats.by_source.get("hybrid", 0) >= 1


# ---------------------------------------------------------------------------
# RF-03: Rate limit handling
# ---------------------------------------------------------------------------

class TestRF03_RateLimits:
    """RF-03: Refresh respects rate limits (429 handling, backoff)."""

    def test_429_triggers_exponential_backoff(self, tmp_path):
        """HTTP 429 errors cause exponential backoff and retry."""
        wl = tmp_path / "wl.csv"
        wl.write_text("AAPL.US,AAPL.US,us_equity,,,1D\n")

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("429 Client Error: Too Many Requests")
            # Succeed on 3rd attempt
            return _make_ohlcv_df([datetime.now()])

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", side_effect=side_effect):
                with patch("time.sleep") as mock_sleep:
                    report = run_data_refresh(
                        watchlist_path=str(wl),
                        data_dir=str(tmp_path),
                        scan_date_str="2026-06-10",
                    )

        # Should have retried
        assert call_count[0] >= 2
        # Backoff sleeps should have been called
        assert mock_sleep.call_count >= 2

    def test_rate_limited_symbol_recorded_in_errors(self, tmp_path):
        """Rate-limited symbols appear in stats.errors with 'rate-limited' message."""
        wl = tmp_path / "wl.csv"
        wl.write_text("AAPL.US,AAPL.US,us_equity,,,1D\n")

        def always_rate_limit(*args, **kwargs):
            raise Exception("429 Client Error: Too Many Requests")

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", side_effect=always_rate_limit):
                with patch("time.sleep"):
                    report = run_data_refresh(
                        watchlist_path=str(wl),
                        data_dir=str(tmp_path),
                        scan_date_str="2026-06-10",
                    )

        assert report.stats.failed >= 1
        error_msgs = list(report.stats.errors)
        assert any(
            "rate-limit" in e or "429" in e for e in error_msgs
        ), f"Expected rate-limit error in {error_msgs}"


# ---------------------------------------------------------------------------
# RF-04: Same parquet paths
# ---------------------------------------------------------------------------

class TestRF04_SameParquetPaths:
    """RF-04: Refresh writes to same parquet paths used by scan."""

    def test_fetched_parquet_at_resolve_cache_file_path(self, tmp_path):
        """Data is written to the path that resolve_cache_file(market, symbol, tf) returns."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        fetched_df = _make_ohlcv_df([datetime.now()])

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=fetched_df):
                run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        # Same path scan_plan.build_scan_plan would use
        from src.data.watchlist_data_health import resolve_cache_file

        expected = resolve_cache_file(tmp_path, "us_futures", "GC=F", "1d")
        assert expected.exists(), (
            f"Parquet not at resolve_cache_file() path: {expected}"
        )
        assert expected == tmp_path / "us_futures" / "GC=F" / "1d.parquet"

    def test_refresh_report_items_have_correct_cache_paths(self, tmp_path):
        """RefreshItemResult.cache_path matches resolve_cache_file() output."""
        wl = tmp_path / "wl.csv"
        wl.write_text("CL=F,CL=F,us_futures,,,1D\n")

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=None):
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        from src.data.watchlist_data_health import resolve_cache_file

        expected = resolve_cache_file(tmp_path, "us_futures", "CL=F", "1d")
        assert all(
            item.cache_path == expected for item in report.items
        ), f"Expected {expected}, got {[i.cache_path for i in report.items]}"


# ---------------------------------------------------------------------------
# RF-05: Non-blocking refresh failures
# ---------------------------------------------------------------------------

class TestRF05_NonBlocking:
    """RF-05: Refresh failures are non-blocking (gate still runs with available data)."""

    def test_refresh_failure_does_not_raise(self, tmp_path):
        """run_data_refresh returns a RefreshReport even when fetch raises an exception."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        # Simulate complete network failure — run_data_refresh must not raise
        def fatal_error(*args, **kwargs):
            raise OSError("network unreachable")

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", side_effect=fatal_error):
                # Must NOT raise
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        assert isinstance(report, RefreshReport)
        assert report.stats.total >= 1
        assert report.stats.failed >= 1

    def test_failed_fetch_counted_in_stats(self, tmp_path):
        """Failed fetch operations are recorded in stats.failed."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=None):
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        assert report.stats.failed >= 1
        assert any("GC=F" in e for e in report.stats.errors)

    def test_blocking_timeframe_failures_counted(self, tmp_path):
        """Failed 1d and 1h (blocking) items are counted in blocking_failures."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D-1H\n")

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=None):
                report = run_data_refresh(
                    watchlist_path=str(wl),
                    data_dir=str(tmp_path),
                    scan_date_str="2026-06-10",
                )

        blocking_items = [
            i for i in report.items
            if i.timeframe in ("1d", "1h") and i.action == "failed"
        ]
        assert len(blocking_items) >= 2, (
            f"Expected 2 blocking failures, got {[i.timeframe for i in blocking_items]}"
        )
        assert report.blocking_failures >= 2

    def test_refresh_report_serializable_to_json(self, tmp_path):
        """RefreshReport.to_dict() produces JSON-serializable output."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        with patch("yfinance.download", return_value=None):
            report = run_data_refresh(
                watchlist_path=str(wl),
                data_dir=str(tmp_path),
                scan_date_str="2026-06-10",
            )

        result = report.to_dict()
        # Must not raise
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert "stats" in parsed
        assert "items" in parsed
        assert "blocking_failures" in parsed


# ---------------------------------------------------------------------------
# Freshness check (RF-02 / data freshness per-symbol)
# ---------------------------------------------------------------------------

class TestFreshnessCheck:
    """Refresh skips symbols whose data is fresh (no unnecessary API calls)."""

    def test_fresh_data_skipped(self, tmp_path):
        """When a parquet file has recent data, no fetch is attempted."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        # Create fresh parquet: max date = today, within 2-day threshold
        out_dir = tmp_path / "us_futures" / "GC=F"
        out_dir.mkdir(parents=True)
        fresh_df = _make_ohlcv_df([
            datetime.now() - timedelta(hours=2),
            datetime.now() - timedelta(hours=1),
        ])
        fresh_df.to_parquet(out_dir / "1d.parquet", index=True)

        with patch("yfinance.download") as mock_dl:
            report = run_data_refresh(
                watchlist_path=str(wl),
                data_dir=str(tmp_path),
                scan_date_str="2026-06-10",
            )

        assert report.stats.skipped_fresh >= 1
        mock_dl.assert_not_called()

    def test_stale_data_not_skipped(self, tmp_path):
        """When a parquet file has old data, fetch IS attempted."""
        wl = tmp_path / "wl.csv"
        wl.write_text("GC=F,GC=F,us_futures,,,1D\n")

        # Create stale parquet: max date MORE than 3 days old (1d threshold = 2 days)
        # Use 10 days to be safely past any threshold
        out_dir = tmp_path / "us_futures" / "GC=F"
        out_dir.mkdir(parents=True)
        stale_df = _make_ohlcv_df([
            datetime.now() - timedelta(days=10),
            datetime.now() - timedelta(days=9),
        ])
        stale_df.to_parquet(out_dir / "1d.parquet", index=True)

        with patch("yfinance.download", return_value=None):
            report = run_data_refresh(
                watchlist_path=str(wl),
                data_dir=str(tmp_path),
                scan_date_str="2026-06-10",
            )

        # Should have attempted fetch, not skipped
        assert report.stats.skipped_fresh == 0
        assert report.stats.total >= 1


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestStaleAfterFor:
    """stale_after_for() returns correct thresholds."""

    def test_1d_threshold(self):
        assert stale_after_for("us_futures", "1d") == timedelta(days=2)

    def test_1h_threshold(self):
        # HK market is currently CLOSED, so session-aware logic applies 1.5x.
        # base=6h → 6h × 1.5 = 9h when market is closed.
        # When market is open (9:30-12:00 or 13:00-16:00 HKT), returns 6h.
        assert stale_after_for("hk_stock", "1h") == timedelta(hours=9)

    def test_us_futures_1h_has_24h_override(self):
        """us_futures/1h has a 24h override per the MARKET_TIMEFRAME_STALE_AFTER table."""
        assert stale_after_for("us_futures", "1h") == timedelta(hours=24)

    def test_4h_threshold(self):
        assert stale_after_for("us_futures", "4h") == timedelta(hours=12)


class TestParseTimeframes:
    """_parse_timeframes_for_refresh handles all watchlist formats."""

    @pytest.mark.parametrize("raw,expected", [
        ("1D-1H", ["1d", "1h"]),
        ("1D|4H", ["1d", "4h"]),
        ("1D,1H,4H", ["1d", "1h", "4h"]),
        ("d1-h1", ["1d", "1h"]),
        ("1H", ["1h"]),
    ])
    def test_parses_formats(self, raw, expected):
        result = _parse_timeframes_for_refresh(raw)
        assert result == expected


class TestRefreshStats:
    """RefreshStats aggregates correctly."""

    def test_success_property(self):
        stats = RefreshStats(fetched=2, created=1, failed=1, total=4)
        assert stats.success == 3

    def test_to_dict(self):
        stats = RefreshStats(total=5, fetched=2, created=1, failed=2)
        d = stats.to_dict()
        assert d["total"] == 5
        assert d["fetched"] == 2
        assert d["created"] == 1
        assert d["failed"] == 2
        # 'success' is a property, not a dict key — check the sum instead
        assert d["fetched"] + d["created"] == 3


class TestWriteParquet:
    """_write_parquet creates parent dirs and writes correct data."""

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "data.parquet"
        df = _make_ohlcv_df([datetime.now()])
        _write_parquet(df, path)
        assert path.exists()
        written = pd.read_parquet(path)
        assert list(written.columns) == list(df.columns)

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "data.parquet"
        df1 = _make_ohlcv_df([datetime.now()])
        _write_parquet(df1, path)
        df2 = _make_ohlcv_df([datetime.now() - timedelta(days=1)])
        _write_parquet(df2, path)
        written = pd.read_parquet(path)
        assert len(written) == 1  # df2 has 1 row


class TestIsFresh:
    """_is_fresh returns correct freshness verdict."""

    def test_missing_file_not_fresh(self, tmp_path):
        path = tmp_path / "nonexistent.parquet"
        assert not _is_fresh(path, "us_futures", "1d")

    def test_old_data_not_fresh(self, tmp_path):
        path = tmp_path / "old.parquet"
        old_df = _make_ohlcv_df([datetime.now() - timedelta(days=10)])
        old_df.to_parquet(path, index=True)
        assert not _is_fresh(path, "us_futures", "1d")

    def test_recent_data_is_fresh(self, tmp_path):
        path = tmp_path / "fresh.parquet"
        fresh_df = _make_ohlcv_df([datetime.now() - timedelta(hours=1)])
        fresh_df.to_parquet(path, index=True)
        assert _is_fresh(path, "us_futures", "1d")


class TestFetchTimeframeUnit:
    """Unit tests for _fetch_timeframe with direct mocking."""

    def test_fetch_timeframe_success(self, tmp_path):
        """_fetch_timeframe writes parquet and returns correct action."""
        cache = tmp_path / "us_futures" / "GC=F" / "1d.parquet"
        cache.parent.mkdir(parents=True)

        fetched_df = _make_ohlcv_df([datetime.now()])

        # Patch _is_fresh to return False so fetch is always attempted
        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", return_value=fetched_df):
                result = _fetch_timeframe(
                    symbol="GC=F",
                    market="us_futures",
                    timeframe="1d",
                    cache_path=cache,
                )

        assert result.action in ("created", "fetched")
        assert result.error is None
        assert result.rows == 1
        assert cache.exists()

    def test_fetch_timeframe_network_error(self, tmp_path):
        """_fetch_timeframe captures errors without raising."""
        cache = tmp_path / "us_futures" / "GC=F" / "1d.parquet"
        cache.parent.mkdir(parents=True)

        def error(*a, **kw):
            raise OSError("connection refused")

        with patch("src.data.data_refresh._is_fresh", return_value=False):
            with patch("yfinance.download", side_effect=error):
                result = _fetch_timeframe(
                    symbol="GC=F",
                    market="us_futures",
                    timeframe="1d",
                    cache_path=cache,
                )

        assert result.action == "failed"
        assert result.error is not None
        assert "connection refused" in result.error
