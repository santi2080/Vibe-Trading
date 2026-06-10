"""TST-01 focused verification tests for the daily scan CLI pipeline.

These tests verify end-to-end CLI behavior:
- Gate FAIL/WARN/PASS artifact emission
- Bucket invariant (exactly one bucket per symbol)
- Artifact schema consistency
- Path safety and CLI exit semantics
"""
from __future__ import annotations

import csv
import json
import os
import random
import string
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from cli.commands.scan import scan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv_df(n_rows: int = 100) -> pd.DataFrame:
    """Create synthetic OHLCV DataFrame with deterministic-ish data."""
    dates = pd.bdate_range("2024-01-01", periods=n_rows)
    np = __import__("numpy")
    close_vals = 100.0 + np.cumsum(np.random.default_rng(42).standard_normal(n_rows) * 0.5)
    close_vals = close_vals.tolist()
    high_vals = [c + abs(np.random.default_rng(43).standard_normal() * 0.3) for c in close_vals]
    low_vals = [c - abs(np.random.default_rng(44).standard_normal() * 0.3) for c in close_vals]
    open_vals = [close_vals[i] + np.random.default_rng(45).standard_normal() * 0.2 for i in range(n_rows)]
    volume_vals = np.random.default_rng(46).integers(1000, 10000, n_rows).tolist()
    return pd.DataFrame(
        {"open": open_vals, "high": high_vals, "low": low_vals,
         "close": close_vals, "volume": volume_vals},
        index=dates,
    )


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    """Write a minimal watchlist CSV."""
    path = tmp_path / "wl.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_parquet(df: pd.DataFrame, market_dir: Path, symbol: str, timeframe: str = "1d") -> Path:
    """Write OHLCV df to parquet path; skip if pyarrow unavailable."""
    pyarrow = pytest.importorskip("pyarrow", reason="pyarrow required for parquet I/O")
    market_dir.mkdir(parents=True, exist_ok=True)
    path = market_dir / symbol / f"{timeframe}.parquet"
    market_dir.joinpath(symbol).mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow")
    return path


def _mock_health_report(
    status: str = "PASS",
    blocking_failures: int = 0,
    warnings: int = 0,
    can_backtest: bool = True,
) -> MagicMock:
    """Build a mock WatchlistDataHealthReport matching the real interface."""
    report = MagicMock()
    report.gate_status = status
    report.blocking_failures = blocking_failures
    report.warnings = warnings
    report.can_backtest = can_backtest
    report.to_dict.return_value = {
        "status": status,
        "total_checks": 5,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "gate": {
            "status": status,
            "can_backtest": can_backtest,
            "blocking_failures": blocking_failures,
            "warnings": warnings,
            "total_checks": 5,
        },
        "items": [],
    }
    return report


def _run_scan_cli(
    tmp_path: Path,
    wl_rows: list[dict],
    include_stale_parquet: bool = False,
    include_fresh_parquet: bool = True,
    gate_status: str = "PASS",
    gate_blocking: int = 0,
    gate_warnings: int = 0,
    gate_can_backtest: bool = True,
    extra_args: list[str] | None = None,
    include_missing_parquet: bool = False,
) -> pytest.runner.TextTestResult:
    """Run the scan CLI with a real temp watchlist + optional parquet setup.

    Returns the Click result object.
    """
    wl = _write_csv(tmp_path, wl_rows)
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"

    for row in wl_rows:
        sym = row["symbol"]
        market_dir = data_dir / row["market"] / sym
        market_dir.mkdir(parents=True, exist_ok=True)

        if include_fresh_parquet:
            df = _make_ohlcv_df(100)
            df.to_parquet(market_dir / "1d.parquet", engine="pyarrow")

        if include_missing_parquet:
            # Intentionally do NOT create the parquet — symbol will be skipped
            pass

    runner = CliRunner()
    args = [
        "--watchlist", str(wl),
        "--data-dir", str(data_dir),
        "--output", str(output_dir),
        "--now", "2024-06-09",
        "--run",
    ]
    if extra_args:
        args += extra_args

    with patch("cli.commands.scan.check_watchlist_data") as mock_gate, \
         patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
        mock_gate.return_value = _mock_health_report(
            status=gate_status,
            blocking_failures=gate_blocking,
            warnings=gate_warnings,
            can_backtest=gate_can_backtest,
        )
        result = runner.invoke(scan, args)

    return result


# ---------------------------------------------------------------------------
# TestGateBlocksStrategy — CLI-level artifact emission on gate FAIL
# ---------------------------------------------------------------------------

