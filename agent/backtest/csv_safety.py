"""CSV artifact safety helpers.

Backtest CSV artifacts are often opened in spreadsheet tools.  Strings that
start with formula characters can execute spreadsheet formulas, so sanitize
only at the serialization boundary while preserving in-memory calculation data.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_ARTIFACT_ROWS_ENV = "VIBE_TRADING_MAX_ARTIFACT_ROWS"
_DEFAULT_MAX_ARTIFACT_ROWS = 250_000


def _env_int(name: str, default: int) -> int:
    """Return a positive integer environment setting or its default."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def max_artifact_rows() -> int:
    """Return the configured maximum rows allowed for one CSV artifact."""
    return _env_int(_MAX_ARTIFACT_ROWS_ENV, _DEFAULT_MAX_ARTIFACT_ROWS)


def ensure_csv_row_limit(df: pd.DataFrame, artifact_name: str) -> None:
    """Raise when a CSV artifact would exceed the configured row cap."""
    limit = max_artifact_rows()
    rows = len(df)
    if rows > limit:
        raise ValueError(
            f"CSV artifact {artifact_name!r} has {rows} rows, exceeding limit {limit}. "
            f"Set {_MAX_ARTIFACT_ROWS_ENV} to adjust this limit."
        )


def safe_csv_filename(prefix: str, name: Any, suffix: str = ".csv") -> str:
    """Return a path-separator-free CSV artifact filename.

    Symbols can contain characters such as ``/`` (for example, crypto pairs).
    Artifact filenames must remain a single basename under the artifact
    directory, so collapse anything outside a conservative filename alphabet.
    """
    raw = str(name).strip() or "unknown"
    safe_name = _SAFE_FILENAME_RE.sub("_", raw).strip("._") or "unknown"
    return f"{prefix}{safe_name}{suffix}"

def sanitize_csv_value(value: Any) -> Any:
    """Return a spreadsheet-safe representation for CSV string values.

    Only strings are modified. Numeric negative values remain numeric because
    they do not carry formula semantics until coerced into text.
    """
    if not isinstance(value, str) or value == "":
        return value
    if value.startswith("'"):
        return value
    stripped = value.lstrip()
    if value.startswith(_FORMULA_PREFIXES) or stripped.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def sanitize_csv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with CSV string surfaces sanitized."""
    safe = df.copy()

    safe.columns = [sanitize_csv_value(col) if isinstance(col, str) else col for col in safe.columns]

    for col in safe.columns:
        series = safe[col]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            safe[col] = series.map(sanitize_csv_value)

    if safe.index.name is not None:
        safe.index.name = sanitize_csv_value(safe.index.name)
    if pd.api.types.is_object_dtype(safe.index) or pd.api.types.is_string_dtype(safe.index):
        safe.index = safe.index.map(sanitize_csv_value)

    return safe


def safe_to_csv(df: pd.DataFrame, path: str | Path, **kwargs: Any) -> None:
    """Write a DataFrame to CSV after bounds checks and formula sanitization."""
    ensure_csv_row_limit(df, Path(path).name)
    sanitize_csv_frame(df).to_csv(path, **kwargs)
