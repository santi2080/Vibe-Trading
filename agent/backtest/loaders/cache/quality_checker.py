"""Data quality checker for validating market data

Provides 5-dimensional data quality checks:
1. Completeness - No missing values
2. Consistency - OHLC relationships are valid
3. Timeliness - Data is not stale
4. Accuracy - Values are within reasonable ranges
5. Uniqueness - No duplicate timestamps

Usage:
    from agent.backtest.loaders.cache.quality_checker import DataQualityChecker

    checker = DataQualityChecker()

    # Check data quality
    report = checker.check(df, symbol="BTC-USDT")

    # Auto-fix common issues
    fixed_df = checker.auto_fix(df)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """Represents a data quality issue

    Attributes:
        dimension: Quality dimension (completeness, consistency, etc.)
        severity: Issue severity (error, warning, info)
        message: Human-readable description
        column: Affected column (if applicable)
        row_count: Number of affected rows
        examples: Example values (if applicable)
    """

    dimension: str
    severity: str  # "error", "warning", "info"
    message: str
    column: Optional[str] = None
    row_count: int = 0
    examples: List = field(default_factory=list)


@dataclass
class QualityReport:
    """Data quality report

    Attributes:
        symbol: Security symbol
        timestamp: When the check was performed
        passed: Whether all checks passed
        issues: List of QualityIssue objects
        completeness: Completeness check results
        consistency: Consistency check results
        timeliness: Timeliness check results
        accuracy: Accuracy check results
        uniqueness: Uniqueness check results
        fixed_count: Number of issues auto-fixed
    """

    symbol: str
    timestamp: datetime
    passed: bool = True
    issues: List[QualityIssue] = field(default_factory=list)
    completeness: Dict = field(default_factory=dict)
    consistency: Dict = field(default_factory=dict)
    timeliness: Dict = field(default_factory=dict)
    accuracy: Dict = field(default_factory=dict)
    uniqueness: Dict = field(default_factory=dict)
    fixed_count: int = 0

    def add_issue(self, issue: QualityIssue) -> None:
        """Add a quality issue"""
        self.issues.append(issue)
        if issue.severity in ("error", "warning"):
            self.passed = False

    def get_summary(self) -> str:
        """Get a human-readable summary"""
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"# Data Quality Report: {self.symbol}",
            f"Status: {status}",
            f"Checked: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## Issues ({len(self.issues)})",
        ]

        if not self.issues:
            lines.append("No issues found.")
        else:
            for issue in self.issues:
                severity_icon = {"error": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "❓")
                lines.append(f"{severity_icon} [{issue.severity.upper()}] {issue.message}")
                if issue.column:
                    lines.append(f"   Column: {issue.column}, Rows: {issue.row_count}")

        lines.extend([
            "",
            "## Dimensions",
            f"- Completeness: {self.completeness.get('status', 'unknown')}",
            f"- Consistency: {self.consistency.get('status', 'unknown')}",
            f"- Timeliness: {self.timeliness.get('status', 'unknown')}",
            f"- Accuracy: {self.accuracy.get('status', 'unknown')}",
            f"- Uniqueness: {self.uniqueness.get('status', 'unknown')}",
        ])

        if self.fixed_count > 0:
            lines.extend([
                "",
                "## Auto-fix",
                f"Fixed {self.fixed_count} issues automatically.",
            ])

        return "\n".join(lines)


class DataQualityChecker:
    """Data quality checker for market data

    Provides comprehensive quality checks across 5 dimensions:
    1. Completeness - No missing values
    2. Consistency - OHLC relationships are valid
    3. Timeliness - Data is not stale
    4. Accuracy - Values are within reasonable ranges
    5. Uniqueness - No duplicate timestamps
    """

    def __init__(
        self,
        max_missing_pct: float = 0.05,
        max_duplicate_pct: float = 0.01,
        max_staleness_hours: int = 24,
    ):
        """Initialize data quality checker

        Args:
            max_missing_pct: Maximum allowed missing value percentage (default 5%)
            max_duplicate_pct: Maximum allowed duplicate percentage (default 1%)
            max_staleness_hours: Maximum data age in hours before warning
        """
        self.max_missing_pct = max_missing_pct
        self.max_duplicate_pct = max_duplicate_pct
        self.max_staleness_hours = max_staleness_hours

    def check(self, df: pd.DataFrame, symbol: str = "unknown") -> QualityReport:
        """Perform comprehensive quality check

        Args:
            df: DataFrame to check (should have DatetimeIndex)
            symbol: Security symbol for reporting

        Returns:
            QualityReport with all check results
        """
        report = QualityReport(symbol=symbol, timestamp=datetime.now())

        if df is None or df.empty:
            report.add_issue(QualityIssue(
                dimension="all",
                severity="error",
                message="DataFrame is empty",
            ))
            return report

        # Run all checks
        report.completeness = self._check_completeness(df, report)
        report.consistency = self._check_consistency(df, report)
        report.timeliness = self._check_timeliness(df, report)
        report.accuracy = self._check_accuracy(df, report)
        report.uniqueness = self._check_uniqueness(df, report)

        return report

    def _check_completeness(self, df: pd.DataFrame, report: QualityReport) -> Dict:
        """Check data completeness (no missing values)"""
        result = {
            "status": "passed",
            "total_rows": len(df),
            "total_columns": len(df.columns),
        }

        # Check for missing values
        missing = df.isnull().sum()
        missing_pct = missing / len(df) * 100

        result["missing_columns"] = {}
        for col in df.columns:
            if missing[col] > 0:
                pct = missing_pct[col]
                result["missing_columns"][col] = {
                    "count": int(missing[col]),
                    "percentage": float(pct),
                }

                severity = "error" if pct > self.max_missing_pct * 100 else "warning"
                report.add_issue(QualityIssue(
                    dimension="completeness",
                    severity=severity,
                    message=f"Missing values in column '{col}'",
                    column=col,
                    row_count=int(missing[col]),
                    examples=[float(df[col].dropna().iloc[0])] if not df[col].dropna().empty else [],
                ))

        total_missing = missing.sum()
        total_missing_pct = total_missing / (len(df) * len(df.columns)) * 100
        result["total_missing"] = int(total_missing)
        result["total_missing_pct"] = float(total_missing_pct)

        if total_missing > 0:
            result["status"] = "warning" if total_missing_pct <= self.max_missing_pct * 100 else "failed"

        return result

    def _check_consistency(self, df: pd.DataFrame, report: QualityReport) -> Dict:
        """Check OHLC consistency"""
        result: Dict = {"status": "passed", "issues": []}

        required_cols = ["open", "high", "low", "close"]
        available_cols = [c for c in required_cols if c in df.columns]

        if len(available_cols) < 4:
            result["status"] = "skipped"
            result["message"] = "Not all OHLC columns present"
            return result

        issues = []

        # Check High >= Low
        high_low_violations = (df["high"] < df["low"]).sum()
        if high_low_violations > 0:
            issues.append({
                "type": "high_less_than_low",
                "count": int(high_low_violations),
            })
            report.add_issue(QualityIssue(
                dimension="consistency",
                severity="error",
                message=f"High < Low in {high_low_violations} rows",
                row_count=int(high_low_violations),
            ))

        # Check High >= Open and High >= Close
        for col in ["open", "close"]:
            violations = (df["high"] < df[col]).sum()
            if violations > 0:
                issues.append({
                    "type": f"high_less_than_{col}",
                    "count": int(violations),
                })
                report.add_issue(QualityIssue(
                    dimension="consistency",
                    severity="warning",
                    message=f"High < {col.capitalize()} in {violations} rows",
                    column="high",
                    row_count=int(violations),
                ))

        # Check Low <= Open and Low <= Close
        for col in ["open", "close"]:
            violations = (df["low"] > df[col]).sum()
            if violations > 0:
                issues.append({
                    "type": f"low_greater_than_{col}",
                    "count": int(violations),
                })
                report.add_issue(QualityIssue(
                    dimension="consistency",
                    severity="warning",
                    message=f"Low > {col.capitalize()} in {violations} rows",
                    column="low",
                    row_count=int(violations),
                ))

        # Check for negative prices
        for col in available_cols:
            negatives = (df[col] < 0).sum()
            if negatives > 0:
                issues.append({
                    "type": f"negative_{col}",
                    "count": int(negatives),
                })
                report.add_issue(QualityIssue(
                    dimension="consistency",
                    severity="error",
                    message=f"Negative {col} values in {negatives} rows",
                    column=col,
                    row_count=int(negatives),
                ))

        result["issues"] = issues
        if issues:
            result["status"] = "failed" if any(i["count"] > 0 for i in issues) else "warning"

        return result

    def _check_timeliness(self, df: pd.DataFrame, report: QualityReport) -> Dict:
        """Check data timeliness (is data stale?)"""
        result: Dict = {"status": "passed"}

        if not isinstance(df.index, pd.DatetimeIndex):
            result["status"] = "skipped"
            result["message"] = "Index is not DatetimeIndex"
            return result

        now = datetime.now()
        last_timestamp = df.index.max()
        age_hours = (now - last_timestamp).total_seconds() / 3600

        result["last_timestamp"] = str(last_timestamp)
        result["age_hours"] = float(age_hours)
        result["max_staleness_hours"] = self.max_staleness_hours

        if age_hours > self.max_staleness_hours:
            result["status"] = "warning"
            report.add_issue(QualityIssue(
                dimension="timeliness",
                severity="warning",
                message=f"Data is {age_hours:.1f} hours old (threshold: {self.max_staleness_hours}h)",
                row_count=len(df),
            ))

        return result

    def _check_accuracy(self, df: pd.DataFrame, report: QualityReport) -> Dict:
        """Check data accuracy (values in reasonable ranges)"""
        result: Dict = {"status": "passed", "issues": []}

        issues = []

        # Check for extreme price changes (>50% in single bar)
        if all(col in df.columns for col in ["close", "open"]):
            pct_change = ((df["close"] - df["open"]) / df["open"] * 100).abs()
            extreme_changes = (pct_change > 50).sum()
            if extreme_changes > 0:
                issues.append({
                    "type": "extreme_price_change",
                    "count": int(extreme_changes),
                })
                report.add_issue(QualityIssue(
                    dimension="accuracy",
                    severity="warning",
                    message=f"Extreme price change (>50%) in {extreme_changes} rows",
                    row_count=int(extreme_changes),
                ))

        # Check for zero volume (may indicate missing data)
        if "volume" in df.columns:
            zero_volume = (df["volume"] == 0).sum()
            zero_volume_pct = zero_volume / len(df) * 100
            if zero_volume_pct > 10:
                issues.append({
                    "type": "zero_volume",
                    "count": int(zero_volume),
                    "percentage": float(zero_volume_pct),
                })
                report.add_issue(QualityIssue(
                    dimension="accuracy",
                    severity="info",
                    message=f"Zero volume in {zero_volume} rows ({zero_volume_pct:.1f}%)",
                    column="volume",
                    row_count=int(zero_volume),
                ))

        result["issues"] = issues
        if issues:
            result["status"] = "warning"

        return result

    def _check_uniqueness(self, df: pd.DataFrame, report: QualityReport) -> Dict:
        """Check for duplicate timestamps"""
        result: Dict = {"status": "passed"}

        if not isinstance(df.index, pd.DatetimeIndex):
            result["status"] = "skipped"
            result["message"] = "Index is not DatetimeIndex"
            return result

        duplicates = df.index.duplicated().sum()
        duplicates_pct = duplicates / len(df) * 100

        result["duplicate_count"] = int(duplicates)
        result["duplicate_pct"] = float(duplicates_pct)

        if duplicates > 0:
            result["status"] = "warning" if duplicates_pct <= self.max_duplicate_pct * 100 else "failed"
            severity = "warning" if duplicates_pct <= self.max_duplicate_pct * 100 else "error"
            report.add_issue(QualityIssue(
                dimension="uniqueness",
                severity=severity,
                message=f"Duplicate timestamps in {duplicates} rows ({duplicates_pct:.2f}%)",
                row_count=int(duplicates),
            ))

        return result

    def auto_fix(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Automatically fix common data quality issues

        Args:
            df: DataFrame to fix

        Returns:
            Tuple of (fixed DataFrame, number of fixes applied)
        """
        if df is None or df.empty:
            return df, 0

        df = df.copy()
        fixes_applied = 0

        # 1. Remove duplicate timestamps (keep first)
        if isinstance(df.index, pd.DatetimeIndex):
            duplicates_before = df.index.duplicated().sum()
            if duplicates_before > 0:
                df = df[~df.index.duplicated(keep="first")]
                fixes_applied += 1
                logger.info(f"Auto-fixed: removed {duplicates_before} duplicate timestamps")

        # 2. Fill missing values with forward fill (for OHLC)
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                missing_before = df[col].isnull().sum()
                if missing_before > 0:
                    df[col] = df[col].ffill()
                    # If still have NaN at start, use backfill
                    df[col] = df[col].bfill()
                    fixes_applied += 1
                    logger.info(f"Auto-fixed: filled {missing_before} missing {col} values")

        # 3. Fix OHLC consistency
        if all(col in df.columns for col in ["open", "high", "low", "close"]):
            # Ensure High is the maximum
            df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
            # Ensure Low is the minimum
            df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
            fixes_applied += 1
            logger.info("Auto-fixed: ensured OHLC consistency")

        return df, fixes_applied
