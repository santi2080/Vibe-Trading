"""Tests for scan_validators.py (WLS-01)."""
from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from src.data.scan_validators import (
    REQUIRED_COLUMNS,
    SUPPORTED_MARKETS,
    validate_watchlist,
    ValidationIssue,
    ValidationResult,
)


class TestValidateWatchlist:
    """Test validate_watchlist() for all WLS-01 scenarios."""

    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        cols = list(rows[0].keys()) if rows else []
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)

    def test_missing_file(self):
        result = validate_watchlist("nonexistent_watchlist_abc123.csv")
        assert not result.valid
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message.lower()

    def test_missing_required_columns(self, tmp_path: Path):
        csv_path = tmp_path / "bad_cols.csv"
        self._write_csv(csv_path, [{"symbol": "GC=F", "market": "us_futures"}])
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert not result.valid
        assert any("missing" in e.message.lower() for e in result.errors)

    def test_empty_watchlist(self, tmp_path: Path):
        csv_path = tmp_path / "empty.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(REQUIRED_COLUMNS))
            writer.writeheader()
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert not result.valid
        assert any("empty" in e.message.lower() for e in result.errors)

    def test_duplicate_symbols(self, tmp_path: Path):
        csv_path = tmp_path / "dupes.csv"
        rows = [
            {"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
            {"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ]
        self._write_csv(csv_path, rows)
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert not result.valid
        assert any("duplicate" in e.message.lower() for e in result.errors)

    def test_fail_fast_on_duplicate(self, tmp_path: Path):
        csv_path = tmp_path / "dupes.csv"
        rows = [
            {"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
            {"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ]
        self._write_csv(csv_path, rows)
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path), fail_fast=True)
        assert not result.valid
        assert len(result.errors) >= 1

    def test_valid_watchlist(self, tmp_path: Path):
        csv_path = tmp_path / "valid.csv"
        rows = [
            {"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D,4H"},
            {"symbol": "SI=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "1D"},
        ]
        self._write_csv(csv_path, rows)
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert result.valid, f"Expected valid, got errors: {[e.message for e in result.errors]}"

    def test_unsupported_market_warning(self, tmp_path: Path):
        csv_path = tmp_path / "bad_market.csv"
        rows = [{"symbol": "X=BAD", "market": "unsupported_market_xyz", "exchange": "NA", "sector": "na", "timeframes": "1D-1H"}]
        self._write_csv(csv_path, rows)
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert result.valid  # warning, not error
        assert any("unsupported market" in w.message.lower() for w in result.warnings)

    def test_unsupported_timeframe_warning(self, tmp_path: Path):
        csv_path = tmp_path / "bad_tf.csv"
        rows = [{"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "999M-1H"}]
        self._write_csv(csv_path, rows)
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert result.valid  # warning, not error
        assert any("timeframe" in w.message.lower() for w in result.warnings)

    def test_timeframe_alias_normalization_no_error(self, tmp_path: Path):
        csv_path = tmp_path / "aliases.csv"
        rows = [
            {"symbol": "GC=F", "market": "us_futures", "exchange": "COMEX", "sector": "metals", "timeframes": "d1-h4"},
        ]
        self._write_csv(csv_path, rows)
        with patch("src.data.scan_validators._resolve_watchlist_path", return_value=csv_path):
            result = validate_watchlist(str(csv_path))
        assert result.valid  # d1->1d, h4->4h are aliases — no warning
