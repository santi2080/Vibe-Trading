"""Focused tests for scan_reporting (ART-01, RPT-01, RPT-02)."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from src.data.scan_reporting import (
    Manifest,
    MarkdownReportRenderer,
    run_reporting,
)
from src.data.scan_plan import ScanPlan, SymbolPlan, build_scan_plan
from src.data.scan_signal_buckets import ScanSignalReport


# --- Helper fixtures -------------------------------------------------------

def _make_mock_signal_report() -> ScanSignalReport:
    """Return a ScanSignalReport with all five buckets populated."""
    return ScanSignalReport(
        scan_info={
            "watchlist": "/tmp/test.csv",
            "watchlist_name": "test",
            "scan_date": "2024-01-01",
            "strategy": "test",
            "total_symbols": 5,
        },
        buckets_summary={
            "actionable": 2,
            "watch": 1,
            "risk_excluded": 1,
            "skipped": 1,
            "failed": 0,
            "total": 5,
        },
        buckets={
            "actionable": [
                {
                    "symbol": "AAPL",
                    "name": "Apple",
                    "market": "us_stocks",
                    "bucket": "actionable",
                    "bucket_reason": "BULL trend, confidence=0.70",
                    "trading_signal": {
                        "direction": "BULL",
                        "status": "VALID",
                        "confidence": 0.70,
                        "signal_score": 65.0,
                        "reasons": [],
                    },
                    "error": None,
                },
                {
                    "symbol": "MSFT",
                    "name": "Microsoft",
                    "market": "us_stocks",
                    "bucket": "actionable",
                    "bucket_reason": "BEAR trend, confidence=0.50",
                    "trading_signal": {
                        "direction": "BEAR",
                        "status": "VALID",
                        "confidence": 0.50,
                        "signal_score": 55.0,
                        "reasons": [],
                    },
                    "error": None,
                },
            ],
            "watch": [
                {
                    "symbol": "GOOG",
                    "name": "Alphabet",
                    "market": "us_stocks",
                    "bucket": "watch",
                    "bucket_reason": "BULL trend, low confidence=0.30",
                    "trading_signal": {
                        "direction": "BULL",
                        "status": "VALID",
                        "confidence": 0.30,
                        "signal_score": 40.0,
                        "reasons": [],
                    },
                    "error": None,
                },
            ],
            "risk_excluded": [
                {
                    "symbol": "TSLA",
                    "name": "Tesla",
                    "market": "us_stocks",
                    "bucket": "risk_excluded",
                    "bucket_reason": "low confidence=0.15",
                    "trading_signal": {
                        "direction": "BULL",
                        "status": "VALID",
                        "confidence": 0.15,
                        "signal_score": 20.0,
                        "reasons": [],
                    },
                    "error": None,
                },
            ],
            "skipped": [
                {
                    "symbol": "NVDA",
                    "name": "NVIDIA",
                    "market": "us_stocks",
                    "bucket": "skipped",
                    "bucket_reason": "parquet missing",
                    "trading_signal": None,
                    "error": None,
                },
            ],
            "failed": [],
        },
        metadata={"strategy": "test", "sources": [], "version": "1.0.0"},
    )


def _make_mock_health_report(status: str = "PASS") -> dict:
    """Return a mock DataHealthReport dict."""
    return {
        "status": status,
        "total_checks": 10,
        "blocking_failures": 0 if status != "FAIL" else 3,
        "warnings": 1 if status == "WARNING" else 0,
        "gate": {
            "status": status,
            "can_backtest": status != "FAIL",
            "blocking_failures": 0 if status != "FAIL" else 3,
            "warnings": 1 if status == "WARNING" else 0,
            "total_checks": 10,
        },
        "items": [],
    }


def _make_minimal_plan(tmp_path: Path) -> ScanPlan:
    """Create a minimal ScanPlan in tmp_path."""
    wl_path = tmp_path / "wl.csv"
    with open(wl_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name", "market"])
        writer.writeheader()
        writer.writerow({"symbol": "AAPL", "name": "Apple", "market": "us_stocks"})

    plan = build_scan_plan(
        watchlist_path=str(wl_path),
        data_dir=str(tmp_path / "data"),
        output_dir=str(tmp_path / "output"),
        scan_date=date(2024, 1, 1),
    )
    return plan


# --- TestManifest (ART-01) ------------------------------------------------

class TestManifest:
    """Test the Manifest dataclass."""

    def test_manifest_to_dict_schema(self):
        manifest = Manifest(
            scan_date="2024-01-01",
            watchlist_name="test.csv",
            version="1.0.0",
            artifacts={"data_health": "data_health.json"},
            scan_info={"watchlist": "/path/to/wl.csv"},
            total_symbols=5,
        )
        d = manifest.to_dict()
        assert "scan_date" in d
        assert "watchlist_name" in d
        assert "version" in d
        assert "artifacts" in d
        assert "scan_info" in d
        assert "total_symbols" in d
        assert d["scan_date"] == "2024-01-01"
        assert d["total_symbols"] == 5

    def test_manifest_to_json_writes_file(self, tmp_path: Path):
        manifest = Manifest(
            scan_date="2024-01-01",
            watchlist_name="test.csv",
            artifacts={"data_health": "data_health.json"},
            total_symbols=3,
        )
        path = tmp_path / "manifest.json"
        manifest.to_json(path)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["scan_date"] == "2024-01-01"
        assert data["total_symbols"] == 3

    def test_manifest_artifacts_contains_required_keys(self):
        manifest = Manifest(
            scan_date="2024-01-01",
            watchlist_name="test.csv",
            artifacts={
                "data_health": "data_health.json",
                "scan_results": "scan_results.json",
                "report": "report.md",
            },
            total_symbols=0,
        )
        assert "data_health" in manifest.artifacts
        assert "scan_results" in manifest.artifacts
        assert "report" in manifest.artifacts


# --- TestMarkdownReportRenderer (RPT-01, RPT-02) -------------------------

class TestMarkdownReportRenderer:
    """Test the MarkdownReportRenderer class."""

    def test_render_contains_all_sections(self, tmp_path: Path):
        plan = _make_minimal_plan(tmp_path)
        renderer = MarkdownReportRenderer(
            scan_plan=plan,
            output_dir=tmp_path,
            scan_date="2024-01-01",
            signal_report=_make_mock_signal_report(),
            health_report_dict=_make_mock_health_report("PASS"),
        )
        md = renderer.render()
        assert "# Daily Scan Report" in md
        assert "Data Health" in md
        assert "Actionable" in md
        assert "Watch" in md
        assert "Risk" in md
        assert "Skipped" in md
        assert "Failed" in md
        assert "Artifacts" in md

    def test_render_stops_on_health_fail(self, tmp_path: Path):
        plan = _make_minimal_plan(tmp_path)
        renderer = MarkdownReportRenderer(
            scan_plan=plan,
            output_dir=tmp_path,
            scan_date="2024-01-01",
            signal_report=_make_mock_signal_report(),
            health_report_dict=_make_mock_health_report("FAIL"),
        )
        md = renderer.render()
        # FAIL: report must show the blocked message and stop before candidates
        assert "FAIL" in md
        assert ("blocked" in md.lower() or "block" in md.lower())
        # Candidates section should not appear after a FAIL stop
        lines = md.splitlines()
        fail_idx = next((i for i, l in enumerate(lines) if "FAIL" in l), -1)
        actionable_idx = next((i for i, l in enumerate(lines) if "Actionable" in l), -1)
        assert actionable_idx == -1 or actionable_idx < fail_idx

    def test_render_avoids_trading_advice(self, tmp_path: Path):
        plan = _make_minimal_plan(tmp_path)
        renderer = MarkdownReportRenderer(
            scan_plan=plan,
            output_dir=tmp_path,
            scan_date="2024-01-01",
            signal_report=_make_mock_signal_report(),
            health_report_dict=_make_mock_health_report("PASS"),
        )
        md = renderer.render().lower()
        forbidden = ["buy", "sell", "hold", "best configuration", "rank",
                     "performance metric", "win rate", "sharpe"]
        for term in forbidden:
            assert term not in md, f"Report contains forbidden term: {term}"

    def test_render_from_loaded_artifacts(self, tmp_path: Path):
        plan = _make_minimal_plan(tmp_path)
        # Write scan_results.json manually
        results_path = tmp_path / "scan_results.json"
        report = _make_mock_signal_report()
        report.to_json(results_path)

        # Write data_health.json manually
        health_path = tmp_path / "data_health.json"
        health_path.write_text(json.dumps(_make_mock_health_report("PASS")), encoding="utf-8")

        # Create renderer without passing signal_report / health_report_dict
        renderer = MarkdownReportRenderer(
            scan_plan=plan,
            output_dir=tmp_path,
            scan_date="2024-01-01",
            signal_report=None,
            health_report_dict=None,
        )
        renderer.load_artifacts()

        assert renderer.signal_report is not None
        assert renderer.health_report_dict is not None
        md = renderer.render()
        assert "# Daily Scan Report" in md
        assert "AAPL" in md

    def test_artifact_links_present(self, tmp_path: Path):
        plan = _make_minimal_plan(tmp_path)
        renderer = MarkdownReportRenderer(
            scan_plan=plan,
            output_dir=tmp_path,
            scan_date="2024-01-01",
            signal_report=_make_mock_signal_report(),
            health_report_dict=_make_mock_health_report("PASS"),
        )
        md = renderer.render()
        assert "data_health.json" in md
        assert "scan_results.json" in md
        assert "manifest.json" in md
        assert "report.md" in md


# --- TestRunReporting (ART-01, RPT-02) -----------------------------------

class TestRunReporting:
    """Test the run_reporting orchestrator."""

    def test_run_reporting_writes_manifest_and_report(self, tmp_path: Path):
        plan = _make_minimal_plan(tmp_path)

        # Write prerequisites so renderer can load them
        results_path = tmp_path / "scan_results.json"
        _make_mock_signal_report().to_json(results_path)
        health_path = tmp_path / "data_health.json"
        health_path.write_text(json.dumps(_make_mock_health_report("PASS")), encoding="utf-8")

        manifest = run_reporting(
            plan,
            tmp_path,
            scan_date="2024-01-01",
            format="json",
            console=None,
        )

        manifest_path = tmp_path / "manifest.json"
        report_path = tmp_path / "report.md"
        assert manifest_path.exists(), "manifest.json not written"
        assert report_path.exists(), "report.md not written"

        # Verify manifest content
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["scan_date"] == "2024-01-01"
        assert "artifacts" in data
        assert data["artifacts"]["data_health"] == "data_health.json"
        assert data["artifacts"]["scan_results"] == "scan_results.json"
        assert data["artifacts"]["report"] == "report.md"

        # Verify report content
        report_md = report_path.read_text(encoding="utf-8")
        assert "# Daily Scan Report" in report_md
        assert "AAPL" in report_md

    def test_manifest_written_before_gate(self, tmp_path: Path):
        """Verify manifest.json is written (not report.md) when called before gate."""
        plan = _make_minimal_plan(tmp_path)

        manifest = run_reporting(
            plan,
            tmp_path,
            scan_date="2024-01-01",
            format="json",
            console=None,
        )

        manifest_path = tmp_path / "manifest.json"
        report_path = tmp_path / "report.md"

        # manifest.json must exist
        assert manifest_path.exists()

        # report.md may exist but gate data is missing so it won't have candidates
        # This verifies manifest is written independently of report rendering
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_data["scan_date"] == "2024-01-01"
        assert manifest_data["watchlist_name"] == plan.watchlist_name
