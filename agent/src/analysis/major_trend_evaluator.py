"""Major Trend Evaluation System scoring.

This module provides the reusable MTES core evaluator used by watchlist and
backtest adapters. The evaluator is deterministic for a fixed OHLCV input and
keeps trend quality score independent from directional sign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

DIMENSIONS = (
    "direction",
    "strength",
    "structure",
    "momentum",
    "volatility_regime",
    "mtf",
)

BASE_WEIGHTS: dict[str, int] = {
    "direction": 15,
    "strength": 15,
    "structure": 25,
    "momentum": 15,
    "volatility_regime": 15,
    "mtf": 15,
}

ASSET_WEIGHT_PROFILES: dict[str, dict[str, int]] = {
    "stock": {},
    "etf": {"structure": 20, "volatility_regime": 20},
    "futures": {"direction": 18, "strength": 17, "structure": 22, "volatility_regime": 13},
    "crypto": {"direction": 12, "strength": 13, "structure": 20, "momentum": 22, "volatility_regime": 18},
    "fx": {"direction": 18, "strength": 12, "structure": 20, "mtf": 20},
}

DIRECTION_PERIODS: dict[str, dict[str, int]] = {
    "stock": {"intermediate": 50, "long": 200, "slope": 40, "return": 200},
    "etf": {"intermediate": 50, "long": 200, "slope": 40, "return": 200},
    "futures": {"intermediate": 40, "long": 160, "slope": 32, "return": 160},
    "crypto": {"intermediate": 30, "long": 120, "slope": 24, "return": 120},
    "fx": {"intermediate": 60, "long": 180, "slope": 36, "return": 180},
}

MARKET_ALIASES = {
    "stock": "stock",
    "stocks": "stock",
    "a_stock": "stock",
    "us_stock": "stock",
    "equity": "stock",
    "etf": "etf",
    "fund": "etf",
    "futures": "futures",
    "future": "futures",
    "us_futures": "futures",
    "cn_futures": "futures",
    "commodity": "futures",
    "crypto": "crypto",
    "cryptocurrency": "crypto",
    "fx": "fx",
    "forex": "fx",
    "currency": "fx",
}


class TrendState(Enum):
    """Locked seven-state major-trend labels."""

    BULL_STRONG = "BULL_STRONG"
    BULL_CONFIRMED = "BULL_CONFIRMED"
    BULL_EARLY = "BULL_EARLY"
    NEUTRAL_CHOPPY = "NEUTRAL_CHOPPY"
    BEAR_EARLY = "BEAR_EARLY"
    BEAR_CONFIRMED = "BEAR_CONFIRMED"
    BEAR_STRONG = "BEAR_STRONG"


@dataclass(frozen=True)
class MajorTrendConfig:
    """Configuration for the MTES evaluator."""

    asset_class: str = "stock"
    adx_period: int = 14
    structure_window: int = 55
    swing_window: int = 20
    regime_window: int = 126
    momentum_windows: tuple[int, int, int] = (63, 126, 252)


@dataclass(frozen=True)
class MajorTrendResult:
    """Structured result returned by :class:`MajorTrendEvaluator`."""

    asset_class: str
    trend_score: float
    trend_state: str
    direction: str
    confidence: float
    regime: str
    sub_scores: dict[str, float]
    raw_scores: dict[str, float]
    weights: dict[str, float]
    top_drivers: list[dict[str, Any]]
    regime_flags: list[str]
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the machine-readable MTES payload."""
        return {
            "asset_class": self.asset_class,
            "trend_score": self.trend_score,
            "trend_state": self.trend_state,
            "direction": self.direction,
            "confidence": self.confidence,
            "regime": self.regime,
            "sub_scores": self.sub_scores,
            "raw_scores": self.raw_scores,
            "weights": self.weights,
            "top_drivers": self.top_drivers,
            "regime_flags": self.regime_flags,
            "explanation": self.explanation,
            "metadata": self.metadata,
        }


