"""Focused tests for scan_signal_buckets (SIG-01, SIG-02)."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.data.scan_signal_buckets import (
    BULL_BEAR_THRESHOLD,
    WATCH_CONFIDENCE_FLOOR,
    ScanSignalReport,
    SymbolSignalResult,
    classify_trading_signal,
    run_signal_scan,
)
from src.data.scan_plan import ScanPlan, SymbolPlan
from src.strategies.composite.base import TradingSignal


# --- Helpers ----------------------------------------------------------------

def _make_ohlcv_df(n_rows: int = 100) -> pd.DataFrame:
    """Create a valid OHLCV DataFrame for testing."""
    dates = pd.bdate_range("2024-01-01", periods=n_rows)
    close = 100.0 + pd.Series(range(n_rows)).multiply(0.1)
    high = close + 1.0
    low = close - 1.0
    open_price = close + 0.5
    volume = pd.Series(range(n_rows)).multiply(100) + 1000
    df = pd.DataFrame(
        {"open": open_price, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    return df


def _make_signal(
    direction: str = "BULL",
    status: str = "VALID",
    readiness: str = "READY",
    confidence: float = 0.7,
    signal_score: float = 50.0,
    warnings: list[str] | None = None,
    reasons: list[str] | None = None,
) -> TradingSignal:
    """Create a TradingSignal for testing."""
    return TradingSignal(
        direction=direction,
        status=status,
        readiness=readiness,
        confidence=confidence,
        signal_score=signal_score,
        components={"test": 0.5},
        warnings=warnings or [],
        reasons=reasons or [],
        source_results={},
        metadata={},
    )


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    """Write a minimal watchlist CSV."""
    path = tmp_path / "wl.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


# --- TestBucketClassification (SIG-02) ------------------------------------


class TestBucketClassification:
    """Test classify_trading_signal() — SIG-02."""

    @pytest.mark.parametrize(
        "direction,status,readiness,confidence,expected_bucket",
        [
            # BULL + VALID + READY
            ("BULL", "VALID", "READY", 0.70, "actionable"),
            ("BULL", "VALID", "READY", 0.60, "actionable"),
            ("BULL", "VALID", "READY", 0.45, "actionable"),
            # BEAR + VALID + READY
            ("BEAR", "VALID", "READY", 0.70, "actionable"),
            ("BEAR", "VALID", "READY", 0.60, "actionable"),
            ("BEAR", "VALID", "READY", 0.45, "actionable"),
            # watch (confidence >= 0.25 but < 0.45)
            ("BULL", "VALID", "READY", 0.44, "watch"),
            ("BULL", "VALID", "READY", 0.30, "watch"),
            ("BEAR", "VALID", "READY", 0.44, "watch"),
            # risk_excluded (confidence < 0.25)
            ("BULL", "VALID", "READY", 0.24, "risk_excluded"),
            ("BULL", "VALID", "READY", 0.10, "risk_excluded"),
            ("BEAR", "VALID", "READY", 0.24, "risk_excluded"),
        ],
    )
    def test_exactly_one_bucket_per_signal(
        self,
        direction,
        status,
        readiness,
        confidence,
        expected_bucket,
    ):
        """Every TradingSignal maps to exactly one valid bucket."""
        signal = _make_signal(
            direction=direction,
            status=status,
            readiness=readiness,
            confidence=confidence,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == expected_bucket, f"expected {expected_bucket}, got {bucket}: {reason}"
        assert bucket in {
            "actionable",
            "watch",
            "risk_excluded",
            "skipped",
            "failed",
        }

    def test_invalid_status_returns_failed(self):
        """INVALID status -> failed bucket."""
        signal = _make_signal(
            status="INVALID",
            direction="BULL",
            warnings=["missing volume column"],
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "failed"
        assert "INVALID" in reason

    def test_no_signal_returns_skipped(self):
        """NO_SIGNAL status -> skipped bucket."""
        signal = _make_signal(
            status="NO_SIGNAL",
            direction="NEUTRAL",
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "skipped"
        assert "NO_SIGNAL" in reason

    def test_bull_valid_ready_high_confidence_actionable(self):
        """BULL + VALID + READY + high confidence -> actionable."""
        signal = _make_signal(
            direction="BULL",
            status="VALID",
            readiness="READY",
            confidence=0.70,
            signal_score=60.0,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "actionable"
        assert "BULL" in reason

    def test_bear_valid_ready_high_confidence_actionable(self):
        """BEAR + VALID + READY + high confidence -> actionable."""
        signal = _make_signal(
            direction="BEAR",
            status="VALID",
            readiness="READY",
            confidence=0.60,
            signal_score=-55.0,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "actionable"
        assert "BEAR" in reason

    def test_bull_valid_ready_low_confidence_watch(self):
        """BULL + VALID + READY + 0.25 <= confidence < 0.45 -> watch."""
        signal = _make_signal(
            direction="BULL",
            status="VALID",
            readiness="READY",
            confidence=0.30,
            signal_score=35.0,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "watch"
        assert "low confidence" in reason

    def test_bull_valid_ready_very_low_confidence_risk(self):
        """BULL + VALID + READY + confidence < 0.25 -> risk_excluded."""
        signal = _make_signal(
            direction="BULL",
            status="VALID",
            readiness="READY",
            confidence=0.15,
            signal_score=10.0,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "risk_excluded"
        assert "low confidence" in reason

    def test_neutral_returns_watch(self):
        """NEUTRAL direction -> watch bucket."""
        signal = _make_signal(
            direction="NEUTRAL",
            status="VALID",
            readiness="READY",
            confidence=0.90,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "watch"
        assert "NEUTRAL" in reason

    def test_filtered_returns_risk_excluded(self):
        """FILTERED status -> risk_excluded."""
        signal = _make_signal(
            status="FILTERED",
            direction="BULL",
            warnings=["volume too low"],
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "risk_excluded"
        assert "FILTERED" in reason

    def test_blocked_readiness_returns_risk_excluded(self):
        """BLOCKED readiness -> risk_excluded."""
        signal = _make_signal(
            status="VALID",
            readiness="BLOCKED",
            direction="BULL",
            confidence=0.70,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "risk_excluded"
        assert "BLOCKED" in reason

    def test_exhausted_readiness_returns_risk_excluded(self):
        """EXHAUSTED readiness -> risk_excluded."""
        signal = _make_signal(
            status="VALID",
            readiness="EXHAUSTED",
            direction="BEAR",
            confidence=0.60,
        )
        bucket, reason = classify_trading_signal(signal)
        assert bucket == "risk_excluded"
        assert "EXHAUSTED" in reason

    def test_thresholds_are_module_level_constants(self):
        """Threshold constants exist at module level."""
        assert BULL_BEAR_THRESHOLD == 0.45
        assert WATCH_CONFIDENCE_FLOOR == 0.25


# --- TestSignalScan (SIG-01) ------------------------------------------------


class TestSignalScan:
    """Test run_signal_scan() — SIG-01."""

    def test_strategy_runs_on_valid_parquet(self, tmp_path: Path):
        """run_signal_scan() returns a report with a valid bucket on good data."""
        # Setup watchlist CSV
        wl_path = _write_csv(
            tmp_path,
            [{"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"}],
        )
        # Setup parquet data
        data_dir = tmp_path / "data"
        market_dir = data_dir / "us_futures" / "GC=F"
        market_dir.mkdir(parents=True)
        df = _make_ohlcv_df(100)
        parquet_path = market_dir / "1d.parquet"
        df.to_parquet(parquet_path, engine="pyarrow")

        output_dir = tmp_path / "output"

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=[
                SymbolPlan(
                    symbol="GC=F",
                    name="Gold",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[parquet_path],
                    output_path=output_dir / "GC=F.json",
                )
            ],
        )

        report = run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")

        assert report is not None
        # At least one bucket should have non-null trading_signal
        buckets_with_signals = [
            bn for bn, items in report.buckets.items()
            if any(item.get("trading_signal") for item in items)
        ]
        assert len(buckets_with_signals) >= 1

    def test_signal_fields_in_results(self, tmp_path: Path):
        """trading_signal dict contains all required keys."""
        wl_path = _write_csv(
            tmp_path,
            [{"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"}],
        )
        data_dir = tmp_path / "data"
        market_dir = data_dir / "us_futures" / "GC=F"
        market_dir.mkdir(parents=True)
        df = _make_ohlcv_df(100)
        df.to_parquet(market_dir / "1d.parquet", engine="pyarrow")
        output_dir = tmp_path / "output"

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=[
                SymbolPlan(
                    symbol="GC=F",
                    name="Gold",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[market_dir / "1d.parquet"],
                    output_path=output_dir / "GC=F.json",
                )
            ],
        )

        report = run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")
        # Find the bucket with this symbol
        symbol_result = None
        for bucket_items in report.buckets.values():
            for item in bucket_items:
                if item["symbol"] == "GC=F":
                    symbol_result = item
                    break
        assert symbol_result is not None, "GC=F not found in any bucket"
        ts = symbol_result.get("trading_signal")
        assert ts is not None, "trading_signal should not be None"
        assert "direction" in ts
        assert "status" in ts
        assert "readiness" in ts
        assert "signal_score" in ts
        assert "confidence" in ts
        assert "reasons" in ts

    def test_skipped_when_parquet_missing(self, tmp_path: Path):
        """Missing parquet -> symbol lands in skipped bucket."""
        wl_path = _write_csv(
            tmp_path,
            [{"symbol": "MISSING", "name": "No Data", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"}],
        )
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "output"
        # Intentionally do NOT create the parquet file

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=[
                SymbolPlan(
                    symbol="MISSING",
                    name="No Data",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[data_dir / "us_futures" / "MISSING" / "1d.parquet"],
                    output_path=output_dir / "MISSING.json",
                )
            ],
        )

        report = run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")
        skipped = report.buckets.get("skipped", [])
        assert len(skipped) == 1
        assert skipped[0]["symbol"] == "MISSING"
        assert skipped[0]["bucket_reason"] != ""


# --- TestGracefulDegradation (SIG-02) --------------------------------------


class TestGracefulDegradation:
    """Test per-symbol exception isolation — SIG-02."""

    def test_failed_symbol_does_not_abort(self, tmp_path: Path):
        """One bad symbol does not abort the scan of remaining symbols."""
        # Symbol 1: valid parquet
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"},
            {"symbol": "BAD", "name": "Bad", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        wl_path = _write_csv(tmp_path, wl_rows)
        data_dir = tmp_path / "data"
        market_dir = data_dir / "us_futures" / "GC=F"
        market_dir.mkdir(parents=True)
        df = _make_ohlcv_df(100)
        df.to_parquet(market_dir / "1d.parquet", engine="pyarrow")
        # BAD parquet: corrupt/invalid file
        bad_market = data_dir / "us_futures" / "BAD"
        bad_market.mkdir(parents=True)
        # Write garbage to parquet
        (bad_market / "1d.parquet").write_bytes(b"PARQUET:corrupt")
        output_dir = tmp_path / "output"

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=[
                SymbolPlan(
                    symbol="GC=F",
                    name="Gold",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[market_dir / "1d.parquet"],
                    output_path=output_dir / "GC=F.json",
                ),
                SymbolPlan(
                    symbol="BAD",
                    name="Bad",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[bad_market / "1d.parquet"],
                    output_path=output_dir / "BAD.json",
                ),
            ],
        )

        # Should NOT raise — one bad symbol must not abort scan
        report = run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")

        # Both symbols should appear in results
        all_symbols = [
            item["symbol"]
            for bucket_items in report.buckets.values()
            for item in bucket_items
        ]
        assert "GC=F" in all_symbols
        assert "BAD" in all_symbols

    def test_skipped_records_reason(self, tmp_path: Path):
        """Skipped symbol has a non-empty, descriptive bucket_reason."""
        wl_path = _write_csv(
            tmp_path,
            [{"symbol": "EMPTY", "name": "Empty", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"}],
        )
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "output"

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=[
                SymbolPlan(
                    symbol="EMPTY",
                    name="Empty",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[data_dir / "us_futures" / "EMPTY" / "1d.parquet"],
                    output_path=output_dir / "EMPTY.json",
                )
            ],
        )

        report = run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")
        skipped = report.buckets.get("skipped", [])
        assert len(skipped) == 1
        reason = skipped[0]["bucket_reason"]
        assert reason != ""
        assert len(reason) > 5  # non-trivial reason


# --- TestScanResultsJson (SIG-01, SIG-02) ----------------------------------


class TestScanResultsJson:
    """Test scan_results.json schema — SIG-01, SIG-02."""

    def test_json_schema(self, tmp_path: Path):
        """Written scan_results.json has required top-level keys."""
        wl_path = _write_csv(
            tmp_path,
            [{"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "CME", "sector": "metals", "timeframes": "1D"}],
        )
        data_dir = tmp_path / "data"
        market_dir = data_dir / "us_futures" / "GC=F"
        market_dir.mkdir(parents=True)
        df = _make_ohlcv_df(100)
        df.to_parquet(market_dir / "1d.parquet", engine="pyarrow")
        output_dir = tmp_path / "output"

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=[
                SymbolPlan(
                    symbol="GC=F",
                    name="Gold",
                    market="us_futures",
                    exchange="CME",
                    sector="metals",
                    timeframes=["1d"],
                    cache_paths=[market_dir / "1d.parquet"],
                    output_path=output_dir / "GC=F.json",
                )
            ],
        )

        run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")

        results_path = output_dir / "scan_results.json"
        assert results_path.exists(), f"scan_results.json not found at {results_path}"
        data = json.loads(results_path.read_text())

        assert "scan_info" in data
        assert "buckets_summary" in data
        assert "buckets" in data
        assert "metadata" in data
        summary = data["buckets_summary"]
        assert "actionable" in summary
        assert "watch" in summary
        assert "risk_excluded" in summary
        assert "skipped" in summary
        assert "failed" in summary
        assert "total" in summary

    def test_all_buckets_present_in_results(self, tmp_path: Path):
        """All 5 bucket names appear as keys in the buckets dict."""
        wl_rows = [
            {"symbol": "A1", "name": "A1", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            {"symbol": "A2", "name": "A2", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            {"symbol": "A3", "name": "A3", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            {"symbol": "A4", "name": "A4", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            {"symbol": "A5", "name": "A5", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
        ]
        wl_path = _write_csv(tmp_path, wl_rows)
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "output"

        def make_plan(symbol: str, cache_path: Path) -> SymbolPlan:
            return SymbolPlan(
                symbol=symbol,
                name=symbol,
                market="us_futures",
                exchange="CME",
                sector="s1",
                timeframes=["1d"],
                cache_paths=[cache_path],
                output_path=output_dir / f"{symbol}.json",
            )

        symbols: list[SymbolPlan] = []
        for i, row in enumerate(wl_rows):
            sym = row["symbol"]
            market_dir = data_dir / "us_futures" / sym
            market_dir.mkdir(parents=True)
            # Only create parquet for A1 and A2 (others will be skipped/missing)
            if i < 2:
                df = _make_ohlcv_df(100)
                df.to_parquet(market_dir / "1d.parquet", engine="pyarrow")
            symbols.append(make_plan(sym, market_dir / "1d.parquet"))

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=symbols,
        )

        run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")

        results_path = output_dir / "scan_results.json"
        data = json.loads(results_path.read_text())
        bucket_keys = set(data["buckets"].keys())
        assert bucket_keys == {"actionable", "watch", "risk_excluded", "skipped", "failed"}

    def test_total_matches_sum_of_buckets(self, tmp_path: Path):
        """total == sum of individual bucket counts."""
        wl_path = _write_csv(
            tmp_path,
            [
                {"symbol": "S1", "name": "S1", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
                {"symbol": "S2", "name": "S2", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
                {"symbol": "S3", "name": "S3", "market": "us_futures", "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            ],
        )
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "output"
        symbols: list[SymbolPlan] = []
        for row in [{"symbol": "S1"}, {"symbol": "S2"}, {"symbol": "S3"}]:
            sym = row["symbol"]
            market_dir = data_dir / "us_futures" / sym
            market_dir.mkdir(parents=True)
            df = _make_ohlcv_df(100)
            df.to_parquet(market_dir / "1d.parquet", engine="pyarrow")
            symbols.append(
                SymbolPlan(
                    symbol=sym,
                    name=sym,
                    market="us_futures",
                    exchange="CME",
                    sector="s1",
                    timeframes=["1d"],
                    cache_paths=[market_dir / "1d.parquet"],
                    output_path=output_dir / f"{sym}.json",
                )
            )

        plan = ScanPlan(
            watchlist_path=wl_path,
            watchlist_name="test.csv",
            data_dir=data_dir,
            output_dir=output_dir,
            scan_date=date(2024, 6, 9),
            symbols=symbols,
        )

        run_signal_scan(plan, output_dir, scan_date=date(2024, 6, 9), format="json")
        results_path = output_dir / "scan_results.json"
        data = json.loads(results_path.read_text())
        summary = data["buckets_summary"]
        total = summary["total"]
        bucket_sum = sum(
            summary[k]
            for k in ["actionable", "watch", "risk_excluded", "skipped", "failed"]
        )
        assert total == bucket_sum, f"total={total} != sum={bucket_sum}"