class TestGateBlocksStrategy:
    """TST-01: Gate FAIL blocks signal scan and skips artifact emission."""

    def test_gate_fail_blocks_signal_scan(self, tmp_path: Path):
        """Gate FAIL: scan exits non-zero and scan_results.json is NOT written."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="FAIL",
            gate_blocking=2,
            gate_can_backtest=False,
        )

        assert result.exit_code != 0, f"Expected non-zero exit on FAIL, got {result.exit_code}. Output: {result.output}"
        output_dir = tmp_path / "output"
        assert not (output_dir / "scan_results.json").exists(), \
            "scan_results.json must NOT exist when gate FAIL blocks the scan"

    def test_gate_fail_writes_health_json(self, tmp_path: Path):
        """Gate FAIL: data_health.json IS written."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="FAIL",
            gate_blocking=1,
            gate_can_backtest=False,
        )

        output_dir = tmp_path / "output"
        health_path = output_dir / "data_health.json"
        assert health_path.exists(), \
            "data_health.json must be written even on gate FAIL"
        data = json.loads(health_path.read_text(encoding="utf-8"))
        assert data["gate"]["status"] == "FAIL"
        assert data["gate"]["can_backtest"] is False

    def test_gate_fail_writes_manifest(self, tmp_path: Path):
        """Gate FAIL: manifest.json IS written (written before gate runs)."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="FAIL",
            gate_blocking=1,
            gate_can_backtest=False,
        )

        output_dir = tmp_path / "output"
        manifest_path = output_dir / "manifest.json"
        assert manifest_path.exists(), \
            "manifest.json must be written even on gate FAIL (before gate runs)"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["scan_date"] == "2024-06-09"

    def test_gate_fail_does_not_write_report_md(self, tmp_path: Path):
        """Gate FAIL: report.md is NOT written (reporting phase skipped)."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="FAIL",
            gate_blocking=1,
            gate_can_backtest=False,
        )

        output_dir = tmp_path / "output"
        assert not (output_dir / "report.md").exists(), \
            "report.md must NOT exist when gate FAIL blocks the scan"


# ---------------------------------------------------------------------------
# TestGateWarnsContinues — CLI-level artifact emission on gate WARN/PASS
# ---------------------------------------------------------------------------

class TestGateWarnsContinues:
    """TST-01: Gate WARN/PASS continues and emits all four artifacts."""

    def test_gate_warn_continues_all_artifacts(self, tmp_path: Path):
        """Gate WARN: scan exits 0 and all 4 artifacts are written."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="WARN",
            gate_warnings=1,
            gate_can_backtest=True,
        )

        assert result.exit_code == 0, f"Expected exit 0 on WARN, got {result.exit_code}. Output: {result.output}"
        output_dir = tmp_path / "output"
        assert (output_dir / "data_health.json").exists(), "data_health.json missing"
        assert (output_dir / "scan_results.json").exists(), "scan_results.json missing"
        assert (output_dir / "report.md").exists(), "report.md missing"
        assert (output_dir / "manifest.json").exists(), "manifest.json missing"

    def test_gate_pass_continues_all_artifacts(self, tmp_path: Path):
        """Gate PASS: scan exits 0 and all 4 artifacts are written."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="PASS",
            gate_blocking=0,
            gate_can_backtest=True,
        )

        assert result.exit_code == 0, f"Expected exit 0 on PASS, got {result.exit_code}. Output: {result.output}"
        output_dir = tmp_path / "output"
        assert (output_dir / "data_health.json").exists(), "data_health.json missing"
        assert (output_dir / "scan_results.json").exists(), "scan_results.json missing"
        assert (output_dir / "report.md").exists(), "report.md missing"
        assert (output_dir / "manifest.json").exists(), "manifest.json missing"


# ---------------------------------------------------------------------------
# TestBucketInvariant — exactly-one-bucket and total = sum
# ---------------------------------------------------------------------------

