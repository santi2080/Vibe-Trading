"""Layer 0: Preprocessor for MTES v3.

This module handles data validation, quality checks, and ADX pre-filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import numpy as np

from .base import BaseLayer


@dataclass
class PreprocessorConfig:
    """Configuration for the Preprocessor layer.

    Attributes:
        adx_threshold: Minimum ADX value required (default: 20.0)
        min_data_points: Minimum number of data points required
        min_volume: Minimum average volume required (0 = no check)
        price_col: Column name for price data
    """
    adx_threshold: float = 20.0
    min_data_points: int = 200
    min_volume: float = 0.0
    price_col: str = 'close'


@dataclass
class PreprocessorResult:
    """Result from the Preprocessor layer.

    Attributes:
        passed: Whether the data passed all prefilter checks
        reason: Reason for failure if not passed
        adx_value: Calculated ADX value
        data_points: Number of data points
        avg_volume: Average volume (if available)
    """
    passed: bool
    reason: Optional[str] = None
    adx_value: float = 0.0
    data_points: int = 0
    avg_volume: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "passed": self.passed,
            "reason": self.reason,
            "adx_value": self.adx_value,
            "data_points": self.data_points,
            "avg_volume": self.avg_volume,
        }


class Preprocessor(BaseLayer):
    """Layer 0: Preprocessor for data quality and ADX filtering.

    This layer performs the following checks:
    1. Data integrity validation (required columns)
    2. Minimum data points check
    3. ADX pre-filtering (trend strength)
    4. Volume check (if configured)
    """

    def __init__(self, config: Optional[PreprocessorConfig] = None):
        """Initialize the Preprocessor.

        Args:
            config: Preprocessor configuration (uses defaults if not provided)
        """
        self.config = config or PreprocessorConfig()

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that the DataFrame has required columns and data.

        Args:
            df: OHLCV DataFrame

        Returns:
            True if all required columns exist and DataFrame is not empty
        """
        required_cols = ['open', 'high', 'low', 'close']
        return all(col in df.columns for col in required_cols) and len(df) > 0

    def _calculate_adx(self, df: pd.DataFrame) -> float:
        """Calculate ADX (Average Directional Index).

        Args:
            df: OHLCV DataFrame

        Returns:
            ADX value (0-100)
        """
        if len(df) < 14:
            return 0.0

        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        # Calculate True Range
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))

        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = high[0] - low[0]  # First value

        # Calculate Directional Movement
        up_move = np.diff(high, prepend=high[0])
        down_move = -np.diff(low, prepend=low[0])

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Smooth using Wilder's method
        period = 14
        alpha = 1.0 / period

        smoothed_tr = np.zeros_like(tr)
        smoothed_plus_dm = np.zeros_like(plus_dm)
        smoothed_minus_dm = np.zeros_like(minus_dm)

        smoothed_tr[period] = np.sum(tr[1:period + 1])
        smoothed_plus_dm[period] = np.sum(plus_dm[1:period + 1])
        smoothed_minus_dm[period] = np.sum(minus_dm[1:period + 1])

        for i in range(period + 1, len(tr)):
            smoothed_tr[i] = smoothed_tr[i - 1] - smoothed_tr[i - 1] * alpha + tr[i]
            smoothed_plus_dm[i] = smoothed_plus_dm[i - 1] - smoothed_plus_dm[i - 1] * alpha + plus_dm[i]
            smoothed_minus_dm[i] = smoothed_minus_dm[i - 1] - smoothed_minus_dm[i - 1] * alpha + minus_dm[i]

        # Calculate DI
        with np.errstate(divide='ignore', invalid='ignore'):
            plus_di = 100 * smoothed_plus_dm / np.where(smoothed_tr != 0, smoothed_tr, 1)
            minus_di = 100 * smoothed_minus_dm / np.where(smoothed_tr != 0, smoothed_tr, 1)

        # Calculate DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) != 0, plus_di + minus_di, 1)

        # Smooth DX to get ADX
        adx = np.zeros_like(dx)
        adx[period * 2] = np.mean(dx[period:period * 2])

        for i in range(period * 2 + 1, len(dx)):
            adx[i] = adx[i - 1] - adx[i - 1] * alpha + dx[i]

        return float(adx[-1]) if len(adx) > 0 else 0.0

    def analyze(self, df: pd.DataFrame, **kwargs) -> PreprocessorResult:
        """Perform pre-filtering analysis.

        Args:
            df: OHLCV DataFrame
            **kwargs: Additional arguments (ignored)

        Returns:
            PreprocessorResult with pass/fail and details
        """
        # 1. Data validation
        if not self.validate(df):
            return PreprocessorResult(
                passed=False,
                reason="invalid_data",
                data_points=len(df)
            )

        # 2. Data points check
        if len(df) < self.config.min_data_points:
            return PreprocessorResult(
                passed=False,
                reason="insufficient_data",
                data_points=len(df)
            )

        # 3. ADX pre-filtering
        adx_value = self._calculate_adx(df)
        if adx_value < self.config.adx_threshold:
            return PreprocessorResult(
                passed=False,
                reason="adx_below_threshold",
                adx_value=adx_value,
                data_points=len(df)
            )

        # 4. Volume check (if configured)
        avg_volume = 0.0
        if self.config.min_volume > 0 and 'volume' in df.columns:
            avg_volume = float(df['volume'].mean())
            if avg_volume < self.config.min_volume:
                return PreprocessorResult(
                    passed=False,
                    reason="low_volume",
                    adx_value=adx_value,
                    data_points=len(df),
                    avg_volume=avg_volume
                )

        return PreprocessorResult(
            passed=True,
            adx_value=adx_value,
            data_points=len(df),
            avg_volume=avg_volume
        )

    def filter_batch(self, data_dict: dict[str, pd.DataFrame]) -> dict[str, bool]:
        """Filter multiple symbols at once.

        Args:
            data_dict: Dictionary mapping symbol -> DataFrame

        Returns:
            Dictionary mapping symbol -> pass/fail
        """
        results = {}
        for symbol, df in data_dict.items():
            results[symbol] = self.analyze(df).passed
        return results
