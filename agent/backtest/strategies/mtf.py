"""Multi-Timeframe (MTF) Alignment System.

This module provides safe alignment of higher timeframe (HTF) indicators
to lower timeframe (LTF) data, preventing look-ahead bias.

Key Features:
1. Mandatory lag mechanism - HTF values are lagged by 1 bar
2. Backward merge - HTF bars align to completed LTF bars
3. Forward fill - HTF values fill forward for continuity

Usage:
    from agent.backtest.strategies.mtf import MTFAligner, MTFConfig

    aligner = MTFAligner(MTFConfig())
    aligned = aligner.align_htf_to_ltf(
        htf_data=d1_data,
        ltf_data=h1_data,
        htf_timeframe='1d',
        ltf_timeframe='1h'
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


class Timeframe(Enum):
    """Standard timeframe definitions."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN = "1M"

    @classmethod
    def get_seconds(cls, timeframe: str) -> int:
        """Get seconds for a timeframe string."""
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800,
            "1M": 2592000,
        }
        return mapping.get(timeframe, 86400)

    @classmethod
    def get_relative_factor(cls, htf: str, ltf: str) -> int:
        """Get the relative factor between timeframes.

        Example:
            1d / 1h = 24
            1h / 15m = 4
        """
        htf_seconds = cls.get_seconds(htf)
        ltf_seconds = cls.get_seconds(ltf)
        if ltf_seconds == 0:
            return 1
        return max(1, htf_seconds // ltf_seconds)


@dataclass
class MTFConfig:
    """Configuration for MTF alignment."""

    # Lag mechanism: shift HTF values by N bars to prevent look-ahead
    lag_bars: int = 1

    # Backward merge direction
    merge_direction: str = "backward"  # "backward" or "forward"

    # Forward fill for continuity
    fill_forward: bool = True

    # Fill limit (max bars to forward fill)
    fill_limit: int = 100

    # Require complete HTF bars
    require_complete_bars: bool = True

    # Auto-calculate warmup period
    auto_warmup: bool = True


@dataclass
class AlignmentResult:
    """Result of MTF alignment operation."""

    data: pd.DataFrame
    warmup_bars: int
    htf_period: int  # How many LTF bars per HTF bar
    alignment_method: str
    lookback_required: int  # Minimum LTF bars needed


class MTFAligner:
    """Aligns higher timeframe (HTF) data to lower timeframe (LTF) data.

    This class implements the three key mechanisms to prevent look-ahead bias:

    1. **Mandatory Lag**: HTF values are shifted by 1+ bars so that at any
       point in time, only the most recently CLOSED HTF bar is used.

    2. **Backward Merge**: Each LTF bar is assigned the HTF value of the
       HTF bar that was closed BEFORE or AT that LTF bar.

    3. **Forward Fill**: HTF values are filled forward to provide continuous
       values for LTF bars that fall within an open HTF bar.

    Example:
        D1 data aligned to H1:

        D1 Bar 1 (Jan 1-2)    D1 Bar 2 (Jan 3-4)
        |                      |
        v                      v
        H1 H1 H1 H1 H1 ... H1 H1 H1 H1 H1 ...
        (uses D1 Bar 1)      (uses D1 Bar 2, lagged by 1 bar)

    """

    def __init__(self, config: Optional[MTFConfig] = None):
        """Initialize MTF Aligner.

        Args:
            config: MTF alignment configuration
        """
        self.config = config or MTFConfig()

    def align_htf_to_ltf(
        self,
        htf_data: pd.DataFrame,
        ltf_data: pd.DataFrame,
        htf_timeframe: str,
        ltf_timeframe: str,
        htf_columns: Optional[List[str]] = None,
    ) -> AlignmentResult:
        """Align HTF data to LTF data.

        Args:
            htf_data: Higher timeframe DataFrame (e.g., daily)
            ltf_data: Lower timeframe DataFrame (e.g., hourly)
            htf_timeframe: HTF string (e.g., '1d', '4h')
            ltf_timeframe: LTF string (e.g., '1h', '15m')
            htf_columns: Columns to align (default: all except index)

        Returns:
            AlignmentResult with aligned data
        """
        # Validate inputs
        if htf_data is None or ltf_data is None:
            raise ValueError("Both htf_data and ltf_data must be provided")

        if len(htf_data) == 0 or len(ltf_data) == 0:
            raise ValueError("Both DataFrames must have data")

        # Determine columns to align
        if htf_columns is None:
            htf_columns = [c for c in htf_data.columns if c != "signal"]

        # Calculate alignment parameters
        htf_period = Timeframe.get_relative_factor(htf_timeframe, ltf_timeframe)
        warmup_bars = self._calculate_warmup(htf_period)

        # Step 1: Apply mandatory lag to HTF data
        htf_lagged = self._apply_lag(htf_data, htf_columns, htf_period)

        # Step 2: Backward merge HTF to LTF
        aligned = self._merge_backward(htf_lagged, ltf_data, htf_columns)

        # Step 3: Forward fill if enabled
        if self.config.fill_forward:
            aligned = self._forward_fill(aligned, htf_columns)

        return AlignmentResult(
            data=aligned,
            warmup_bars=warmup_bars,
            htf_period=htf_period,
            alignment_method="backward_lag",
            lookback_required=warmup_bars + htf_period,
        )

    def _calculate_warmup(self, htf_period: int) -> int:
        """Calculate warmup period for HTF alignment.

        The warmup period is the number of LTF bars needed before
        we have a valid HTF value. This accounts for:
        1. The lag mechanism (1+ bars)
        2. The HTF period (N LTF bars per HTF bar)

        Args:
            htf_period: Number of LTF bars per HTF bar

        Returns:
            Number of warmup bars
        """
        if self.config.auto_warmup:
            return self.config.lag_bars + htf_period
        return self.config.lag_bars

    def _apply_lag(
        self,
        htf_data: pd.DataFrame,
        columns: List[str],
        htf_period: int,
    ) -> pd.DataFrame:
        """Apply mandatory lag to HTF data.

        This shifts HTF values by lag_bars to ensure that at any LTF bar,
        we only use HTF values from already-closed HTF bars.

        Args:
            htf_data: HTF DataFrame
            columns: Columns to lag
            htf_period: HTF period in LTF bars

        Returns:
            Lagged HTF DataFrame
        """
        result = htf_data.copy()

        # Calculate lag in HTF bars (not LTF bars)
        # We need to lag by at least 1 complete HTF bar
        lag_htf_bars = max(1, self.config.lag_bars // htf_period + 1)

        for col in columns:
            if col in result.columns:
                result[col] = result[col].shift(lag_htf_bars)

        return result

    def _merge_backward(
        self,
        htf_lagged: pd.DataFrame,
        ltf_data: pd.DataFrame,
        htf_columns: List[str],
    ) -> pd.DataFrame:
        """Merge HTF data backward to LTF data.

        Each LTF bar gets the HTF value from the most recent
        closed HTF bar.

        Args:
            htf_lagged: Lagged HTF DataFrame
            ltf_data: LTF DataFrame
            htf_columns: Columns to merge

        Returns:
            LTF DataFrame with HTF columns added
        """
        # Create merged DataFrame starting with LTF
        result = ltf_data.copy()

        # Initialize HTF columns with NaN
        for col in htf_columns:
            result[f"htf_{col}"] = np.nan

        # Find HTF timestamps that fall within each LTF bar
        for i, ltf_ts in enumerate(ltf_data.index):
            # Find the most recent HTF bar that closed before this LTF bar
            valid_htf = htf_lagged[htf_lagged.index <= ltf_ts]

            if len(valid_htf) > 0:
                # Get the last valid HTF bar
                last_htf = valid_htf.iloc[-1]

                # Assign HTF values to this LTF bar
                for col in htf_columns:
                    if col in last_htf.index:
                        result.at[ltf_ts, f"htf_{col}"] = last_htf[col]

        return result

    def _forward_fill(
        self,
        aligned: pd.DataFrame,
        columns: List[str],
    ) -> pd.DataFrame:
        """Forward fill HTF values for continuity.

        Args:
            aligned: Aligned DataFrame
            columns: HTF columns to fill

        Returns:
            DataFrame with filled values
        """
        result = aligned.copy()

        htf_columns = [f"htf_{col}" for col in columns if f"htf_{col}" in result.columns]

        # Forward fill with limit
        for col in htf_columns:
            if col in result.columns:
                result[col] = result[col].ffill(limit=self.config.fill_limit)

        return result

    def get_warmup_bars(self, htf_timeframe: str, ltf_timeframe: str) -> int:
        """Get the number of warmup bars needed.

        Args:
            htf_timeframe: Higher timeframe
            ltf_timeframe: Lower timeframe

        Returns:
            Number of warmup bars
        """
        htf_period = Timeframe.get_relative_factor(htf_timeframe, ltf_timeframe)
        return self._calculate_warmup(htf_period)

    def validate_alignment(
        self,
        aligned: pd.DataFrame,
        htf_columns: List[str],
        warmup_bars: int,
    ) -> Dict[str, any]:
        """Validate the alignment result.

        Args:
            aligned: Aligned DataFrame
            htf_columns: HTF columns that were aligned
            warmup_bars: Expected warmup bars

        Returns:
            Validation report
        """
        htf_columns_check = [f"htf_{col}" for col in htf_columns if f"htf_{col}" in aligned.columns]

        # Count NaN values in warmup period
        warmup_nan = {}
        for col in htf_columns_check:
            warmup_nan[col] = aligned[col].iloc[:warmup_bars].isna().sum()

        # Check if warmup period has NaN (expected)
        warmup_valid = all(count == warmup_bars for count in warmup_nan.values())

        # Check if data period has fewer NaN
        data_period = aligned.iloc[warmup_bars:]
        data_nan = {}
        for col in htf_columns_check:
            data_nan[col] = data_period[col].isna().sum() / len(data_period) if len(data_period) > 0 else 1

        return {
            "warmup_bars": warmup_bars,
            "warmup_nan_count": warmup_nan,
            "warmup_valid": warmup_valid,
            "data_nan_ratio": data_nan,
            "total_bars": len(aligned),
            "valid_bars": len(aligned) - warmup_bars,
        }


class MTFComposer:
    """Composes multi-timeframe strategies.

    This class helps build strategies that use multiple timeframes:
    - High timeframe: trend direction (e.g., daily)
    - Medium timeframe: pullback detection (e.g., 4h)
    - Low timeframe: entry signals (e.g., 1h)

    Example:
        from agent.backtest.strategies.mtf import MTFComposer

        composer = MTFComposer()
        composer.add_timeframe('1d', trend_indicator='ema_50')
        composer.add_timeframe('4h', pullback_indicator='rsi')
        composer.add_timeframe('1h', entry_indicator='breakout')

        result = composer.run(df_d1, df_h4, df_h1)
    """

    def __init__(self, aligner: Optional[MTFAligner] = None):
        """Initialize MTF Composer.

        Args:
            aligner: MTFAligner instance
        """
        self.aligner = aligner or MTFAligner()
        self.timeframes: Dict[str, pd.DataFrame] = {}
        self.aligned_data: Dict[str, pd.DataFrame] = {}

    def add_timeframe(
        self,
        timeframe: str,
        data: pd.DataFrame,
        indicator_name: Optional[str] = None,
    ) -> "MTFComposer":
        """Add a timeframe to the composer.

        Args:
            timeframe: Timeframe string (e.g., '1d', '4h', '1h')
            data: DataFrame for this timeframe
            indicator_name: Optional name for the indicator

        Returns:
            Self for chaining
        """
        self.timeframes[timeframe] = data
        return self

    def align_timeframes(
        self,
        base_timeframe: str,
        target_timeframes: Optional[List[str]] = None,
    ) -> "MTFComposer":
        """Align all timeframes to the base timeframe.

        Args:
            base_timeframe: The lowest timeframe to align to
            target_timeframes: Timeframes to align (default: all except base)

        Returns:
            Self for chaining
        """
        if base_timeframe not in self.timeframes:
            raise ValueError(f"Base timeframe {base_timeframe} not found")

        if target_timeframes is None:
            target_timeframes = [tf for tf in self.timeframes if tf != base_timeframe]

        base_data = self.timeframes[base_timeframe]

        for tf in target_timeframes:
            if tf not in self.timeframes:
                continue

            # Determine which is HTF and which is LTF
            if Timeframe.get_relative_factor(tf, base_timeframe) > 1:
                # tf is higher timeframe
                result = self.aligner.align_htf_to_ltf(
                    htf_data=self.timeframes[tf],
                    ltf_data=base_data,
                    htf_timeframe=tf,
                    ltf_timeframe=base_timeframe,
                )
                self.aligned_data[tf] = result.data
            else:
                # tf is lower timeframe or same - just copy
                self.aligned_data[tf] = self.timeframes[tf].copy()

        # Add base timeframe
        self.aligned_data[base_timeframe] = base_data

        return self

    def get_aligned_data(self, timeframe: str) -> Optional[pd.DataFrame]:
        """Get aligned data for a timeframe.

        Args:
            timeframe: Timeframe string

        Returns:
            Aligned DataFrame or None
        """
        return self.aligned_data.get(timeframe)

    def get_composite_data(self) -> pd.DataFrame:
        """Get combined data from all timeframes.

        Returns:
            DataFrame with all timeframe data
        """
        if not self.aligned_data:
            raise ValueError("No aligned data. Call align_timeframes() first.")

        # Start with base timeframe
        base_tf = min(
            self.timeframes.keys(),
            key=lambda x: Timeframe.get_seconds(x)
        )

        result = self.aligned_data[base_tf].copy()

        # Add HTF columns from other timeframes
        for tf, data in self.aligned_data.items():
            if tf == base_tf:
                continue

            for col in data.columns:
                if col not in result.columns:
                    result[col] = data[col]

        return result
