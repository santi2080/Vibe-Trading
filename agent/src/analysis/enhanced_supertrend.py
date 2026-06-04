"""Packaged Enhanced SuperTrend trend signal helper.

This module mirrors the lightweight prototype in the repository-root
``src/analysis/enhanced_supertrend.py`` so agent package code can import it via
``src.analysis.enhanced_supertrend`` without relying on ad hoc sys.path changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

TrendDirection = Literal[1, -1, 0]
TrendState = Literal["上涨", "下跌", "震荡"]


@dataclass
class TrendSignal:
    """Current enhanced SuperTrend signal."""

    trend: TrendState
    direction: TrendDirection
    confidence: float
    adx: float = 0.0
    supertrend_direction: TrendDirection = 0
    trend_magic_direction: TrendDirection = 0
    bars_since_flip: int = 0


class EnhancedSuperTrend:
    """Enhanced SuperTrend using SuperTrend, ADX, and TrendMagic-style CCI."""

    def __init__(
        self,
        st_period: int = 10,
        st_multiplier: float = 3.0,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        tm_cci_period: int = 20,
        tm_atr_period: int = 10,
        tm_atr_mult: float = 1.0,
    ) -> None:
        self.st_period = st_period
        self.st_multiplier = st_multiplier
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.tm_cci_period = tm_cci_period
        self.tm_atr_period = tm_atr_period
        self.tm_atr_mult = tm_atr_mult

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate enhanced SuperTrend columns for an OHLC DataFrame."""
        result = df.copy()

        st_direction = self._calc_supertrend(df)
        result["st_direction"] = st_direction

        adx, plus_di, minus_di = self._calc_adx(df)
        result["adx"] = adx
        result["plus_di"] = plus_di
        result["minus_di"] = minus_di

        tm_direction = self._calc_trend_magic(df)
        result["tm_direction"] = tm_direction

        persistence = self._calc_persistence(st_direction)
        result["persistence"] = persistence

        confidence = self._calc_confidence(adx, tm_direction, st_direction, persistence)
        result["confidence"] = confidence

        trend = self._calc_trend_state(st_direction, adx, tm_direction)
        result["trend"] = trend
        result["trend_code"] = trend.map({"上涨": 1, "下跌": -1, "震荡": 0})

        return result

    def get_signal(self, df: pd.DataFrame) -> TrendSignal:
        """Return the current signal from the final row."""
        result = self.calculate(df)
        last = result.iloc[-1]

        return TrendSignal(
            trend=last["trend"],
            direction=int(last["trend_code"]),
            confidence=float(last["confidence"]),
            adx=float(last["adx"]),
            supertrend_direction=int(last["st_direction"]),
            trend_magic_direction=int(last["tm_direction"]),
            bars_since_flip=int(last["persistence"]),
        )

    def _calc_supertrend(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr1[0], tr2[0], tr3[0] = 0, 0, 0
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = pd.Series(tr).rolling(window=self.st_period).mean().values

        hl_avg = (high + low) / 2
        basic_ub = hl_avg + self.st_multiplier * atr
        basic_lb = hl_avg - self.st_multiplier * atr

        final_ub = basic_ub.copy()
        final_lb = basic_lb.copy()
        direction = np.zeros(n)

        direction[self.st_period] = 1

        for i in range(self.st_period + 1, n):
            if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
                final_ub[i] = basic_ub[i]
            else:
                final_ub[i] = final_ub[i - 1]

            if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]:
                final_lb[i] = basic_lb[i]
            else:
                final_lb[i] = final_lb[i - 1]

            if direction[i - 1] == 1:
                direction[i] = -1 if close[i] < final_lb[i] else 1
            else:
                direction[i] = 1 if close[i] > final_ub[i] else -1

        return pd.Series(direction, index=df.index)

    def _calc_adx(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.adx_period).mean()

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        smooth_plus_dm = plus_dm.rolling(window=self.adx_period).mean()
        smooth_minus_dm = minus_dm.rolling(window=self.adx_period).mean()

        plus_di = 100 * (smooth_plus_dm / atr)
        minus_di = 100 * (smooth_minus_dm / atr)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(window=self.adx_period).mean()

        return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)

    def _calc_trend_magic(self, df: pd.DataFrame) -> pd.Series:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(window=self.tm_cci_period).mean()
        mad = tp.rolling(window=self.tm_cci_period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        cci = (tp - sma_tp) / (0.015 * mad + 1e-10)

        direction = np.where(cci >= 0, 1, -1)
        return pd.Series(direction, index=df.index)

    def _calc_persistence(self, direction: pd.Series) -> pd.Series:
        n = len(direction)
        persistence = np.zeros(n)
        current_dir = 0
        current_count = 0

        for i in range(n):
            if direction.iloc[i] == current_dir:
                current_count += 1
            else:
                current_dir = direction.iloc[i]
                current_count = 1
            persistence[i] = current_count

        return pd.Series(persistence, index=direction.index)

    def _calc_confidence(
        self,
        adx: pd.Series,
        tm_direction: pd.Series,
        st_direction: pd.Series,
        persistence: pd.Series,
    ) -> pd.Series:
        adx_score = ((adx - self.adx_threshold) / (40 - self.adx_threshold)).clip(0, 1)
        tm_alignment = (tm_direction == st_direction).astype(float)
        persistence_score = (persistence / 5).clip(0, 0.8)
        confidence = 0.4 * adx_score + 0.3 * tm_alignment + 0.3 * persistence_score
        return confidence.clip(0, 1)

    def _calc_trend_state(
        self,
        st_direction: pd.Series,
        adx: pd.Series,
        tm_direction: pd.Series,
    ) -> pd.Series:
        trend = pd.Series(index=st_direction.index, dtype=object)

        bull_mask = (adx >= self.adx_threshold) & (st_direction == 1) & (tm_direction == 1)
        bear_mask = (adx >= self.adx_threshold) & (st_direction == -1) & (tm_direction == -1)

        trend[bull_mask] = "上涨"
        trend[bear_mask] = "下跌"
        trend[~(bull_mask | bear_mask)] = "震荡"

        return trend


def quick_signal(df: pd.DataFrame) -> TrendSignal:
    """Return an Enhanced SuperTrend signal with default parameters."""
    return EnhancedSuperTrend().get_signal(df)