class MajorTrendEvaluator:
    """Evaluate cross-asset major-trend quality across six dimensions."""

    def __init__(self, config: MajorTrendConfig | None = None):
        """Initialize the evaluator with optional configuration."""
        self.config = config or MajorTrendConfig()

    def evaluate(
        self,
        df: pd.DataFrame,
        asset_class: str | None = None,
        higher_timeframe: pd.DataFrame | None = None,
        base_timeframe: str = "1d",
        higher_timeframe_name: str = "1w",
        cross_section_context: dict[str, Any] | None = None,
    ) -> MajorTrendResult:
        """Score an OHLCV frame and return the MTES result contract."""
        resolved_asset_class = resolve_asset_class(asset_class or self.config.asset_class)
        weights = get_weight_profile(resolved_asset_class)
        missing_optional = [column for column in ["volume"] if column not in df.columns]
        data = normalize_ohlcv(df)
        periods = DIRECTION_PERIODS[resolved_asset_class]
        required_bars = max(periods["long"], periods["return"])

        if len(data) < required_bars:
            return insufficient_data_result(
                resolved_asset_class,
                weights,
                bars=len(data),
                required=required_bars,
                metadata={"input": {"missing_optional": missing_optional}},
            )

        direction_score, direction, direction_meta = self.score_direction(data, resolved_asset_class)
        strength_score, strength_meta = self.score_strength(data, direction)
        structure_score, structure_meta = self.score_structure(data, direction)
        momentum_score, momentum_meta = self.score_momentum(data, direction, cross_section_context)
        regime_score, regime, regime_flags, regime_meta = self.score_volatility_regime(data)
        mtf_score, mtf_meta = self.score_mtf_alignment(
            data,
            direction,
            higher_timeframe,
            base_timeframe,
            higher_timeframe_name,
        )

        raw_scores = {
            "direction": direction_score,
            "strength": strength_score,
            "structure": structure_score,
            "momentum": momentum_score,
            "volatility_regime": regime_score,
            "mtf": mtf_score,
        }
        sub_scores = {
            dimension: round(raw_scores[dimension] * weights[dimension] / 100, 2)
            for dimension in DIMENSIONS
        }
        trend_score = round(sum(sub_scores.values()), 2)
        trend_state = classify_trend_state(trend_score, direction)

        if mtf_meta.get("timeframe_conflict"):
            regime_flags.append("timeframe_conflict")

        metadata = {
            "status": "scored",
            "bars": len(data),
            "required_bars": required_bars,
            "input": {"missing_optional": missing_optional},
            "direction": direction_meta,
            "strength": strength_meta,
            "structure": structure_meta,
            "momentum": momentum_meta,
            "volatility_regime": regime_meta,
            "mtf": mtf_meta,
        }
        top_drivers = build_top_drivers(sub_scores, raw_scores, mtf_meta)
        confidence = round(min(1.0, trend_score / 100), 3)
        explanation = (
            f"{trend_state} with {trend_score:.1f}/100 quality; "
            f"direction={direction}, regime={regime}."
        )

        return MajorTrendResult(
            asset_class=resolved_asset_class,
            trend_score=trend_score,
            trend_state=trend_state,
            direction=direction,
            confidence=confidence,
            regime=regime,
            sub_scores=sub_scores,
            raw_scores=raw_scores,
            weights={dimension: float(weight) for dimension, weight in weights.items()},
            top_drivers=top_drivers,
            regime_flags=sorted(set(regime_flags)),
            explanation=explanation,
            metadata=metadata,
        )

    def score_direction(self, df: pd.DataFrame, asset_class: str) -> tuple[float, str, dict[str, Any]]:
        """Score direction using price/MA, MA spread, long-MA slope, and long return."""
        periods = DIRECTION_PERIODS[asset_class]
        close = df["close"]
        intermediate_ma = close.rolling(periods["intermediate"]).mean()
        long_ma = close.rolling(periods["long"]).mean()
        current = float(close.iloc[-1])
        intermediate = float(intermediate_ma.iloc[-1])
        long_value = float(long_ma.iloc[-1])
        slope_base = float(long_ma.iloc[-1 - periods["slope"]])
        long_slope = (long_value - slope_base) / abs(slope_base) if slope_base else 0.0
        return_base = float(close.iloc[-1 - periods["return"]])
        long_return = (current - return_base) / abs(return_base) if return_base else 0.0

        signals = {
            "price_vs_long_ma": compare_sign(current, long_value, tolerance=0.005),
            "intermediate_vs_long_ma": compare_sign(intermediate, long_value, tolerance=0.0025),
            "long_ma_slope": compare_sign(long_slope, 0.0, tolerance=0.001),
            "long_horizon_return": compare_sign(long_return, 0.0, tolerance=0.01),
        }
        net = sum(signals.values())
        if net >= 2:
            direction = "BULL"
        elif net <= -2:
            direction = "BEAR"
        else:
            direction = "NEUTRAL"

        agreement = abs(net) / len(signals)
        magnitude = min(1.0, abs(long_return) * 4 + abs(long_slope) * 12)
        score = clamp(35 + agreement * 45 + magnitude * 20, 0, 100)
        if direction == "NEUTRAL":
            score = min(score, 45.0)

        return round(score, 2), direction, {
            "periods": periods,
            "signals": signals,
            "long_slope": round(long_slope, 6),
            "long_horizon_return": round(long_return, 6),
        }

    def score_strength(self, df: pd.DataFrame, direction: str) -> tuple[float, dict[str, Any]]:
        """Score trend strength with ADX and directional movement agreement."""
        adx, plus_di, minus_di = calculate_adx(df, self.config.adx_period)
        adx_value = safe_last(adx, default=0.0)
        plus_value = safe_last(plus_di, default=0.0)
        minus_value = safe_last(minus_di, default=0.0)
        di_agrees = (
            (direction == "BULL" and plus_value >= minus_value)
            or (direction == "BEAR" and minus_value >= plus_value)
            or direction == "NEUTRAL"
        )
        score = min(100.0, adx_value * 2.5)
        if di_agrees:
            score = min(100.0, score + 10.0)
        else:
            score = max(0.0, score - 20.0)
        return round(score, 2), {
            "adx": round(adx_value, 4),
            "plus_di": round(plus_value, 4),
            "minus_di": round(minus_value, 4),
            "di_agrees_with_direction": di_agrees,
        }

    def score_structure(self, df: pd.DataFrame, direction: str) -> tuple[float, dict[str, Any]]:
        """Score Donchian/range position and swing structure evidence."""
        window = min(self.config.structure_window, max(20, len(df) // 2))
        close = df["close"]
        high = df["high"]
        low = df["low"]
        prior_high = float(high.iloc[-window:-1].max())
        prior_low = float(low.iloc[-window:-1].min())
        current = float(close.iloc[-1])
        price_range = max(prior_high - prior_low, 1e-9)
        range_position = clamp((current - prior_low) / price_range, 0, 1)

        if current > prior_high:
            breakout_state = "breakout_up"
        elif current < prior_low:
            breakout_state = "breakout_down"
        else:
            breakout_state = "in_range"

        swing = self._swing_structure(df, direction)
        range_score = range_position * 100 if direction == "BULL" else (1 - range_position) * 100
        if direction == "NEUTRAL":
            range_score = 50 - abs(range_position - 0.5) * 60
        breakout_bonus = 15 if (
            (direction == "BULL" and breakout_state == "breakout_up")
            or (direction == "BEAR" and breakout_state == "breakout_down")
        ) else 0
        swing_score = {"aligned": 90, "mixed": 55, "opposed": 25}.get(swing, 55)
        score = clamp(range_score * 0.45 + swing_score * 0.45 + breakout_bonus, 0, 100)

        return round(score, 2), {
            "range_position": round(range_position, 4),
            "breakout_state": breakout_state,
            "swing_structure": swing,
            "window": window,
        }

    def score_momentum(
        self,
        df: pd.DataFrame,
        direction: str,
        cross_section_context: dict[str, Any] | None,
    ) -> tuple[float, dict[str, Any]]:
        """Score absolute 3/6/12 month momentum with optional relative rank."""
        close = df["close"]
        returns: dict[str, float | None] = {}
        available_scores: list[float] = []
        for window in self.config.momentum_windows:
            key = f"return_{window}"
            if len(close) <= window:
                returns[key] = None
                continue
            base = float(close.iloc[-1 - window])
            value = (float(close.iloc[-1]) - base) / abs(base) if base else 0.0
            returns[key] = round(value, 6)
            signed = value if direction == "BULL" else -value if direction == "BEAR" else abs(value) * 0.25
            available_scores.append(clamp(50 + signed * 250, 0, 100))

        absolute_score = float(np.mean(available_scores)) if available_scores else 35.0
        metadata: dict[str, Any] = {
            "absolute_returns": returns,
            "missing_windows": [key for key, value in returns.items() if value is None],
            "relative_status": "not_provided",
        }
        score = absolute_score

        if cross_section_context:
            rank = resolve_relative_rank(cross_section_context)
            if rank is not None:
                relative_score = rank * 100
                score = absolute_score * 0.75 + relative_score * 0.25
                metadata["relative_status"] = "applied"
                metadata["relative_rank"] = round(rank, 4)
            else:
                metadata["relative_status"] = "unavailable"

        return round(clamp(score, 0, 100), 2), metadata

    def score_volatility_regime(self, df: pd.DataFrame) -> tuple[float, str, list[str], dict[str, Any]]:
        """Score trend-following suitability, primarily using efficiency/chop."""
        window = min(self.config.regime_window, len(df) - 1)
        close = df["close"]
        recent = close.iloc[-window:]
        net_move = abs(float(recent.iloc[-1] - recent.iloc[0]))
        path = float(recent.diff().abs().sum())
        trend_efficiency = net_move / path if path else 0.0
        returns = close.pct_change().dropna()
        historical_volatility = float(returns.iloc[-window:].std() * np.sqrt(252)) if len(returns) else 0.0
        atr = calculate_atr(df, 14)
        atr_value = safe_last(atr, default=0.0)
        atr_pct = atr_value / abs(float(close.iloc[-1])) if float(close.iloc[-1]) else 0.0

        flags: list[str] = []
        if trend_efficiency < 0.25:
            flags.append("choppy")
        if historical_volatility > 0.85:
            flags.append("extreme_volatility")
        if atr_pct > 0.08:
            flags.append("high_atr")

        score = clamp(20 + trend_efficiency * 85, 0, 100)
        if "extreme_volatility" in flags:
            score -= 10
        if "high_atr" in flags:
            score -= 8
        score = clamp(score, 0, 100)
        regime = "trend_friendly" if score >= 65 else "mixed" if score >= 40 else "choppy"

        return round(score, 2), regime, flags, {
            "trend_efficiency": round(trend_efficiency, 6),
            "atr_pct": round(atr_pct, 6),
            "historical_volatility": round(historical_volatility, 6),
            "primary_penalty": "trend_efficiency_chop",
        }

    def score_mtf_alignment(
        self,
        df: pd.DataFrame,
        direction: str,
        higher_timeframe: pd.DataFrame | None,
        base_timeframe: str,
        higher_timeframe_name: str,
    ) -> tuple[float, dict[str, Any]]:
        """Score higher-timeframe alignment through the project MTFAligner."""
        if higher_timeframe is None:
            return 50.0, {
                "method": "not_provided",
                "aligner": None,
                "timeframe_conflict": False,
                "base_timeframe": base_timeframe,
                "higher_timeframe": higher_timeframe_name,
            }

        from backtest.strategies.mtf import MTFAligner, MTFConfig

        htf = normalize_ohlcv(higher_timeframe)
        htf = htf.copy()
        htf["major_direction"] = directional_series(htf["close"])
        aligned = MTFAligner(MTFConfig(lag_bars=1)).align_htf_to_ltf(
            htf_data=htf[["major_direction"]],
            ltf_data=df[["close"]],
            htf_timeframe=higher_timeframe_name,
            ltf_timeframe=base_timeframe,
            htf_columns=["major_direction"],
        )
        aligned_data = aligned.data.dropna(subset=["htf_major_direction"])
        if aligned_data.empty:
            return 50.0, {
                "method": aligned.alignment_method,
                "aligner": "MTFAligner",
                "lag_bars": 1,
                "timeframe_conflict": False,
                "status": "degraded_no_aligned_bars",
                "base_timeframe": base_timeframe,
                "higher_timeframe": higher_timeframe_name,
            }

        htf_signal = float(aligned_data["htf_major_direction"].iloc[-1])
        htf_direction = "BULL" if htf_signal > 0 else "BEAR" if htf_signal < 0 else "NEUTRAL"
        conflict = direction in {"BULL", "BEAR"} and htf_direction in {"BULL", "BEAR"} and direction != htf_direction
        score = 25.0 if conflict else 90.0 if direction == htf_direction else 55.0
        return score, {
            "method": aligned.alignment_method,
            "aligner": "MTFAligner",
            "lag_bars": 1,
            "timeframe_conflict": conflict,
            "base_direction": direction,
            "higher_direction": htf_direction,
            "base_timeframe": base_timeframe,
            "higher_timeframe": higher_timeframe_name,
            "warmup_bars": aligned.warmup_bars,
        }

    def _swing_structure(self, df: pd.DataFrame, direction: str) -> str:
        """Classify swing structure as aligned, mixed, or opposed."""
        window = min(self.config.swing_window, max(5, len(df) // 4))
        current_high = float(df["high"].iloc[-window:].max())
        previous_high = float(df["high"].iloc[-2 * window : -window].max())
        current_low = float(df["low"].iloc[-window:].min())
        previous_low = float(df["low"].iloc[-2 * window : -window].min())
        higher_high = current_high > previous_high
        higher_low = current_low > previous_low
        lower_high = current_high < previous_high
        lower_low = current_low < previous_low

        if direction == "BULL":
            if higher_high and higher_low:
                return "aligned"
            if lower_high and lower_low:
                return "opposed"
        if direction == "BEAR":
            if lower_high and lower_low:
                return "aligned"
            if higher_high and higher_low:
                return "opposed"
        return "mixed"


def resolve_asset_class(asset_class: str) -> str:
    """Resolve market aliases to a supported MTES asset class."""
    normalized = str(asset_class).strip().lower()
    resolved = MARKET_ALIASES.get(normalized, normalized)
    if resolved not in ASSET_WEIGHT_PROFILES:
        raise ValueError(f"unsupported asset class: {asset_class}")
    return resolved


def get_weight_profile(asset_class: str) -> dict[str, int]:
    """Return final Base+Override weights for a supported asset class."""
    resolved = resolve_asset_class(asset_class)
    profile = BASE_WEIGHTS | ASSET_WEIGHT_PROFILES[resolved]
    if set(profile) != set(DIMENSIONS):
        raise ValueError(f"weight profile for {resolved} must contain exactly {DIMENSIONS}")
    total = sum(profile.values())
    if total != 100:
        raise ValueError(f"weight profile for {resolved} totals {total}, expected 100")
    return dict(profile)


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, sort, and coerce OHLCV input data."""
    data = df.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        if "timestamp" in data.columns:
            data["timestamp"] = pd.to_datetime(data["timestamp"])
            data = data.set_index("timestamp")
        elif "datetime" in data.columns:
            data["datetime"] = pd.to_datetime(data["datetime"])
            data = data.set_index("datetime")
    required = ["open", "high", "low", "close"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"missing required OHLC columns: {', '.join(missing)}")
    if "volume" not in data.columns:
        data["volume"] = 0.0
    data = data.sort_index()
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["open", "high", "low", "close"])


def insufficient_data_result(
    asset_class: str,
    weights: dict[str, int],
    bars: int,
    required: int,
    metadata: dict[str, Any] | None = None,
) -> MajorTrendResult:
    """Return the locked no-score result for insufficient long-horizon data."""
    sub_scores = {dimension: 0.0 for dimension in DIMENSIONS}
    raw_scores = {dimension: 0.0 for dimension in DIMENSIONS}
    extra_metadata = metadata or {}
    return MajorTrendResult(
        asset_class=asset_class,
        trend_score=0.0,
        trend_state=TrendState.NEUTRAL_CHOPPY.value,
        direction="NEUTRAL",
        confidence=0.0,
        regime="insufficient",
        sub_scores=sub_scores,
        raw_scores=raw_scores,
        weights={dimension: float(weight) for dimension, weight in weights.items()},
        top_drivers=[],
        regime_flags=["insufficient_data"],
        explanation=f"Insufficient data: {bars} bars available, {required} required.",
        metadata={"status": "no_score", "bars": bars, "required_bars": required, **extra_metadata},
    )


def classify_trend_state(score: float, direction: str) -> str:
    """Classify score and independent direction into seven locked states."""
    if direction == "BULL":
        if score >= 80:
            return TrendState.BULL_STRONG.value
        if score >= 62:
            return TrendState.BULL_CONFIRMED.value
        if score >= 45:
            return TrendState.BULL_EARLY.value
    if direction == "BEAR":
        if score >= 80:
            return TrendState.BEAR_STRONG.value
        if score >= 62:
            return TrendState.BEAR_CONFIRMED.value
        if score >= 45:
            return TrendState.BEAR_EARLY.value
    return TrendState.NEUTRAL_CHOPPY.value


def build_top_drivers(
    sub_scores: dict[str, float],
    raw_scores: dict[str, float],
    mtf_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build explainability drivers from weighted scores and conflict metadata."""
    drivers = [
        {"name": dimension, "sub_score": sub_scores[dimension], "raw_score": raw_scores[dimension]}
        for dimension in DIMENSIONS
    ]
    drivers.sort(key=lambda item: item["sub_score"], reverse=True)
    top = drivers[:3]
    if mtf_meta.get("timeframe_conflict"):
        top.append({"name": "timeframe_conflict", "sub_score": sub_scores["mtf"], "raw_score": raw_scores["mtf"]})
    return top


def calculate_adx(df: pd.DataFrame, period: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate ADX and directional indicators."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    plus_dm = high.diff().where(lambda series: series > 0, 0.0)
    minus_dm = (-low.diff()).where(lambda series: series > 0, 0.0)
    atr = tr.rolling(window=period).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
    minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window=period).mean().fillna(0.0)
    return adx, plus_di.fillna(0.0), minus_di.fillna(0.0)


def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculate average true range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().fillna(0.0)


def directional_series(close: pd.Series) -> pd.Series:
    """Return a compact directional signal series for MTF alignment."""
    span = max(3, min(20, len(close) // 2))
    average = close.ewm(span=span, adjust=False).mean()
    slope = average.diff(max(1, min(5, len(close) // 4))).fillna(0.0)
    return np.sign(slope + (close - average) * 0.01)


def resolve_relative_rank(context: dict[str, Any]) -> float | None:
    """Resolve a 0-1 relative momentum rank from cross-sectional context."""
    if "relative_rank" in context:
        return clamp(float(context["relative_rank"]), 0, 1)
    returns = context.get("returns_252") or context.get("momentum_returns")
    asset_id = context.get("asset_id")
    if not isinstance(returns, dict) or asset_id not in returns:
        return None
    ordered = sorted(float(value) for value in returns.values())
    if len(ordered) <= 1:
        return 1.0
    value = float(returns[asset_id])
    below_or_equal = sum(1 for item in ordered if item <= value)
    return (below_or_equal - 1) / (len(ordered) - 1)


def compare_sign(left: float, right: float, tolerance: float) -> int:
    """Compare two values with tolerance and return -1/0/1."""
    reference = max(abs(right), 1.0)
    difference = (left - right) / reference
    if difference > tolerance:
        return 1
    if difference < -tolerance:
        return -1
    return 0


def safe_last(series: pd.Series, default: float) -> float:
    """Return the last finite value in a series or a default."""
    clean = series.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return default
    return float(clean.iloc[-1])


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a numeric value to an inclusive range."""
    return max(lower, min(upper, float(value)))


def validate_weight_profiles() -> bool:
    """Validate every composed asset-class profile at import or test time."""
    for asset_class in ASSET_WEIGHT_PROFILES:
        get_weight_profile(asset_class)
    return True
