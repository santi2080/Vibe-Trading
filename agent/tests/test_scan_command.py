"""Tests for scan.py Click CLI (CLI-01, CLI-02)."""
from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli.commands.scan import scan


class TestScanCommand:
    """Test the scan Click CLI command."""

    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _runner(self):
        return CliRunner()

    def test_help(self):
        runner = self._runner()
        result = runner.invoke(scan, ["--help"])
        assert result.exit_code == 0, f"stdout: {result.output}"
        assert "--watchlist" in result.output
        assert "--data-dir" in result.output
        assert "--output" in result.output
        assert "--format" in result.output
        assert "--run" in result.output

    def test_plan_mode_shows_table(self, tmp_path: Path):
        wl = tmp_path / "wl.csv"
        self._write_csv(wl, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        runner = self._runner()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
            result = runner.invoke(scan, ["--watchlist", str(wl), "--data-dir", str(data_dir)])
        assert result.exit_code == 0, f"stderr: {result.output}"
        assert "GC=F" in result.output

    def test_plan_mode_json_format(self, tmp_path: Path):
        wl = tmp_path / "wl.csv"
        self._write_csv(wl, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        runner = self._runner()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
            result = runner.invoke(scan, ["--watchlist", str(wl), "--data-dir", str(data_dir), "--format", "json"])
        assert result.exit_code == 0
        assert '"symbol"' in result.output or '"GC=F"' in result.output
        assert "summary" in result.output

    def test_run_mode_missing_watchlist_exits_1(self, tmp_path: Path):
        runner = self._runner()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=tmp_path / "nonexistent.csv"):
            result = runner.invoke(scan, ["--watchlist", str(tmp_path / "nonexistent.csv"), "--run"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_run_mode_validation_error_exits_1(self, tmp_path: Path):
        wl = tmp_path / "dupes.csv"
        self._write_csv(wl, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        runner = self._runner()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
            result = runner.invoke(scan, ["--watchlist", str(wl), "--run"])
        assert result.exit_code == 1
        assert "duplicate" in result.output.lower()

    def test_invalid_date_format_exits_1(self, tmp_path: Path):
        wl = tmp_path / "wl.csv"
        self._write_csv(wl, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        runner = self._runner()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
            result = runner.invoke(scan, ["--watchlist", str(wl), "--now", "not-a-date"])
        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    def test_run_mode_local_data_first_stub_message(self, tmp_path: Path):
        wl = tmp_path / "wl.csv"
        self._write_csv(wl, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        runner = self._runner()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=wl):
            result = runner.invoke(scan, ["--watchlist", str(wl), "--data-dir", str(data_dir), "--run"])
        assert result.exit_code == 0, f"output: {result.output}"
        assert "local-data" in result.output.lower() or "no remote" in result.output.lower()
