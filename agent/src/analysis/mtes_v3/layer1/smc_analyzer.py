"""Layer 1: SMC (Smart Money Concepts) Market Structure Analysis.

This module implements swing detection, BOS (Break of Structure),
and MSS (Market Structure Shift) detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd
import numpy as np

from ..base import BaseLayer


@dataclass
class Swing:
    """Swing high/low point.

    Attributes:
        index: Bar index in the DataFrame
        timestamp: Timestamp of the swing
        price: Price at the swing point
        swing_type: Swing classification (HH, LH, HL, LL)
    """
    index: int
    timestamp: pd.Timestamp
    price: float
    swing_type: Literal["HH", "LH", "HL", "LL"]

    def is_high(self) -> bool:
        """Check if this is a swing high."""
        return self.swing_type in ["HH", "LH"]

    def is_low(self) -> bool:
        """Check if this is a swing low."""
        return self.swing_type in ["HL", "LL"]


@dataclass
class MarketStructureResult:
    """Result from SMC Market Structure analysis.

    Attributes:
        trend: Detected trend direction
        confidence: Confidence level (0-1)
        swings: List of detected swing points
        bos_confirmed: Whether Break of Structure is confirmed
        mss_confirmed: Whether Market Structure Shift is confirmed
        last_swing_high: Most recent swing high price
        last_swing_low: Most recent swing low price
        liquidity_sweeps: List of detected liquidity sweeps
    """
    trend: Literal["BULL", "BEAR", "NEUTRAL"]
    confidence: float
    swings: list[Swing] = field(default_factory=list)
    bos_confirmed: bool = False
    mss_confirmed: bool = False
    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    liquidity_sweeps: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "trend": self.trend,
            "confidence": self.confidence,
            "swings": [
                {
                    "index": s.index,
                    "timestamp": str(s.timestamp),
                    "price": s.price,
                    "swing_type": s.swing_type,
                }
                for s in self.swings
            ],
            "bos_confirmed": self.bos_confirmed,
            "mss_confirmed": self.mss_confirmed,
            "last_swing_high": self.last_swing_high,
            "last_swing_low": self.last_swing_low,
            "liquidity_sweeps": self.liquidity_sweeps,
        }


class SwingDetector:
    """Detects swing highs and lows in price data.

    A swing high is a point where the price is higher than surrounding bars.
    A swing low is a point where the price is lower than surrounding bars.
    """

    def __init__(self, lookback: int = 5, min_bars_between: int = 3):
        """Initialize SwingDetector.

        Args:
            lookback: Number of bars to check on each side (default: 5)
            min_bars_between: Minimum bars between swings (default: 3)
        """
        self.lookback = lookback
        self.min_bars_between = min_bars_between

    def detect(self, df: pd.DataFrame) -> list[Swing]:
        """Detect all swing highs and lows.

        Args:
            df: OHLCV DataFrame

        Returns:
            List of Swing points sorted by index
        """
        swings = []
        highs = df['high'].values
        lows = df['low'].values
        timestamps = df.index.tolist()
        last_swing_idx = -self.min_bars_between  # Ensure first swing is allowed

        for i in range(self.lookback, len(df) - self.lookback):
            # Check if enough bars since last swing
            if i - last_swing_idx < self.min_bars_between:
                continue

            # Get the window of prices
            window_highs = highs[i - self.lookback:i + self.lookback + 1]
            window_lows = lows[i - self.lookback:i + self.lookback + 1]

            current_high = highs[i]
            current_low = lows[i]

            # Check for swing high (HH or LH)
            if current_high == max(window_highs):
                swing_type = self._classify_high(i, swings, highs)
                swings.append(Swing(
                    index=i,
                    timestamp=pd.Timestamp(timestamps[i]) if not isinstance(timestamps[i], pd.Timestamp) else timestamps[i],
                    price=float(current_high),
                    swing_type=swing_type,
                ))
                last_swing_idx = i

            # Check for swing low (HL or LL)
            elif current_low == min(window_lows):
                swing_type = self._classify_low(i, swings, lows)
                swings.append(Swing(
                    index=i,
                    timestamp=pd.Timestamp(timestamps[i]) if not isinstance(timestamps[i], pd.Timestamp) else timestamps[i],
                    price=float(current_low),
                    swing_type=swing_type,
                ))
                last_swing_idx = i

        return sorted(swings, key=lambda s: s.index)

    def _classify_high(self, idx: int, prev_swings: list[Swing], highs: np.ndarray) -> str:
        """Classify a swing high as HH (Higher High) or LH (Lower High).

        Args:
            idx: Current bar index
            prev_swings: Previously detected swings
            highs: Array of high prices

        Returns:
            "HH" for higher high, "LH" for lower high
        """
        prev_highs = [s for s in prev_swings if s.is_high()]
        if not prev_highs:
            return "HH"  # First high is always HH

        last_high_price = prev_highs[-1].price
        return "HH" if highs[idx] > last_high_price else "LH"

    def _classify_low(self, idx: int, prev_swings: list[Swing], lows: np.ndarray) -> str:
        """Classify a swing low as HL (Higher Low) or LL (Lower Low).

        Args:
            idx: Current bar index
            prev_swings: Previously detected swings
            lows: Array of low prices

        Returns:
            "HL" for higher low, "LL" for lower low
        """
        prev_lows = [s for s in prev_swings if s.is_low()]
        if not prev_lows:
            return "HL"  # First low is always HL

        last_low_price = prev_lows[-1].price
        return "LL" if lows[idx] < last_low_price else "HL"


class SMCAnalyzer(BaseLayer):
    """SMC (Smart Money Concepts) Market Structure Analyzer.

    This analyzer identifies market structure through:
    - Swing detection (HH, HL, LH, LL)
    - Trend direction determination
    - BOS (Break of Structure) detection
    - MSS (Market Structure Shift) detection
    - Liquidity sweep detection
    """

    def __init__(self, swing_lookback: int = 5, swing_min_bars: int = 3):
        """Initialize SMCAnalyzer.

        Args:
            swing_lookback: Lookback period for swing detection (default: 5)
            swing_min_bars: Minimum bars between swings (default: 3)
        """
        self.swing_detector = SwingDetector(
            lookback=swing_lookback,
            min_bars_between=swing_min_bars
        )

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that the DataFrame has sufficient data.

        Args:
            df: OHLCV DataFrame

        Returns:
            True if data is sufficient for analysis
        """
        return len(df) >= 50

    def analyze(self, df: pd.DataFrame, **kwargs) -> MarketStructureResult:
        """Perform complete SMC analysis.

        Args:
            df: OHLCV DataFrame
            **kwargs: Additional arguments

        Returns:
            MarketStructureResult with trend, swings, and signals
        """
        # 1. Detect swings
        swings = self.swing_detector.detect(df)

        if len(swings) < 4:
            return MarketStructureResult(
                trend="NEUTRAL",
                confidence=0.0,
                swings=swings,
            )

        # 2. Determine trend
        trend, confidence = self._determine_trend(swings)

        # 3. Detect BOS
        bos_confirmed = self._detect_bos(swings, trend)

        # 4. Detect MSS
        mss_confirmed = self._detect_mss(swings, trend)

        # 5. Get recent swing levels
        recent_highs = [s for s in swings if s.is_high()]
        recent_lows = [s for s in swings if s.is_low()]
        last_swing_high = recent_highs[-1].price if recent_highs else None
        last_swing_low = recent_lows[-1].price if recent_lows else None

        # 6. Detect liquidity sweeps (simplified)
        liquidity_sweeps = self._detect_sweeps(df, swings)

        return MarketStructureResult(
            trend=trend,
            confidence=confidence,
            swings=swings,
            bos_confirmed=bos_confirmed,
            mss_confirmed=mss_confirmed,
            last_swing_high=last_swing_high,
            last_swing_low=last_swing_low,
            liquidity_sweeps=liquidity_sweeps,
        )

    def _determine_trend(self, swings: list[Swing]) -> tuple[str, float]:
        """Determine the trend direction from swings.

        Rules:
        - BULL: HH and HL both making higher highs and higher lows
        - BEAR: LH and LL both making lower highs and lower lows
        - NEUTRAL: Mixed or insufficient swings

        Args:
            swings: List of detected swings

        Returns:
            Tuple of (trend, confidence)
        """
        highs = [s for s in swings if s.is_high()]
        lows = [s for s in swings if s.is_low()]

        if len(highs) < 2 or len(lows) < 2:
            return "NEUTRAL", 0.0

        # Get recent swings
        recent_highs = highs[-3:]  # Last 3 highs
        recent_lows = lows[-3:]  # Last 3 lows

        # Check for uptrend: HH > prev HH and HL > prev HL
        hh_higher = all(highs[i].price > highs[i - 1].price for i in range(1, len(recent_highs)))
        hl_higher = all(lows[i].price > lows[i - 1].price for i in range(1, len(recent_lows)))

        if hh_higher and hl_higher:
            return "BULL", 0.8

        # Check for downtrend: LH < prev LH and LL < prev LL
        lh_lower = all(highs[i].price < highs[i - 1].price for i in range(1, len(recent_highs)))
        ll_lower = all(lows[i].price < lows[i - 1].price for i in range(1, len(recent_lows)))

        if lh_lower and ll_lower:
            return "BEAR", 0.8

        # Mixed signals
        return "NEUTRAL", 0.3

    def _detect_bos(self, swings: list[Swing], trend: str) -> bool:
        """Detect Break of Structure.

        BOS occurs when price breaks above/below the previous swing high/low
        in the direction of the trend.

        Args:
            swings: List of detected swings
            trend: Current trend direction

        Returns:
            True if BOS is confirmed
        """
        if trend == "NEUTRAL" or len(swings) < 4:
            return False

        highs = [s for s in swings if s.is_high()]
        lows = [s for s in swings if s.is_low()]

        if trend == "BULL" and len(highs) >= 2:
            # In uptrend, BOS = breaking above previous high
            return highs[-1].price > highs[-2].price
        elif trend == "BEAR" and len(lows) >= 2:
            # In downtrend, BOS = breaking below previous low
            return lows[-1].price < lows[-2].price

        return False

    def _detect_mss(self, swings: list[Swing], trend: str) -> bool:
        """Detect Market Structure Shift.

        MSS occurs when the structure changes (e.g., in an uptrend,
        price breaks below the previous swing low, indicating potential reversal).

        Args:
            swings: List of detected swings
            trend: Current trend direction

        Returns:
            True if MSS is detected
        """
        if len(swings) < 4:
            return False

        highs = [s for s in swings if s.is_high()]
        lows = [s for s in swings if s.is_low()]

        if trend == "BULL" and len(lows) >= 2:
            # In uptrend, MSS = breaking below previous low
            return lows[-1].price < lows[-2].price
        elif trend == "BEAR" and len(highs) >= 2:
            # In downtrend, MSS = breaking above previous high
            return highs[-1].price > highs[-2].price

        return False

    def _detect_sweeps(self, df: pd.DataFrame, swings: list[Swing]) -> list[dict]:
        """Detect liquidity sweeps (wicks that exceed swing levels).

        Args:
            df: OHLCV DataFrame
            swings: List of detected swings

        Returns:
            List of detected liquidity sweeps
        """
        sweeps = []
        # Simplified implementation - look for wicks that exceed recent highs/lows
        if len(swings) < 2:
            return sweeps

        # Check for wicks exceeding recent highs
        recent_high = max(s.price for s in swings if s.swing_type == "HH")
        recent_low = min(s.price for s in swings if s.swing_type == "HL")

        # Check last few bars for sweeps
        for i in range(max(0, len(df) - 10), len(df)):
            wick_high = df['high'].iloc[i]
            wick_low = df['low'].iloc[i]

            # Check for sweep above recent high
            if wick_high > recent_high * 1.001:  # 0.1% threshold
                sweeps.append({
                    "type": "high_sweep",
                    "index": i,
                    "timestamp": str(df.index[i]),
                    "wick_high": float(wick_high),
                    "sweep_target": float(recent_high),
                })

            # Check for sweep below recent low
            if wick_low < recent_low * 0.999:  # 0.1% threshold
                sweeps.append({
                    "type": "low_sweep",
                    "index": i,
                    "timestamp": str(df.index[i]),
                    "wick_low": float(wick_low),
                    "sweep_target": float(recent_low),
                })

        return sweeps