class TestBucketInvariant:
    """TST-01: Bucket invariants verified at CLI / scan_results.json level."""

    def test_every_symbol_in_exactly_one_bucket(self, tmp_path: Path):
        """Every symbol appears in exactly one of the five buckets."""
        wl_rows = [
            # Valid symbol -> goes to some bucket
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
            # Missing parquet -> skipped bucket
            {"symbol": "NOMISS", "name": "No Data", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
            # Another valid symbol
            {"symbol": "SI=F", "name": "Silver", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            include_missing_parquet=True,  # NOMISS deliberately skipped
            gate_status="PASS",
        )

        assert result.exit_code == 0, f"Scan failed: {result.output}"
        output_dir = tmp_path / "output"
        results_path = output_dir / "scan_results.json"
        assert results_path.exists(), "scan_results.json not found"
        data = json.loads(results_path.read_text(encoding="utf-8"))

        bucket_names = {"actionable", "watch", "risk_excluded", "skipped", "failed"}
        all_items: list[dict] = []
        for bucket_name in bucket_names:
            all_items.extend(data["buckets"].get(bucket_name, []))

        seen: dict[str, int] = {}
        for item in all_items:
            sym = item["symbol"]
            seen[sym] = seen.get(sym, 0) + 1

        for sym, count in seen.items():
            assert count == 1, \
                f"Symbol {sym} appears in {count} buckets (expected exactly 1)"

    def test_total_equals_sum_of_buckets(self, tmp_path: Path):
        """buckets_summary.total == sum of all 5 bucket counts."""
        wl_rows = [
            {"symbol": "A", "name": "A", "market": "us_futures",
             "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            {"symbol": "B", "name": "B", "market": "us_futures",
             "exchange": "CME", "sector": "s1", "timeframes": "1D"},
            {"symbol": "C", "name": "C", "market": "us_futures",
             "exchange": "CME", "sector": "s1", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="PASS",
        )

        assert result.exit_code == 0, f"Scan failed: {result.output}"
        output_dir = tmp_path / "output"
        data = json.loads((output_dir / "scan_results.json").read_text(encoding="utf-8"))
        summary = data["buckets_summary"]
        total = summary["total"]
        bucket_sum = sum(
            summary[k]
            for k in ["actionable", "watch", "risk_excluded", "skipped", "failed"]
        )
        assert total == bucket_sum, \
            f"total={total} != sum={bucket_sum}"


# ---------------------------------------------------------------------------
# TestArtifactConsistency — schema validation for all artifacts
# ---------------------------------------------------------------------------

class TestArtifactConsistency:
    """TST-01: All four artifacts have the required schema fields."""

    def test_scan_results_json_schema(self, tmp_path: Path):
        """scan_results.json has all required top-level keys and bucket fields."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="PASS",
        )

        assert result.exit_code == 0
        output_dir = tmp_path / "output"
        data = json.loads((output_dir / "scan_results.json").read_text(encoding="utf-8"))

        # Top-level keys
        assert "scan_info" in data, "scan_results missing scan_info"
        assert "buckets_summary" in data, "scan_results missing buckets_summary"
        assert "buckets" in data, "scan_results missing buckets"
        assert "metadata" in data, "scan_results missing metadata"

        # buckets_summary fields
        summary = data["buckets_summary"]
        for field in ["actionable", "watch", "risk_excluded", "skipped", "failed", "total"]:
            assert field in summary, f"buckets_summary missing field: {field}"
            assert isinstance(summary[field], int), f"buckets_summary.{field} must be int"

    def test_data_health_json_schema(self, tmp_path: Path):
        """data_health.json has required top-level and gate fields."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="FAIL",
            gate_blocking=2,
            gate_can_backtest=False,
        )

        output_dir = tmp_path / "output"
        data = json.loads((output_dir / "data_health.json").read_text(encoding="utf-8"))

        # Top-level fields
        assert "status" in data, "data_health missing status"
        assert "total_checks" in data, "data_health missing total_checks"
        assert "blocking_failures" in data, "data_health missing blocking_failures"
        assert "warnings" in data, "data_health missing warnings"
        assert "gate" in data, "data_health missing gate"

        # gate sub-object
        gate = data["gate"]
        for field in ["status", "can_backtest", "blocking_failures", "warnings", "total_checks"]:
            assert field in gate, f"data_health.gate missing {field}"

    def test_manifest_json_schema(self, tmp_path: Path):
        """manifest.json has all required top-level and artifacts fields."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="PASS",
        )

        output_dir = tmp_path / "output"
        data = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

        for field in ["scan_date", "watchlist_name", "version", "artifacts", "scan_info", "total_symbols"]:
            assert field in data, f"manifest.json missing required field: {field}"

        artifacts = data["artifacts"]
        assert "data_health" in artifacts, "manifest.artifacts missing data_health"
        assert "scan_results" in artifacts, "manifest.artifacts missing scan_results"
        assert "report" in artifacts, "manifest.artifacts missing report"

    def test_report_md_contains_artifacts_section(self, tmp_path: Path):
        """report.md contains references to all three artifact filenames."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        result = _run_scan_cli(
            tmp_path=tmp_path,
            wl_rows=wl_rows,
            include_fresh_parquet=True,
            gate_status="PASS",
        )

        output_dir = tmp_path / "output"
        report_path = output_dir / "report.md"
        assert report_path.exists(), "report.md not found"
        md = report_path.read_text(encoding="utf-8")

        assert "data_health.json" in md, "report.md missing data_health.json reference"
        assert "scan_results.json" in md, "report.md missing scan_results.json reference"
        assert "report.md" in md, "report.md missing report.md self-reference"
        assert "manifest.json" in md, "report.md missing manifest.json reference"


# ---------------------------------------------------------------------------
# TestPathSafety — CLI handles invalid paths gracefully
# ---------------------------------------------------------------------------

class TestPathSafety:
    """TST-01: CLI rejects invalid paths and accepts absolute output paths."""

    def test_nonexistent_watchlist_fails(self, tmp_path: Path):
        """Non-existent watchlist path exits non-zero."""
        nonexistent = tmp_path / "does_not_exist.csv"
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(scan, [
            "--watchlist", str(nonexistent),
            "--data-dir", str(data_dir),
            "--output", str(output_dir),
            "--run",
        ])

        assert result.exit_code != 0, \
            f"Expected non-zero exit for non-existent watchlist, got {result.exit_code}"

    def test_absolute_output_path_accepted(self, tmp_path: Path):
        """Absolute --output path is accepted and artifacts written there."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        wl = _write_csv(tmp_path, wl_rows)
        data_dir = tmp_path / "data"
        market_dir = data_dir / "us_futures" / "GC=F"
        market_dir.mkdir(parents=True, exist_ok=True)
        _make_ohlcv_df(100).to_parquet(market_dir / "1d.parquet", engine="pyarrow")

        # Use a random absolute path under /tmp
        random_suffix = "".join(random.choices(string.ascii_lowercase, k=8))
        abs_output = Path(f"/tmp/scan-test-{random_suffix}")

        try:
            runner = CliRunner()
            with patch("cli.commands.scan.check_watchlist_data") as mock_gate, \
                 patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
                mock_gate.return_value = _mock_health_report(
                    status="PASS", blocking_failures=0, can_backtest=True
                )
                result = runner.invoke(scan, [
                    "--watchlist", str(wl),
                    "--data-dir", str(data_dir),
                    "--output", str(abs_output),
                    "--now", "2024-06-09",
                    "--run",
                ])

            assert result.exit_code == 0, \
                f"Expected exit 0 with absolute output path, got {result.exit_code}. Output: {result.output}"
            assert (abs_output / "scan_results.json").exists(), \
                "scan_results.json not found at absolute output path"
            assert (abs_output / "manifest.json").exists(), \
                "manifest.json not found at absolute output path"
        finally:
            import shutil as _shutil
            if abs_output.exists():
                _shutil.rmtree(abs_output)


# ---------------------------------------------------------------------------
# TestCliExitSemantics — CLI exit codes for --help, plan mode, validation
# ---------------------------------------------------------------------------

class TestCliExitSemantics:
    """TST-01: CLI exit codes match expected semantics."""

    def test_help_exits_0(self, tmp_path: Path):
        """scan --help exits 0."""
        runner = CliRunner()
        result = runner.invoke(scan, ["--help"])
        assert result.exit_code == 0, f"--help should exit 0, got {result.exit_code}"

    def test_plan_mode_exits_0(self, tmp_path: Path):
        """Plan mode (no --run) exits 0 regardless of watchlist validity."""
        wl_rows = [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures",
             "exchange": "CME", "sector": "metals", "timeframes": "1D"},
        ]
        wl = _write_csv(tmp_path, wl_rows)
        data_dir = tmp_path / "data"

        runner = CliRunner()
        result = runner.invoke(scan, [
            "--watchlist", str(wl),
            "--data-dir", str(data_dir),
            "--now", "2024-06-09",
            # NOTE: no --run flag
        ])

        assert result.exit_code == 0, \
            f"Plan mode (no --run) should exit 0, got {result.exit_code}. Output: {result.output}"

    def test_validation_failure_exits_1(self, tmp_path: Path):
        """Malformed watchlist CSV causes --run to exit 1."""
        # Write a CSV missing required columns
        bad_path = tmp_path / "bad_watchlist.csv"
        with open(bad_path, "w", newline="", encoding="utf-8") as f:
            f.write("wrong_col\ngold\n")

        data_dir = tmp_path / "data"
        output_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(scan, [
            "--watchlist", str(bad_path),
            "--data-dir", str(data_dir),
            "--output", str(output_dir),
            "--run",
        ])

        assert result.exit_code == 1, \
            f"Malformed watchlist should exit 1 in --run mode, got {result.exit_code}. Output: {result.output}"
