"""MTES V4 - Lean Direction Indicator.

Minimalist trend direction indicator with:
- ADX pre-filter for range detection
- Ichimoku Cloud for structural direction
- EMA alignment for momentum confirmation
- Market Structure as auxiliary reference (non-weighted)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

from .base import (
    LeanTrendResult,
    TrendDirection,
    TrendStrength,
    IchimokuSignal,
    EMASignal,
)
from .market_structure import MarketStructure, MarketStructureSignal


# Default periods
DEFAULT_TENKAN = 9
DEFAULT_KIJUN = 26
DEFAULT_SENKOU_B = 52
DEFAULT_DISPLACEMENT = 26
DEFAULT_FAST_EMA = 9
DEFAULT_SLOW_EMA = 21
DEFAULT_ADX_PERIOD = 14


@dataclass
class LeanMTESConfig:
    """Configuration for LeanMTES."""
    # ADX settings
    adx_period: int = DEFAULT_ADX_PERIOD
    adx_threshold: float = 20.0  # Minimum for trending
    adx_strong: float = 30.0  # Strong trend
    adx_ready: float = 25.0  # Ready to trend

    # Ichimoku settings
    tenkan_period: int = DEFAULT_TENKAN
    kijun_period: int = DEFAULT_KIJUN
    senkou_b_period: int = DEFAULT_SENKOU_B
    displacement: int = DEFAULT_DISPLACEMENT
    ichimoku_weight: float = 0.6  # Weight in voting

    # EMA settings
    fast_ema_period: int = DEFAULT_FAST_EMA
    slow_ema_period: int = DEFAULT_SLOW_EMA
    ema_weight: float = 0.4  # Weight in voting


class LeanMTES:
    """Lean MTES - Minimalist trend direction indicator.

    Architecture:
    1. ADX pre-filter: Skip if ADX < threshold (range-bound market)
    2. Ichimoku: Structural direction (60% weight)
    3. EMA: Momentum direction (40% weight)
    4. Voting: Combine signals for final direction
    """

    def __init__(self, config: Optional[LeanMTESConfig] = None):
        self.config = config or LeanMTESConfig()
        # Auxiliary: Market Structure (non-weighted)
        self.market_structure = MarketStructure()

    def analyze(self, df: pd.DataFrame) -> LeanTrendResult:
        """Analyze trend direction.

        Args:
            df: OHLCV DataFrame with columns [open, high, low, close]

        Returns:
            LeanTrendResult with direction and confidence
        """
        df = self._prepare_data(df)
        bars = len(df)

        # Step 1: Calculate ADX
        adx, plus_di, minus_di = self._calculate_adx(df)
        adx_val = float(adx.iloc[-1])
        plus_di_val = float(plus_di.iloc[-1])
        minus_di_val = float(minus_di.iloc[-1])

        # Step 2: ADX pre-filter
        is_trending = adx_val >= self.config.adx_threshold

        if not is_trending:
            return self._create_neutral_result(
                adx_val, plus_di_val, minus_di_val, bars, df,
                reason=f"ADX {adx_val:.1f} < {self.config.adx_threshold}"
            )

        # Step 3: Calculate Ichimoku signal
        ichimoku = self._analyze_ichimoku(df)
        ichimoku_score = self._ichimoku_to_score(ichimoku)

        # Step 4: Calculate EMA signal
        ema = self._analyze_ema(df)
        ema_score = self._ema_to_score(ema)

        # Step 5: Weighted voting
        direction, confidence = self._vote(
            ichimoku, ema,
            ichimoku_score, ema_score
        )

        # Step 6: Calculate final score
        final_score = self._calculate_final_score(
            direction, confidence, adx_val
        )

        # Step 7: Determine strength
        strength = self._determine_strength(adx_val)

        # Build explanation
        explanation = self._build_explanation(
            direction, confidence, adx_val, ichimoku, ema
        )

        # Auxiliary: Market Structure (non-weighted)
        mkt_structure = self.market_structure.analyze(df)

        return LeanTrendResult(
            direction=direction,
            confidence=confidence,
            final_score=final_score,
            is_trending=is_trending,
            strength=strength,
            adx=adx_val,
            plus_di=plus_di_val,
            minus_di=minus_di_val,
            ichimoku_score=ichimoku_score,
            ema_score=ema_score,
            ichimoku_signal=ichimoku,
            ema_signal=ema,
            market_structure=mkt_structure,
            bars_analyzed=bars,
            explanation=explanation,
        )

    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare and validate data."""
        df = df.copy()

        # Ensure lowercase columns
        df.columns = df.columns.str.lower()

        # Ensure required columns
        required = ['open', 'high', 'low', 'close']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
            elif 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')

        return df.sort_index()

    def _calculate_adx(
        self, df: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate ADX and directional indicators."""
        period = self.config.adx_period
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        n = len(df)

        # True Range
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        tr[1:] = np.maximum(np.maximum(tr1, tr2), tr3)

        # Directional Movement
        up_move = np.zeros(n)
        down_move = np.zeros(n)
        up_move[1:] = high[1:] - high[:-1]
        down_move[1:] = low[:-1] - low[1:]
        down_move = np.maximum(down_move, 0)

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Wilder's smoothing
        alpha = 1.0 / period
        smoothed_tr = np.zeros(n)
        smoothed_plus = np.zeros(n)
        smoothed_minus = np.zeros(n)

        smoothed_tr[period] = np.sum(tr[1:period + 1])
        smoothed_plus[period] = np.sum(plus_dm[1:period + 1])
        smoothed_minus[period] = np.sum(minus_dm[1:period + 1])

        for i in range(period + 1, n):
            smoothed_tr[i] = (1 - alpha) * smoothed_tr[i - 1] + alpha * tr[i]
            smoothed_plus[i] = (1 - alpha) * smoothed_plus[i - 1] + alpha * plus_dm[i]
            smoothed_minus[i] = (1 - alpha) * smoothed_minus[i - 1] + alpha * minus_dm[i]

        # Calculate DI
        with np.errstate(divide='ignore', invalid='ignore'):
            plus_di = 100 * smoothed_plus / np.where(smoothed_tr > 0, smoothed_tr, 1)
            minus_di = 100 * smoothed_minus / np.where(smoothed_tr > 0, smoothed_tr, 1)

        # Calculate DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / np.where(
            (plus_di + minus_di) > 0, plus_di + minus_di, 1
        )

        adx = np.zeros(n)
        adx[period * 2] = np.mean(dx[period:period * 2])
        for i in range(period * 2 + 1, n):
            adx[i] = (1 - alpha) * adx[i - 1] + alpha * dx[i]

        return (
            pd.Series(adx, index=df.index),
            pd.Series(plus_di, index=df.index),
            pd.Series(minus_di, index=df.index),
        )

    def _analyze_ichimoku(self, df: pd.DataFrame) -> IchimokuSignal:
        """Analyze Ichimoku Cloud."""
        c = self.config
        n = len(df)

        # Check minimum data
        min_required = c.senkou_b_period + c.displacement + 2
        if n < min_required:
            return IchimokuSignal(
                direction=TrendDirection.NEUTRAL,
                price_vs_cloud="in_cloud",
                tk_cross="neutral",
                cloud_direction="neutral",
                chikou_confirm=False,
                confidence=0.0,
            )

        high = df['high']
        low = df['low']
        close = df['close']

        # Tenkan-sen (Conversion Line)
        tenkan = (high.rolling(c.tenkan_period).max() +
                  low.rolling(c.tenkan_period).min()) / 2

        # Kijun-sen (Base Line)
        kijun = (high.rolling(c.kijun_period).max() +
                 low.rolling(c.kijun_period).min()) / 2

        # Senkou Span A (Leading Span A)
        senkou_a = ((tenkan + kijun) / 2).shift(c.displacement)

        # Senkou Span B (Leading Span B)
        senkou_b = ((high.rolling(c.senkou_b_period).max() +
                    low.rolling(c.senkou_b_period).min()) / 2).shift(c.displacement)

        # Current values
        current_close = float(close.iloc[-1])
        current_tenkan = float(tenkan.iloc[-1])
        current_kijun = float(kijun.iloc[-1])
        current_senkou_a = float(senkou_a.iloc[-1])
        current_senkou_b = float(senkou_b.iloc[-1])

        # Chikou comparison (current close vs 26 bars ago)
        chikou_compare = (current_close > float(close.iloc[-c.displacement - 1])
                          if n > c.displacement + 1 else False)

        # Cloud boundaries
        cloud_top = max(current_senkou_a, current_senkou_b)
        cloud_bottom = min(current_senkou_a, current_senkou_b)

        # Determine conditions
        price_vs_cloud: Literal["above", "in_cloud", "below"]
        if current_close > cloud_top:
            price_vs_cloud = "above"
        elif current_close < cloud_bottom:
            price_vs_cloud = "below"
        else:
            price_vs_cloud = "in_cloud"

        tk_cross: Literal["bullish", "bearish", "neutral"]
        if current_tenkan > current_kijun:
            tk_cross = "bullish"
        elif current_tenkan < current_kijun:
            tk_cross = "bearish"
        else:
            tk_cross = "neutral"

        cloud_direction: Literal["bullish", "bearish"] = (
            "bullish" if current_senkou_a > current_senkou_b else "bearish"
        )

        # Count bullish/bearish signals
        bullish_count = sum([
            price_vs_cloud == "above",
            tk_cross == "bullish",
            cloud_direction == "bullish",
            chikou_compare,
        ])

        bearish_count = sum([
            price_vs_cloud == "below",
            tk_cross == "bearish",
            cloud_direction == "bearish",
            not chikou_compare,
        ])

        # Determine direction
        if bullish_count >= 3:
            direction = TrendDirection.BULL
        elif bearish_count >= 3:
            direction = TrendDirection.BEAR
        else:
            direction = TrendDirection.NEUTRAL

        # Calculate confidence
        confidence = min(1.0, (bullish_count + bearish_count) / 6)

        return IchimokuSignal(
            direction=direction,
            price_vs_cloud=price_vs_cloud,
            tk_cross=tk_cross,
            cloud_direction=cloud_direction,
            chikou_confirm=chikou_compare,
            confidence=confidence,
        )

    def _analyze_ema(self, df: pd.DataFrame) -> EMASignal:
        """Analyze EMA alignment."""
        c = self.config
        close = df['close']

        # Calculate EMAs
        ema_fast = close.ewm(span=c.fast_ema_period, adjust=False).mean()
        ema_slow = close.ewm(span=c.slow_ema_period, adjust=False).mean()

        # Current values
        current_close = float(close.iloc[-1])
        current_fast = float(ema_fast.iloc[-1])
        current_slow = float(ema_slow.iloc[-1])

        # Previous values for slope
        if len(ema_fast) >= 5:
            fast_slope = float(ema_fast.iloc[-1] - ema_fast.iloc[-5]) / current_fast
        else:
            fast_slope = 0.0

        # Determine alignment
        alignment: Literal["bullish", "bearish", "mixed", "flat"]
        if current_fast > current_slow and fast_slope > 0.005:
            alignment = "bullish"
        elif current_fast < current_slow and fast_slope < -0.005:
            alignment = "bearish"
        elif current_fast > current_slow:
            alignment = "mixed"  # Still above but flattening
        elif current_fast < current_slow:
            alignment = "mixed"
        else:
            alignment = "flat"

        # Determine direction
        if alignment == "bullish":
            direction = TrendDirection.BULL
        elif alignment == "bearish":
            direction = TrendDirection.BEAR
        else:
            direction = TrendDirection.NEUTRAL

        # Price vs EMA
        price_vs_ema = current_close > current_slow

        # Slope
        slope: Literal["UP", "DOWN", "FLAT"]
        if fast_slope > 0.005:
            slope = "UP"
        elif fast_slope < -0.005:
            slope = "DOWN"
        else:
            slope = "FLAT"

        # Confidence
        confidence = 0.3
        if alignment == "bullish":
            confidence += 0.35
        elif alignment == "bearish":
            confidence += 0.35
        if price_vs_ema and direction == TrendDirection.BULL:
            confidence += 0.2
        if not price_vs_ema and direction == TrendDirection.BEAR:
            confidence += 0.2
        if slope != "FLAT":
            confidence += 0.15

        return EMASignal(
            direction=direction,
            alignment=alignment,
            price_vs_ema=price_vs_ema,
            slope=slope,
            confidence=min(1.0, confidence),
        )

    def _ichimoku_to_score(self, sig: IchimokuSignal) -> float:
        """Convert Ichimoku signal to 0-100 score."""
        if sig.direction == TrendDirection.BULL:
            base = 50
        elif sig.direction == TrendDirection.BEAR:
            base = -50
        else:
            return 50

        # Add bonus for conditions
        bonus = 0
        if sig.price_vs_cloud == "above":
            bonus += 15
        elif sig.price_vs_cloud == "below":
            bonus -= 15
        if sig.tk_cross == "bullish":
            bonus += 10
        elif sig.tk_cross == "bearish":
            bonus -= 10
        if sig.chikou_confirm and sig.direction == TrendDirection.BULL:
            bonus += 10
        if not sig.chikou_confirm and sig.direction == TrendDirection.BEAR:
            bonus -= 10

        return max(0, min(100, base + bonus + 25))

    def _ema_to_score(self, sig: EMASignal) -> float:
        """Convert EMA signal to 0-100 score."""
        if sig.direction == TrendDirection.BULL:
            base = 50
        elif sig.direction == TrendDirection.BEAR:
            base = -50
        else:
            return 50

        bonus = 0
        if sig.alignment == "bullish":
            bonus += 25
        elif sig.alignment == "bearish":
            bonus -= 25
        if sig.price_vs_ema and sig.direction == TrendDirection.BULL:
            bonus += 10
        if not sig.price_vs_ema and sig.direction == TrendDirection.BEAR:
            bonus -= 10
        if sig.slope == "UP":
            bonus += 10
        elif sig.slope == "DOWN":
            bonus -= 10

        return max(0, min(100, base + bonus + 25))

    def _vote(
        self,
        ichimoku: IchimokuSignal,
        ema: EMASignal,
        ichimoku_score: float,
        ema_score: float,
    ) -> tuple[TrendDirection, float]:
        """Vote on final direction."""
        ichimoku_weight = self.config.ichimoku_weight
        ema_weight = self.config.ema_weight

        # Weighted average of scores
        combined_score = (
            ichimoku_score * ichimoku_weight +
            ema_score * ema_weight
        )

        # Determine direction
        if combined_score >= 65:
            direction = TrendDirection.BULL
        elif combined_score <= 35:
            direction = TrendDirection.BEAR
        else:
            direction = TrendDirection.NEUTRAL

        # Confidence based on agreement
        direction_match = (
            ichimoku.direction == ema.direction == direction
        )
        base_confidence = 0.5
        if direction_match:
            base_confidence += 0.3
        elif direction == TrendDirection.NEUTRAL:
            base_confidence = 0.3
        else:
            base_confidence += 0.1

        # Adjust by strength of signal
        if direction == TrendDirection.BULL:
            confidence = base_confidence + (combined_score - 50) / 100
        elif direction == TrendDirection.BEAR:
            confidence = base_confidence + (50 - combined_score) / 100
        else:
            confidence = base_confidence

        return direction, min(1.0, max(0.0, confidence))

    def _calculate_final_score(
        self,
        direction: TrendDirection,
        confidence: float,
        adx: float,
    ) -> float:
        """Calculate final -100 to +100 score."""
        if direction == TrendDirection.BULL:
            base = 100
        elif direction == TrendDirection.BEAR:
            base = -100
        else:
            return 0.0

        # Adjust by ADX strength
        adx_factor = min(1.0, adx / 40.0)
        score = base * confidence * adx_factor

        return round(score, 2)

    def _determine_strength(self, adx: float) -> TrendStrength:
        """Determine trend strength from ADX."""
        if adx >= self.config.adx_strong:
            return TrendStrength.STRONG
        elif adx >= self.config.adx_ready:
            return TrendStrength.READY
        elif adx >= self.config.adx_threshold:
            return TrendStrength.WEAK
        else:
            return TrendStrength.EXHAUSTED

    def _create_neutral_result(
        self,
        adx: float,
        plus_di: float,
        minus_di: float,
        bars: int,
        df: pd.DataFrame | None = None,
        reason: str = "",
    ) -> LeanTrendResult:
        """Create neutral result for non-trending market."""
        # Auxiliary: Market Structure (non-weighted)
        mkt_structure = self.market_structure.analyze(df) if df is not None else None

        return LeanTrendResult(
            direction=TrendDirection.NEUTRAL,
            confidence=0.3,
            final_score=0.0,
            is_trending=False,
            strength=TrendStrength.EXHAUSTED,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            ichimoku_score=50.0,
            ema_score=50.0,
            ichimoku_signal=None,
            ema_signal=None,
            market_structure=mkt_structure,
            bars_analyzed=bars,
            explanation=f"Range-bound market: {reason}",
        )

    def _build_explanation(
        self,
        direction: TrendDirection,
        confidence: float,
        adx: float,
        ichimoku: IchimokuSignal,
        ema: EMASignal,
    ) -> str:
        """Build human-readable explanation."""
        strength_map = {
            TrendStrength.STRONG: "strong",
            TrendStrength.READY: "ready",
            TrendStrength.WEAK: "weak",
            TrendStrength.EXHAUSTED: "exhausted",
        }

        parts = []

        # Direction
        if direction == TrendDirection.BULL:
            parts.append("BULLISH")
        elif direction == TrendDirection.BEAR:
            parts.append("BEARISH")
        else:
            parts.append("NEUTRAL")

        # ADX
        parts.append(f"(ADX={adx:.1f})")

        # Ichimoku
        if ichimoku:
            if ichimoku.price_vs_cloud == "above":
                parts.append("price above cloud")
            elif ichimoku.price_vs_cloud == "below":
                parts.append("price below cloud")
            else:
                parts.append("price in cloud")

        # EMA
        if ema:
            parts.append(f"EMA {ema.alignment}")

        return " | ".join(parts)
