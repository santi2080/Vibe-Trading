"""Tests for CSV artifact formula-injection protection."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.csv_safety import (
    safe_csv_filename,
    sanitize_csv_frame,
    sanitize_csv_value,
    safe_to_csv,
)


def test_sanitize_csv_value_prefixes_formula_strings() -> None:
    assert sanitize_csv_value("=IMPORTXML('x')") == "'=IMPORTXML('x')"
    assert sanitize_csv_value("+SUM(1,2)") == "'+SUM(1,2)"
    assert sanitize_csv_value("@HYPERLINK('x')") == "'@HYPERLINK('x')"
    assert sanitize_csv_value("  =SUM(1,2)") == "'  =SUM(1,2)"


def test_sanitize_csv_value_preserves_safe_values_and_numbers() -> None:
    assert sanitize_csv_value("normal") == "normal"
    assert sanitize_csv_value("'already escaped") == "'already escaped"
    assert sanitize_csv_value(-1.23) == -1.23
    assert sanitize_csv_value(42) == 42


def test_sanitize_csv_frame_sanitizes_cells_columns_and_index() -> None:
    df = pd.DataFrame(
        {"=col": ["@cell", -1.23], "normal": ["ok", "+bad"]},
        index=pd.Index(["=idx", "safe"], name="@index"),
    )

    safe = sanitize_csv_frame(df)

    assert list(safe.columns) == ["'=col", "normal"]
    assert safe.index.name == "'@index"
    assert list(safe.index) == ["'=idx", "safe"]
    assert safe.iloc[0, 0] == "'@cell"
    assert safe.iloc[1, 0] == -1.23
    assert safe.iloc[1, 1] == "'+bad"
    assert df.iloc[0, 0] == "@cell"  # original frame is not mutated

def test_safe_csv_filename_removes_path_separators() -> None:
    assert safe_csv_filename("ohlcv_", "BTC/USDT") == "ohlcv_BTC_USDT.csv"
    assert safe_csv_filename("ohlcv_", "../evil") == "ohlcv_evil.csv"


def test_safe_to_csv_writes_sanitized_output(tmp_path) -> None:
    path = tmp_path / "artifact.csv"
    df = pd.DataFrame({"symbol": ["=BAD"], "value": [-1.23]})

    safe_to_csv(df, path, index=False)

    text = path.read_text(encoding="utf-8")
    assert "'=BAD" in text
    assert "-1.23" in text


def test_safe_to_csv_rejects_rows_over_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_TRADING_MAX_ARTIFACT_ROWS", "1")
    path = tmp_path / "too_large.csv"
    df = pd.DataFrame({"value": [1, 2]})

    with pytest.raises(ValueError, match="exceeding limit 1"):
        safe_to_csv(df, path, index=False)

    assert not path.exists()
