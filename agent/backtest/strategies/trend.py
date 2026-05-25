"""Trend Strategy - Identifies market direction using trend indicators.

Trend strategies determine the primary direction of the market using
various technical indicators like moving averages, ADX, and MACD.

---
# SKILL Metadata
name: trend_ema_adx
category: trend
tags: [trend, ema, adx, multi_timeframe]
timeframes: [1d, 4h, 1h]
markets: [cn_futures, us_futures, a_stock, us_stock, crypto]
parameters:
  ema_fast:
    type: int
    default: 20
    description: Fast EMA period
  ema_slow:
    type: int
    default: 50
    description: Slow EMA period
  adx_period:
    type: int
    default: 14
    description: ADX calculation period
  adx_threshold:
    type: float
    default: 25.0
    description: Minimum ADX for trend confirmation
version: "1.0.0"
---
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import BaseStrategy, StrategyType, StrategySignal


@dataclass
class TrendParameters:
    """Parameters for trend strategies."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    adx_period: int = 14
    adx_threshold: float = 25.0
    ema_fast: int = 20
    ema_slow: int = 50


class TrendEmaAdxStrategy(BaseStrategy):
    """Trend strategy using EMA crossover with ADX confirmation.

    Entry rules:
    - Long: EMA_fast > EMA_slow AND ADX > threshold (strong trend)
    - Short: EMA_fast < EMA_slow AND ADX > threshold

    Exit rules:
    - Trend reversal (EMA crossover)
    - ADX drops below threshold (weak trend)
    """

    def __init__(self, parameters: Optional[TrendParameters | Dict] = None):
        """Initialize EMA ADX strategy.

        Args:
            parameters: Strategy parameters (uses defaults if not provided)
        """
        if parameters is None:
            params = TrendParameters()
        elif isinstance(parameters, dict):
            params = TrendParameters(**parameters)
        else:
            params = parameters

        super().__init__(
            name="trend_ema_adx",
            strategy_type=StrategyType.TREND,
            parameters={
                "ema_fast": params.ema_fast,
                "ema_slow": params.ema_slow,
                "adx_period": params.adx_period,
                "adx_threshold": params.adx_threshold,
            },
        )
        self.params = params
        self.tags = ["trend", "ema", "adx", "multi_timeframe"]
        self.timeframes = ["1d", "4h", "1h"]
        self.supported_markets = ["cn_futures", "us_futures", "a_stock", "us_stock", "crypto"]

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate EMA and ADX indicators."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # EMA calculations
        ema_fast = close.ewm(span=self.params.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.params.ema_slow, adjust=False).mean()

        # ADX calculation
        adx = self._calculate_adx(high, low, close, self.params.adx_period)
        plus_di = self._calculate_directional_indicator(
            high, low, close, self.params.adx_period, direction="positive"
        )
        minus_di = self._calculate_directional_indicator(
            high, low, close, self.params.adx_period, direction="negative"
        )

        return {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
        }

    def _calculate_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Calculate Average Directional Index (ADX)."""
        # True Range
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        # Directional Movement
        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        # Smoothed DM
        smooth_plus_dm = plus_dm.rolling(window=period).mean()
        smooth_minus_dm = minus_dm.rolling(window=period).mean()

        # Directional Indicators
        plus_di = 100 * (smooth_plus_dm / atr)
        minus_di = 100 * (smooth_minus_dm / atr)

        # DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def _calculate_directional_indicator(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int,
        direction: str,
    ) -> pd.Series:
        """Calculate directional indicators (+DI, -DI)."""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        up_move = high.diff()
        down_move = -low.diff()

        if direction == "positive":
            dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        else:
            dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        smooth_dm = dm.rolling(window=period).mean()
        di = 100 * (smooth_dm / atr)

        return di

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate trend signals based on EMA and ADX."""
        ema_fast = indicators["ema_fast"]
        ema_slow = indicators["ema_slow"]
        adx = indicators["adx"]

        # Initialize signals
        signals = pd.Series(0, index=df.index)

        # Strong trend conditions
        strong_uptrend = (ema_fast > ema_slow) & (adx > self.params.adx_threshold)
        strong_downtrend = (ema_fast < ema_slow) & (adx > self.params.adx_threshold)

        # Generate signals
        signals[strong_uptrend] = 1
        signals[strong_downtrend] = -1

        return signals


class TrendMacdStrategy(BaseStrategy):
    """Trend strategy using MACD (Moving Average Convergence Divergence).

    Entry rules:
    - Long: MACD line crosses above signal line AND MACD > 0
    - Short: MACD line crosses below signal line AND MACD < 0
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        """Initialize MACD strategy.

        Args:
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period
        """
        super().__init__(
            name="trend_macd",
            strategy_type=StrategyType.TREND,
            parameters={
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period,
            },
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate MACD indicators."""
        close = df["close"]

        # MACD calculation
        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate MACD crossover signals."""
        macd = indicators["macd"]
        signal = indicators["signal"]

        # Crossover detection
        macd_above = macd > signal
        macd_below = macd < signal

        # Previous state (handle NaN)
        prev_above = macd_above.shift(1).fillna(False).astype(bool)

        # Signals
        signals = pd.Series(0, index=df.index)

        # Long: MACD crosses above signal AND MACD > 0
        long_condition = macd_above & ~prev_above & (macd > 0)
        signals[long_condition] = 1

        # Short: MACD crosses below signal AND MACD < 0
        short_condition = macd_below & prev_above & (macd < 0)
        signals[short_condition] = -1

        return signals


class TrendDualEmaStrategy(BaseStrategy):
    """Simple dual EMA crossover strategy.

    Entry rules:
    - Long: Fast EMA crosses above Slow EMA
    - Short: Fast EMA crosses below Slow EMA
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        """Initialize dual EMA strategy.

        Args:
            fast_period: Fast EMA period
            slow_period: Slow EMA period
        """
        super().__init__(
            name="trend_dual_ema",
            strategy_type=StrategyType.TREND,
            parameters={"fast_period": fast_period, "slow_period": slow_period},
        )
        self.fast_period = fast_period
        self.slow_period = slow_period

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate dual EMA indicators."""
        close = df["close"]

        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()

        return {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate EMA crossover signals."""
        ema_fast = indicators["ema_fast"]
        ema_slow = indicators["ema_slow"]

        # Trend direction (handle NaN)
        above = (ema_fast > ema_slow).fillna(False)
        prev_above = above.shift(1).fillna(False)

        signals = pd.Series(0, index=df.index)

        # Long: Fast crosses above Slow
        signals[above & ~prev_above] = 1

        # Short: Fast crosses below Slow
        signals[~above & prev_above] = -1

        return signals
