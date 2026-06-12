"""Market Structure Analyzer - Auxiliary indicator for MTES V4.

This module provides market structure analysis as a supplementary signal
without affecting the core scoring algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class SwingPoint:
    """A swing high or low point."""
    index: int
    price: float
    swing_type: Literal["HH", "LH", "HL", "LL"]


@dataclass
class TradingRange:
    """Trading range based on swing highs/lows."""
    high: float  # Upper bound (Swing High)
    low: float  # Lower bound (Swing Low)
    mid: float  # Middle of range
    width: float  # Absolute width
    width_pct: float  # Width as percentage
    position: float  # Current price position in range (0-1)
    near_support: bool  # Price near support (< 30% from bottom)
    near_resistance: bool  # Price near resistance (> 70% from top)
    breakout_up: bool  # Price broke above range
    breakout_down: bool  # Price broke below range

    def to_dict(self) -> dict:
        return {
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "mid": round(self.mid, 2),
            "width_pct": round(self.width_pct, 2),
            "position": round(self.position, 3),
            "near_support": self.near_support,
            "near_resistance": self.near_resistance,
            "breakout_up": self.breakout_up,
            "breakout_down": self.breakout_down,
        }


@dataclass
class MarketStructureSignal:
    """Market structure analysis result."""
    trend: Literal["BULL", "BEAR", "NEUTRAL"]
    structure: Literal["HH_HL", "LH_LL", "mixed", "insufficient"]
    confidence: float  # 0-1
    recent_swings: list[SwingPoint]
    last_swing_high: float | None
    last_swing_low: float | None
    trading_range: TradingRange | None = None  # Trading range analysis

    def to_dict(self) -> dict:
        return {
            "trend": self.trend,
            "structure": self.structure,
            "confidence": self.confidence,
            "last_swing_high": self.last_swing_high,
            "last_swing_low": self.last_swing_low,
            "trading_range": self.trading_range.to_dict() if self.trading_range else None,
        }


class MarketStructure:
    """Market Structure Analyzer.

    Detects swing highs/lows and determines trend direction from structure.
    This is an AUXILIARY indicator - it does not participate in core scoring.

    Trend determination:
    - BULL: Higher Highs (HH) + Higher Lows (HL)
    - BEAR: Lower Highs (LH) + Lower Lows (LL)
    - NEUTRAL: Mixed or insufficient structure
    """

    def __init__(self, lookback: int = 5, min_swings: int = 4):
        """Initialize MarketStructure.

        Args:
            lookback: Bars to check on each side for swing detection
            min_swings: Minimum swings needed for valid structure
        """
        self.lookback = lookback
        self.min_swings = min_swings

    def analyze(self, df: pd.DataFrame) -> MarketStructureSignal:
        """Analyze market structure.

        Args:
            df: OHLCV DataFrame

        Returns:
            MarketStructureSignal with structure analysis and trading range
        """
        if len(df) < 50:
            return MarketStructureSignal(
                trend="NEUTRAL",
                structure="insufficient",
                confidence=0.0,
                recent_swings=[],
                last_swing_high=None,
                last_swing_low=None,
            )

        swings = self._detect_swings(df)

        if len(swings) < self.min_swings:
            return MarketStructureSignal(
                trend="NEUTRAL",
                structure="insufficient",
                confidence=0.0,
                recent_swings=swings,
                last_swing_high=self._get_last_high(swings),
                last_swing_low=self._get_last_low(swings),
            )

        trend, structure, confidence = self._analyze_structure(swings)

        # Calculate trading range
        trading_range = self._calculate_trading_range(df, swings)

        return MarketStructureSignal(
            trend=trend,
            structure=structure,
            confidence=confidence,
            recent_swings=swings[-6:],  # Keep last 6 swings
            last_swing_high=self._get_last_high(swings),
            last_swing_low=self._get_last_low(swings),
            trading_range=trading_range,
        )

    def _detect_swings(self, df: pd.DataFrame) -> list[SwingPoint]:
        """Detect swing highs and lows using pivot point approach.

        Returns:
            List of SwingPoint sorted by index
        """
        highs = df['high'].values
        lows = df['low'].values
        n = len(df)

        swings: list[SwingPoint] = []
        last_high_idx = -self.lookback * 2
        last_low_idx = -self.lookback * 2

        for i in range(self.lookback, n - self.lookback):
            # Check for swing high
            if i - last_high_idx >= self.lookback:
                window = highs[i - self.lookback:i + self.lookback + 1]
                if highs[i] == max(window):
                    swing_type = self._classify_high(highs[i], swings)
                    swings.append(SwingPoint(index=i, price=float(highs[i]), swing_type=swing_type))
                    last_high_idx = i

            # Check for swing low
            if i - last_low_idx >= self.lookback:
                window = lows[i - self.lookback:i + self.lookback + 1]
                if lows[i] == min(window):
                    swing_type = self._classify_low(lows[i], swings)
                    swings.append(SwingPoint(index=i, price=float(lows[i]), swing_type=swing_type))
                    last_low_idx = i

        return sorted(swings, key=lambda s: s.index)

    def _classify_high(self, price: float, prev_swings: list[SwingPoint]) -> Literal["HH", "LH"]:
        """Classify swing high as HH or LH."""
        prev_highs = [s for s in prev_swings if s.swing_type in ("HH", "LH")]
        if not prev_highs:
            return "HH"
        return "HH" if price > prev_highs[-1].price else "LH"

    def _classify_low(self, price: float, prev_swings: list[SwingPoint]) -> Literal["HL", "LL"]:
        """Classify swing low as HL or LL."""
        prev_lows = [s for s in prev_swings if s.swing_type in ("HL", "LL")]
        if not prev_lows:
            return "HL"
        return "LL" if price < prev_lows[-1].price else "HL"

    def _analyze_structure(
        self, swings: list[SwingPoint]
    ) -> tuple[Literal["BULL", "BEAR", "NEUTRAL"], Literal["HH_HL", "LH_LL", "mixed"], float]:
        """Analyze swing sequence for trend direction."""
        # Get recent swings (alternating high/low)
        recent = swings[-8:] if len(swings) >= 8 else swings

        # Count structure types
        hh = sum(1 for s in recent if s.swing_type == "HH")
        hl = sum(1 for s in recent if s.swing_type == "HL")
        lh = sum(1 for s in recent if s.swing_type == "LH")
        ll = sum(1 for s in recent if s.swing_type == "LL")

        # Bullish structure: HH + HL pattern
        if hh >= 2 and hl >= 1:
            # Check if highs are actually higher
            highs = [s for s in recent if s.swing_type in ("HH", "LH")]
            lows = [s for s in recent if s.swing_type in ("HL", "LL")]

            if len(highs) >= 2 and len(lows) >= 1:
                # HH confirmation: each HH higher than previous
                hh_higher = all(
                    highs[i].price > highs[i - 1].price
                    for i in range(1, len(highs))
                )
                # HL confirmation: each HL higher than previous
                hl_higher = all(
                    lows[i].price > lows[i - 1].price
                    for i in range(1, len(lows))
                )

                if hh_higher and hl_higher:
                    return "BULL", "HH_HL", 0.85
                elif hh_higher or hl_higher:
                    return "BULL", "HH_HL", 0.70

        # Bearish structure: LH + LL pattern
        if lh >= 2 and ll >= 1:
            highs = [s for s in recent if s.swing_type in ("HH", "LH")]
            lows = [s for s in recent if s.swing_type in ("HL", "LL")]

            if len(highs) >= 1 and len(lows) >= 2:
                # LH confirmation: each LH lower than previous
                lh_lower = all(
                    lows[i].price < lows[i - 1].price
                    for i in range(1, len(lows))
                )
                # LL confirmation: each LL lower than previous
                ll_lower = all(
                    lows[i].price < lows[i - 1].price
                    for i in range(1, len(lows))
                )

                if lh_lower and ll_lower:
                    return "BEAR", "LH_LL", 0.85
                elif lh_lower or ll_lower:
                    return "BEAR", "LH_LL", 0.70

        return "NEUTRAL", "mixed", 0.40

    def _get_last_high(self, swings: list[SwingPoint]) -> float | None:
        """Get last swing high price."""
        highs = [s for s in swings if s.swing_type in ("HH", "LH")]
        return highs[-1].price if highs else None

    def _get_last_low(self, swings: list[SwingPoint]) -> float | None:
        """Get last swing low price."""
        lows = [s for s in swings if s.swing_type in ("HL", "LL")]
        return lows[-1].price if lows else None

    def _calculate_trading_range(
        self, df: pd.DataFrame, swings: list[SwingPoint]
    ) -> TradingRange | None:
        """Calculate trading range from swing highs/lows.

        The range is based on the most recent significant swing high and low.
        """
        high = self._get_last_high(swings)
        low = self._get_last_low(swings)

        if high is None or low is None:
            return None

        current_price = float(df['close'].iloc[-1])

        # Calculate range metrics
        width = high - low
        width_pct = (width / low) * 100 if low > 0 else 0
        mid = (high + low) / 2

        # Position in range (0 = at bottom, 1 = at top)
        position = (current_price - low) / width if width > 0 else 0.5

        # Near boundaries (within 30% of range)
        near_support = position < 0.30
        near_resistance = position > 0.70

        # Breakout detection (current bar exceeded range)
        breakout_high = float(df['high'].iloc[-1]) > high
        breakout_low = float(df['low'].iloc[-1]) < low

        return TradingRange(
            high=high,
            low=low,
            mid=mid,
            width=width,
            width_pct=width_pct,
            position=position,
            near_support=near_support,
            near_resistance=near_resistance,
            breakout_up=breakout_high,
            breakout_down=breakout_low,
        )
