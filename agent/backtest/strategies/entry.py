"""Entry Strategy - Generates precise entry signals with confirmation.

Entry strategies combine trend and pullback signals to generate
precise entry signals with proper risk management.

---
# SKILL Metadata
name: breakout_entry
category: entry
tags: [entry, breakout, volume, atr]
timeframes: [1h, 4h]
markets: [cn_futures, us_futures, a_stock, us_stock, crypto]
parameters:
  breakout_period:
    type: int
    default: 20
    description: Lookback period for breakout detection
  volume_multiplier:
    type: float
    default: 1.5
    description: Minimum volume spike multiplier
  atr_period:
    type: int
    default: 14
    description: ATR calculation period
  atr_multiplier:
    type: float
    default: 2.0
    description: ATR multiplier for stop loss
version: "1.0.0"
---
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from . import BaseStrategy, StrategyType


@dataclass
class EntryParameters:
    """Parameters for entry strategies."""

    breakout_period: int = 20
    volume_multiplier: float = 1.5
    atr_period: int = 14
    atr_multiplier: float = 2.0
    min_volume: float = 100000


class BreakoutEntryStrategy(BaseStrategy):
    """Breakout entry strategy with volume confirmation.

    Entry rules:
    - Long: Price breaks above N-period high with volume spike
    - Short: Price breaks below N-period low with volume spike

    Uses ATR for stop loss placement.
    """

    def __init__(self, parameters: Optional[EntryParameters] = None):
        """Initialize breakout strategy.

        Args:
            parameters: Strategy parameters (uses defaults if not provided)
        """
        params = parameters or EntryParameters()
        super().__init__(
            name="entry_breakout",
            strategy_type=StrategyType.ENTRY,
            parameters={
                "breakout_period": params.breakout_period,
                "volume_multiplier": params.volume_multiplier,
                "atr_period": params.atr_period,
            },
        )
        self.params = params
        self.tags = ["entry", "breakout", "volume", "atr"]
        self.timeframes = ["1h", "4h"]
        self.supported_markets = ["cn_futures", "us_futures", "a_stock", "us_stock", "crypto"]

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate breakout indicators."""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        volume = df.get("volume", pd.Series(1, index=df.index))

        # Rolling high/low
        rolling_high = high.rolling(window=self.params.breakout_period).max()
        rolling_low = low.rolling(window=self.params.breakout_period).min()

        # Volume average
        volume_avg = volume.rolling(window=self.params.breakout_period).mean()

        # ATR
        tr1 = high - low
        tr2 = np.abs(high - close.shift())
        tr3 = np.abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.params.atr_period).mean()

        # Volume ratio
        volume_ratio = volume / volume_avg

        return {
            "rolling_high": rolling_high,
            "rolling_low": rolling_low,
            "volume_ratio": volume_ratio,
            "atr": atr,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate breakout entry signals."""
        close = df["close"]
        rolling_high = indicators["rolling_high"]
        rolling_low = indicators["rolling_low"]
        volume_ratio = indicators["volume_ratio"]

        signals = pd.Series(0, index=df.index)

        # Long: Breakout above high with volume confirmation
        long_breakout = close > rolling_high.shift(1)
        volume_confirm = volume_ratio > self.params.volume_multiplier

        signals[long_breakout & volume_confirm] = 1

        # Short: Breakout below low with volume confirmation
        short_breakout = close < rolling_low.shift(1)

        signals[short_breakout & volume_confirm] = -1

        return signals


class VolumeSpikeEntryStrategy(BaseStrategy):
    """Volume spike entry strategy.

    Entry rules:
    - Long: Volume exceeds N * average with price rise
    - Short: Volume exceeds N * average with price drop
    """

    def __init__(
        self,
        volume_period: int = 20,
        spike_multiplier: float = 2.0,
    ):
        """Initialize volume spike strategy.

        Args:
            volume_period: Period for volume average
            spike_multiplier: Multiplier for volume spike threshold
        """
        super().__init__(
            name="entry_volume_spike",
            strategy_type=StrategyType.ENTRY,
            parameters={
                "volume_period": volume_period,
                "spike_multiplier": spike_multiplier,
            },
        )
        self.volume_period = volume_period
        self.spike_multiplier = spike_multiplier

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate volume indicators."""
        volume = df.get("volume", pd.Series(1, index=df.index))
        close = df["close"]

        # Volume average
        volume_avg = volume.rolling(window=self.volume_period).mean()

        # Volume ratio
        volume_ratio = volume / volume_avg

        # Price change
        price_change = close.pct_change()

        return {
            "volume_avg": volume_avg,
            "volume_ratio": volume_ratio,
            "price_change": price_change,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate volume spike signals."""
        volume_ratio = indicators["volume_ratio"]
        price_change = indicators["price_change"]

        signals = pd.Series(0, index=df.index)

        # Volume spike with bullish price action
        long_condition = (volume_ratio > self.spike_multiplier) & (price_change > 0.01)
        signals[long_condition] = 1

        # Volume spike with bearish price action
        short_condition = (volume_ratio > self.spike_multiplier) & (price_change < -0.01)
        signals[short_condition] = -1

        return signals


class VwapEntryStrategy(BaseStrategy):
    """VWAP (Volume Weighted Average Price) entry strategy.

    Entry rules:
    - Long: Price crosses above VWAP with increasing VWAP slope
    - Short: Price crosses below VWAP with decreasing VWAP slope
    """

    def __init__(self, lookback_minutes: int = 390):
        """Initialize VWAP strategy.

        Args:
            lookback_minutes: Minutes to calculate VWAP (default: full trading day)
        """
        super().__init__(
            name="entry_vwap",
            strategy_type=StrategyType.ENTRY,
            parameters={"lookback_minutes": lookback_minutes},
        )
        self.lookback_minutes = lookback_minutes

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate VWAP indicator."""
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        volume = df.get("volume", pd.Series(1, index=df.index))

        # VWAP: cumulative sum of (typical_price * volume) / cumulative sum of volume
        cumulative_tpv = (typical_price * volume).cumsum()
        cumulative_vol = volume.cumsum()
        vwap = cumulative_tpv / cumulative_vol

        # VWAP slope (trend)
        vwap_slope = vwap.diff()

        return {
            "vwap": vwap,
            "vwap_slope": vwap_slope,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate VWAP crossover signals."""
        close = df["close"]
        vwap = indicators["vwap"]
        vwap_slope = indicators["vwap_slope"]

        signals = pd.Series(0, index=df.index)

        # Previous position
        prev_above = (close.shift(1) > vwap.shift(1))
        curr_above = (close > vwap)

        # Long: Cross above VWAP with positive slope
        signals[(curr_above & ~prev_above) & (vwap_slope > 0)] = 1

        # Short: Cross below VWAP with negative slope
        signals[(~curr_above & prev_above) & (vwap_slope < 0)] = -1

        return signals


class SignalConfluenceStrategy(BaseStrategy):
    """Signal confluence strategy combining multiple indicators.

    Entry rules:
    - Long: Multiple indicators agree (trend + momentum + volume)
    - Short: Multiple indicators agree on bearish signal

    This is a meta-strategy that combines signals from other strategies.
    """

    def __init__(
        self,
        trend_ema_fast: int = 20,
        trend_ema_slow: int = 50,
        rsi_period: int = 14,
        volume_period: int = 20,
    ):
        """Initialize confluence strategy.

        Args:
            trend_ema_fast: Fast EMA period
            trend_ema_slow: Slow EMA period
            rsi_period: RSI period
            volume_period: Volume average period
        """
        super().__init__(
            name="entry_confluence",
            strategy_type=StrategyType.ENTRY,
            parameters={
                "trend_ema_fast": trend_ema_fast,
                "trend_ema_slow": trend_ema_slow,
                "rsi_period": rsi_period,
                "volume_period": volume_period,
            },
        )
        self.ema_fast = trend_ema_fast
        self.ema_slow = trend_ema_slow
        self.rsi_period = rsi_period
        self.volume_period = volume_period

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate all confluence indicators."""
        close = df["close"]
        volume = df.get("volume", pd.Series(1, index=df.index))

        # EMA
        ema_fast = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow, adjust=False).mean()

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # Volume
        volume_avg = volume.rolling(window=self.volume_period).mean()
        volume_ratio = volume / volume_avg

        # Trend signal (1 = up, -1 = down)
        trend = pd.Series(0, index=df.index)
        trend[ema_fast > ema_slow] = 1
        trend[ema_fast < ema_slow] = -1

        # Momentum signal
        momentum = pd.Series(0, index=df.index)
        momentum[rsi < 40] = 1  # Bullish
        momentum[rsi > 60] = -1  # Bearish

        # Volume signal
        vol_signal = pd.Series(0, index=df.index)
        vol_signal[volume_ratio > 1.2] = 1
        vol_signal[volume_ratio > 1.2] = -1

        return {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
            "trend": trend,
            "momentum": momentum,
            "vol_signal": vol_signal,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate confluence signals."""
        trend = indicators["trend"]
        momentum = indicators["momentum"]
        volume_ratio = indicators["volume_ratio"]

        signals = pd.Series(0, index=df.index)

        # Count agreement (need at least 2 out of 3)
        bullish = (trend == 1).astype(int) + (momentum == 1).astype(int)
        bearish = (trend == -1).astype(int) + (momentum == -1).astype(int)

        # Volume confirmation (optional but weighted)
        volume_confirm = volume_ratio > 1.2

        # Long: At least 2 bullish signals + volume
        signals[(bullish >= 2) & volume_confirm] = 1

        # Short: At least 2 bearish signals + volume
        signals[(bearish >= 2) & volume_confirm] = -1

        return signals
