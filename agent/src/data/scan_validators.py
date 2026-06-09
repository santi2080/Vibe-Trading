"""Watchlist validation for the daily scan CLI."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import path safety helper from existing tool (do NOT reimplement).
from src.tools.watchlist_tool import _resolve_watchlist_path

# Reuse market/timeframe constants from data health module.
from src.data.watchlist_data_health import MARKET_DIRS, TIMEFRAME_ALIASES


# --- Issue model -----------------------------------------------------------
@dataclass
class ValidationIssue:
    row_index: int | None  # None = file-level issue
    field: str
    symbol: str | None
    severity: str  # "error" | "warning"
    message: str


@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


# --- Public API -----------------------------------------------------------
REQUIRED_COLUMNS = frozenset({"symbol", "market", "exchange", "sector", "timeframes"})

SUPPORTED_MARKETS = frozenset(MARKET_DIRS.keys())


def validate_watchlist(
    watchlist_path: str,
    *,
    fail_fast: bool = False,
) -> ValidationResult:
    """Validate a watchlist CSV and return all issues.

    Args:
        watchlist_path: Path to the watchlist CSV.
        fail_fast: If True, raise on first file-level error instead of collecting.
    """
    issues: list[ValidationIssue] = []

    # 1. Path existence and sandbox safety
    try:
        resolved = _resolve_watchlist_path(watchlist_path)
    except ValueError as exc:
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(
                row_index=None, field="path", symbol=None,
                severity="error", message=str(exc),
            )],
        )

    if not resolved.exists():
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(
                row_index=None, field="path", symbol=None,
                severity="error", message=f"Watchlist file not found: {resolved}",
            )],
        )

    # 2. Required columns
    try:
        with open(resolved, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            raw_columns = frozenset(reader.fieldnames or [])
    except Exception as exc:
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(
                row_index=None, field="path", symbol=None,
                severity="error", message=f"Cannot read watchlist: {exc}",
            )],
        )

    missing_cols = REQUIRED_COLUMNS - raw_columns
    if missing_cols:
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(
                row_index=None, field="columns", symbol=None,
                severity="error",
                message=f"Missing required columns: {', '.join(sorted(missing_cols))}",
            )],
        )

    # 3. Row-level validation
    try:
        with open(resolved, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as exc:
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(
                row_index=None, field="path", symbol=None,
                severity="error", message=f"Cannot parse watchlist: {exc}",
            )],
        )

    # 3a. Empty list
    if not rows:
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(
                row_index=None, field="rows", symbol=None,
                severity="error", message="Watchlist is empty.",
            )],
        )

    # 3b. Duplicates
    seen: dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        sym = (row.get("symbol") or "").strip()
        if sym:
            if sym in seen:
                issues.append(ValidationIssue(
                    row_index=idx, field="symbol", symbol=sym,
                    severity="error",
                    message=f"Duplicate symbol '{sym}' (first seen at row {seen[sym]})",
                ))
                if fail_fast:
                    return ValidationResult(valid=False, issues=issues)
            else:
                seen[sym] = idx

    # 3c. Unsupported market
    for idx, row in enumerate(rows, start=1):
        market = (row.get("market") or "").strip().lower()
        if market and market not in SUPPORTED_MARKETS:
            issues.append(ValidationIssue(
                row_index=idx, field="market", symbol=row.get("symbol"),
                severity="warning",
                message=f"Unsupported market '{market}' — may not have local data. "
                        f"Supported: {', '.join(sorted(SUPPORTED_MARKETS))}",
            ))

    # 3d. Unsupported timeframe (check each timeframe in the comma-separated list)
    for idx, row in enumerate(rows, start=1):
        tf_raw = (row.get("timeframes") or "").strip()
        if tf_raw:
            for tf in tf_raw.split(","):
                tf = tf.strip()
                if tf and tf not in TIMEFRAME_ALIASES and tf not in {"1d", "1h", "4h", "1w"}:
                    issues.append(ValidationIssue(
                        row_index=idx, field="timeframes", symbol=row.get("symbol"),
                        severity="warning",
                        message=f"Unsupported timeframe '{tf}'. "
                                f"Supported: 1d, 1h, 4h, 1w (and aliases d1, h1, h4, w1, etc.)",
                    ))
                    break  # one warning per row per field

    return ValidationResult(
        valid=len([i for i in issues if i.severity == "error"]) == 0,
        issues=issues,
    )
