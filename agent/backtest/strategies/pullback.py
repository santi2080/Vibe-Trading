"""Pullback Strategy - Identifies corrections against the primary trend.

Pullback strategies identify temporary corrections or retracements
against the primary trend, providing better entry prices.

Supported indicators:
- RSI (Relative Strength Index)
- Bollinger Bands
- Fibonacci Retracement
- Stochastic Oscillator

Usage:
    from agent.backtest.strategies.pullback import PullbackRsiStrategy

    strategy = PullbackRsiStrategy()
    result = strategy.generate(df)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from . import BaseStrategy, StrategyType


@dataclass
class PullbackParameters:
    """Parameters for pullback strategies."""

    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    bb_period: int = 20
    bb_std: float = 2.0
    stochastic_period: int = 14
    stochastic_smooth: int = 3


class PullbackRsiStrategy(BaseStrategy):
    """Pullback strategy using RSI for oversold/overbought conditions.

    Entry rules:
    - Long: RSI < oversold threshold (pullback in uptrend)
    - Short: RSI > overbought threshold (pullback in downtrend)

    This strategy identifies pullbacks against the trend for better entries.
    """

    def __init__(self, parameters: Optional[PullbackParameters] = None):
        """Initialize RSI pullback strategy.

        Args:
            parameters: Strategy parameters (uses defaults if not provided)
        """
        params = parameters or PullbackParameters()
        super().__init__(
            name="pullback_rsi",
            strategy_type=StrategyType.PULLBACK,
            parameters={
                "rsi_period": params.rsi_period,
                "rsi_oversold": params.rsi_oversold,
                "rsi_overbought": params.rsi_overbought,
            },
        )
        self.params = params

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate RSI indicator."""
        close = df["close"]

        # RSI calculation
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1 / self.params.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.params.rsi_period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return {
            "rsi": rsi,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate pullback signals based on RSI."""
        rsi = indicators["rsi"]

        signals = pd.Series(0, index=df.index)

        # Long: RSI oversold (potential pullback entry)
        signals[rsi < self.params.rsi_oversold] = 1

        # Short: RSI overbought (potential pullback entry)
        signals[rsi > self.params.rsi_overbought] = -1

        return signals


class PullbackBollingerBandsStrategy(BaseStrategy):
    """Pullback strategy using Bollinger Bands.

    Entry rules:
    - Long: Price touches lower band (support pullback)
    - Short: Price touches upper band (resistance pullback)

    Exit rules:
    - Price returns to middle band
    """

    def __init__(
        self,
        period: int = 20,
        std_multiplier: float = 2.0,
    ):
        """Initialize Bollinger Bands strategy.

        Args:
            period: Moving average period
            std_multiplier: Standard deviation multiplier
        """
        super().__init__(
            name="pullback_bollinger",
            strategy_type=StrategyType.PULLBACK,
            parameters={
                "period": period,
                "std_multiplier": std_multiplier,
            },
        )
        self.period = period
        self.std_multiplier = std_multiplier

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands."""
        close = df["close"]

        # Calculate bands
        sma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()

        upper_band = sma + (std * self.std_multiplier)
        lower_band = sma - (std * self.std_multiplier)

        # Position in bands (0-100 scale)
        band_width = upper_band - lower_band
        position = ((close - lower_band) / band_width) * 100

        return {
            "sma": sma,
            "upper_band": upper_band,
            "lower_band": lower_band,
            "band_position": position,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate Bollinger Band pullback signals."""
        close = df["close"]
        lower_band = indicators["lower_band"]
        upper_band = indicators["upper_band"]

        signals = pd.Series(0, index=df.index)

        # Long: Price touches or crosses below lower band
        signals[close <= lower_band] = 1

        # Short: Price touches or crosses above upper band
        signals[close >= upper_band] = -1

        return signals


class PullbackStochasticStrategy(BaseStrategy):
    """Pullback strategy using Stochastic Oscillator.

    Entry rules:
    - Long: %K crosses above %D in oversold region (< 20)
    - Short: %K crosses below %D in overbought region (> 80)
    """

    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        oversold: float = 20.0,
        overbought: float = 80.0,
    ):
        """Initialize Stochastic strategy.

        Args:
            k_period: %K period
            d_period: %D period (smoothed)
            oversold: Oversold threshold
            overbought: Overbought threshold
        """
        super().__init__(
            name="pullback_stochastic",
            strategy_type=StrategyType.PULLBACK,
            parameters={
                "k_period": k_period,
                "d_period": d_period,
                "oversold": oversold,
                "overbought": overbought,
            },
        )
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate Stochastic Oscillator."""
        low_min = df["low"].rolling(window=self.k_period).min()
        high_max = df["high"].rolling(window=self.k_period).max()

        # %K
        k_percent = 100 * (df["close"] - low_min) / (high_max - low_min)

        # %D (smoothed)
        d_percent = k_percent.rolling(window=self.d_period).mean()

        return {
            "k_percent": k_percent,
            "d_percent": d_percent,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate Stochastic crossover signals."""
        k = indicators["k_percent"]
        d = indicators["d_percent"]

        signals = pd.Series(0, index=df.index)

        # Crossover detection
        k_above_d = (k > d).fillna(False)
        prev_k_above_d = k_above_d.shift(1).fillna(False).astype(bool)

        # Long: %K crosses above %D in oversold region
        long_condition = k_above_d & ~prev_k_above_d & (k < self.oversold)
        signals[long_condition] = 1

        # Short: %K crosses below %D in overbought region
        short_condition = ~k_above_d & prev_k_above_d & (k > self.overbought)
        signals[short_condition] = -1

        return signals


class PullbackFibonacciStrategy(BaseStrategy):
    """Pullback strategy using Fibonacci Retracement levels.

    Entry rules:
    - Long: Price retraces to 38.2%, 50%, or 61.8% level
    - Short: Price bounces from resistance levels

    Note: This is a simplified version that uses historical high/low as reference.
    """

    def __init__(
        self,
        lookback_period: int = 100,
        retracement_levels: tuple = (0.382, 0.5, 0.618),
    ):
        """Initialize Fibonacci strategy.

        Args:
            lookback_period: Period to look back for swing high/low
            retracement_levels: Fibonacci retracement levels
        """
        super().__init__(
            name="pullback_fibonacci",
            strategy_type=StrategyType.PULLBACK,
            parameters={
                "lookback_period": lookback_period,
                "retracement_levels": retracement_levels,
            },
        )
        self.lookback_period = lookback_period
        self.retracement_levels = retracement_levels

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate Fibonacci retracement levels."""
        close = df["close"]

        # Rolling swing high/low
        swing_high = close.rolling(window=self.lookback_period).max()
        swing_low = close.rolling(window=self.lookback_period).min()
        swing_range = swing_high - swing_low

        # Retracement levels
        levels = {}
        for level in self.retracement_levels:
            levels[f"fib_{int(level*1000)}"] = swing_high - (swing_range * level)

        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            **levels,
        }

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Generate Fibonacci pullback signals."""
        close = df["close"]

        signals = pd.Series(0, index=df.index)

        # Check if price is near any Fibonacci level
        tolerance = 0.005  # 0.5% tolerance

        for level in self.retracement_levels:
            level_key = f"fib_{int(level*1000)}"
            fib_level = indicators[level_key]

            # Price near Fibonacci level
            near_level = (
                (close >= fib_level * (1 - tolerance))
                & (close <= fib_level * (1 + tolerance))
            )

            # Long: Pullback to Fibonacci support
            if level < 0.5:
                signals[near_level] = 1
            # Short: Pullback to Fibonacci resistance
            else:
                signals[near_level] = -1

        return signals
