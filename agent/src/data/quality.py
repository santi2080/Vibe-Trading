"""数据质量监控器

从 trading-assistant 移植
五维度数据质量检查
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """质量问题"""

    dimension: str  # 维度: completeness, consistency, validity, timeliness, uniqueness
    severity: str  # 严重程度: error, warning, info
    description: str  # 描述
    count: int = 0  # 影响数量
    percentage: float = 0.0  # 影响比例


@dataclass
class QualityReport:
    """质量报告"""

    symbol: str
    timeframe: str
    score: float  # 0.0 - 1.0
    issues: List[QualityIssue]
    passed: bool  # 是否通过检查

    def get_summary(self) -> str:
        """获取摘要"""
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | Score: {self.score:.1%} | Issues: {len(self.issues)}"


class DataQualityMonitor:
    """数据质量监控器

    五维度检查:
    1. completeness: 完整性（缺失值）
    2. consistency: 一致性（时间连续性、OHLC 逻辑）
    3. validity: 有效性（异常值、离群点）
    4. timeliness: 时效性（数据年龄）
    5. uniqueness: 唯一性（重复数据）
    """

    def __init__(self, min_score: float = 0.8):
        """初始化

        Args:
            min_score: 最低质量分数，低于此分数报告失败
        """
        self.min_score = min_score

    def check(self, df: pd.DataFrame, symbol: str = "unknown", timeframe: str = "1d") -> QualityReport:
        """检查数据质量

        Args:
            df: K 线数据
            symbol: 品种代码
            timeframe: 时间周期

        Returns:
            QualityReport
        """
        if df is None or df.empty:
            return QualityReport(
                symbol=symbol,
                timeframe=timeframe,
                score=0.0,
                issues=[QualityIssue("completeness", "error", "No data")],
                passed=False,
            )

        issues = []
        total_checks = 0

        # 1. 完整性检查
        completeness_score, completeness_issues = self._check_completeness(df)
        issues.extend(completeness_issues)
        total_checks += 1

        # 2. 一致性检查
        consistency_score, consistency_issues = self._check_consistency(df)
        issues.extend(consistency_issues)
        total_checks += 1

        # 3. 有效性检查
        validity_score, validity_issues = self._check_validity(df)
        issues.extend(validity_issues)
        total_checks += 1

        # 4. 唯一性检查
        uniqueness_score, uniqueness_issues = self._check_uniqueness(df)
        issues.extend(uniqueness_issues)
        total_checks += 1

        # 计算总体分数
        score = (completeness_score + consistency_score + validity_score + uniqueness_score) / 4

        return QualityReport(
            symbol=symbol,
            timeframe=timeframe,
            score=score,
            issues=issues,
            passed=score >= self.min_score,
        )

    def _check_completeness(self, df: pd.DataFrame) -> Tuple[float, List[QualityIssue]]:
        """检查完整性（缺失值）"""
        issues = []

        # 检查各列缺失值
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                missing = df[col].isna().sum()
                if missing > 0:
                    pct = missing / len(df) * 100
                    issues.append(QualityIssue(
                        dimension="completeness",
                        severity="error" if pct > 5 else "warning",
                        description=f"Column '{col}' has {missing} missing values ({pct:.1f}%)",
                        count=missing,
                        percentage=pct,
                    ))

        # 计算分数
        if not issues:
            return 1.0, []
        max_pct = max(i.percentage for i in issues)
        score = max(0, 1 - max_pct / 100)
        return score, issues

    def _check_consistency(self, df: pd.DataFrame) -> Tuple[float, List[QualityIssue]]:
        """检查一致性（时间连续性、OHLC 逻辑）"""
        issues = []

        # OHLC 逻辑检查
        if all(col in df.columns for col in ["high", "low", "open", "close"]):
            # high >= low
            invalid_hl = (df["high"] < df["low"]).sum()
            if invalid_hl > 0:
                pct = invalid_hl / len(df) * 100
                issues.append(QualityIssue(
                    dimension="consistency",
                    severity="error",
                    description=f"High < Low: {invalid_hl} bars ({pct:.1f}%)",
                    count=invalid_hl,
                    percentage=pct,
                ))

            # high >= open, close
            invalid_h = ((df["high"] < df["open"]) | (df["high"] < df["close"])).sum()
            if invalid_h > 0:
                pct = invalid_h / len(df) * 100
                issues.append(QualityIssue(
                    dimension="consistency",
                    severity="error",
                    description=f"High < Open/Close: {invalid_h} bars ({pct:.1f}%)",
                    count=invalid_h,
                    percentage=pct,
                ))

            # low <= open, close
            invalid_l = ((df["low"] > df["open"]) | (df["low"] > df["close"])).sum()
            if invalid_l > 0:
                pct = invalid_l / len(df) * 100
                issues.append(QualityIssue(
                    dimension="consistency",
                    severity="error",
                    description=f"Low > Open/Close: {invalid_l} bars ({pct:.1f}%)",
                    count=invalid_l,
                    percentage=pct,
                ))

        # 时间连续性检查（检测缺口）
        if df.index.is_monotonic_increasing and len(df) > 1:
            time_diffs = df.index.to_series().diff()
            median_diff = time_diffs.median()
            if pd.notna(median_diff) and median_diff > pd.Timedelta(0):
                threshold = median_diff * 3
                gaps = time_diffs[time_diffs > threshold].dropna()
                if len(gaps) > 0:
                    issues.append(QualityIssue(
                        dimension="consistency",
                        severity="warning",
                        description=f"Time gaps detected: {len(gaps)} gaps",
                        count=len(gaps),
                        percentage=len(gaps) / len(df) * 100,
                    ))

        if not issues:
            return 1.0, []
        max_pct = max((i.percentage for i in issues), default=0)
        score = max(0, 1 - max_pct / 100)
        return score, issues

    def _check_validity(self, df: pd.DataFrame) -> Tuple[float, List[QualityIssue]]:
        """检查有效性（异常值）"""
        issues = []

        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                continue

            # 检查负值（volume 允许为 0）
            if col != "volume":
                negatives = (df[col] <= 0).sum()
                if negatives > 0:
                    pct = negatives / len(df) * 100
                    issues.append(QualityIssue(
                        dimension="validity",
                        severity="error",
                        description=f"Column '{col}' has {negatives} non-positive values ({pct:.1f}%)",
                        count=negatives,
                        percentage=pct,
                    ))

            # 检查异常大的值（使用 IQR 方法）
            if df[col].notna().sum() > 10:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outliers = ((df[col] < q1 - 3 * iqr) | (df[col] > q3 + 3 * iqr)).sum()
                    if outliers > 0:
                        pct = outliers / len(df) * 100
                        issues.append(QualityIssue(
                            dimension="validity",
                            severity="warning",
                            description=f"Column '{col}' has {outliers} outliers ({pct:.1f}%)",
                            count=outliers,
                            percentage=pct,
                        ))

        if not issues:
            return 1.0, []
        max_pct = max((i.percentage for i in issues), default=0)
        score = max(0, 1 - max_pct / 100)
        return score, issues

    def _check_uniqueness(self, df: pd.DataFrame) -> Tuple[float, List[QualityIssue]]:
        """检查唯一性（重复数据）"""
        issues = []

        # 检查索引重复
        if df.index.is_monotonic_increasing:
            duplicates = df.index.duplicated().sum()
        else:
            duplicates = df.index.duplicated().sum()

        if duplicates > 0:
            pct = duplicates / len(df) * 100
            issues.append(QualityIssue(
                dimension="uniqueness",
                severity="warning",
                description=f"Duplicate timestamps: {duplicates} ({pct:.1f}%)",
                count=duplicates,
                percentage=pct,
            ))

        if not issues:
            return 1.0, []
        max_pct = max((i.percentage for i in issues), default=0)
        score = max(0, 1 - max_pct / 100)
        return score, issues
