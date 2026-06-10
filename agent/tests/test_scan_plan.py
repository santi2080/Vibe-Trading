"""Tests for scan_plan.py (WLS-02, CLI-01)."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from src.data.scan_plan import (
    ScanPlan,
    SymbolPlan,
    build_scan_plan,
    format_plan_json,
    format_plan_table,
)


class TestScanPlan:
    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def test_build_scan_plan_basic(self, tmp_path: Path):
        wl_path = tmp_path / "wl.csv"
        self._write_csv(wl_path, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D-4H"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        plan = build_scan_plan(str(wl_path), data_dir=str(data_dir), scan_date=date(2026, 6, 9))

        assert plan.total_symbols == 1
        assert plan.by_market == {"us_futures": 1}
        sym = plan.symbols[0]
        assert sym.symbol == "GC=F"
        assert sym.timeframes == ["1d", "4h"]
        assert len(sym.cache_paths) == 2
        assert sym.output_path.name == "GC=F.json"

    def test_to_dict_json_roundtrip(self, tmp_path: Path):
        wl_path = tmp_path / "wl.csv"
        self._write_csv(wl_path, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        plan = build_scan_plan(str(wl_path), data_dir=str(data_dir), scan_date=date(2026, 6, 9))
        d = plan.to_dict()

        # Must be valid JSON
        parsed = json.loads(json.dumps(d))
        assert parsed["summary"]["total"] == 1
        assert parsed["symbols"][0]["symbol"] == "GC=F"
        assert parsed["symbols"][0]["timeframes"] == ["1d"]

    def test_format_plan_json_returns_string(self, tmp_path: Path):
        wl_path = tmp_path / "wl.csv"
        self._write_csv(wl_path, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        plan = build_scan_plan(str(wl_path), data_dir=str(data_dir), scan_date=date(2026, 6, 9))
        output = format_plan_json(plan)
        assert isinstance(output, str)
        parsed = json.loads(output)
        assert parsed["summary"]["total"] == 1

    def test_format_plan_table_returns_string(self, tmp_path: Path):
        wl_path = tmp_path / "wl.csv"
        self._write_csv(wl_path, [
            {"symbol": "GC=F", "name": "Gold", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ])
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        plan = build_scan_plan(str(wl_path), data_dir=str(data_dir), scan_date=date(2026, 6, 9))
        output = format_plan_table(plan)
        assert isinstance(output, str)
        assert "GC=F" in output
        assert "us_futures" in output
        assert "1d" in output.lower()
