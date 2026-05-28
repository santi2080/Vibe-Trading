"""Major Trend Evaluation System scoring."""

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

ASSET_WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "stock": {
        "direction": 22,
        "strength": 16,
        "structure": 18,
        "momentum": 20,
        "volatility_regime": 12,
        "mtf": 12,
    },
    "etf": {
        "direction": 24,
        "strength": 14,
        "structure": 14,
        "momentum": 22,
        "volatility_regime": 12,
        "mtf": 14,
    },
    "futures": {
        "direction": 22,
        "strength": 20,
        "structure": 16,
        "momentum": 16,
        "volatility_regime": 14,
        "mtf": 12,
    },
    "crypto": {
        "direction": 18,
        "strength": 16,
        "structure": 14,
        "momentum": 18,
        "volatility_regime": 20,
        "mtf": 14,
    },
    "fx": {
        "direction": 24,
        "strength": 18,
        "structure": 14,
        "momentum": 14,
        "volatility_regime": 12,
        "mtf": 18,
    },
}

MARKET_ASSET_CLASS = {
    "a_stock": "stock",
    "cn_stock": "stock",
    "stock": "stock",
    "us_stock": "stock",
    "us_stocks": "stock",
    "hk_stock": "stock",
    "hk_stocks": "stock",
    "etf": "etf",
    "us_etf": "etf",
    "futures": "futures",
    "future": "futures",
    "us_futures": "futures",
    "us_future": "futures",
    "cn_futures": "futures",
    "cn_future": "futures",
    "crypto": "crypto",
    "ccxt": "crypto",
    "fx": "fx",
    "forex": "fx",
}


class TrendState(str, Enum):
    BULL_STRONG = "BULL_STRONG"
    BULL_CONFIRMED = "BULL_CONFIRMED"
    BULL_EARLY = "BULL_EARLY"
    NEUTRAL_CHOPPY = "NEUTRAL_CHOPPY"
    BEAR_EARLY = "BEAR_EARLY"
    BEAR_CONFIRMED = "BEAR_CONFIRMED"
    BEAR_STRONG = "BEAR_STRONG"


@dataclass(frozen=True)
class MajorTrendConfig:
    asset_class: str = "futures"
    long_window: int = 200
    intermediate_window: int = 50
    short_window: int = 20
    adx_window: int = 14
    momentum_windows: tuple[int, int, int] = (63, 126, 252)
    structure_window: int = 55
    volatility_window: int = 20
    volatility_lookback: int = 252
    efficiency_window: int = 60


@dataclass(frozen=True)
class MajorTrendResult:
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
    """Scores major trend state across asset classes."""

    def __init__(self, config: MajorTrendConfig | None = None):
        self.config = config or MajorTrendConfig()
        validate_weight_profiles()

    def evaluate(
        self,
        df: pd.DataFrame,
        asset_class: str | None = None,
        higher_timeframe: pd.DataFrame | None = None,
        base_timeframe: str = "1d",
        higher_timeframe_name: str = "1w",
    ) -> MajorTrendResult:
        data = normalize_ohlcv(df)
        resolved_asset_class = resolve_asset_class(asset_class or self.config.asset_class)
        weights = get_weight_profile(resolved_asset_class)

        if len(data) < self.config.intermediate_window:
            return insufficient_data_result(resolved_asset_class, weights, len(data), self.config.intermediate_window)

        direction_score, direction, direction_meta = self.score_direction(data)
        strength_score, strength_meta = self.score_strength(data, direction)
        structure_score, structure_meta = self.score_structure(data, direction)
        momentum_score, momentum_meta = self.score_momentum(data, direction)
        regime_score, regime, regime_flags, regime_meta = self.score_volatility_regime(data)
        mtf_score, mtf_meta = self.score_mtf_alignment(
            data,
            direction,
            higher_timeframe=higher_timeframe,
            base_timeframe=base_timeframe,
            higher_timeframe_name=higher_timeframe_name,
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
        confidence = round(trend_score / 100, 3)
        top_drivers = build_top_drivers(sub_scores, raw_scores)
        explanation = build_explanation(trend_state, direction, trend_score, top_drivers, regime_flags)

        return MajorTrendResult(
            asset_class=resolved_asset_class,
            trend_score=trend_score,
            trend_state=trend_state,
            direction=direction,
            confidence=confidence,
            regime=regime,
            sub_scores=sub_scores,
            raw_scores={key: round(value, 2) for key, value in raw_scores.items()},
            weights=weights,
            top_drivers=top_drivers,
            regime_flags=regime_flags,
            explanation=explanation,
            metadata={
                "bars": len(data),
                "direction": direction_meta,
                "strength": strength_meta,
                "structure": structure_meta,
                "momentum": momentum_meta,
                "volatility_regime": regime_meta,
                "mtf": mtf_meta,
            },
        )

    def score_direction(self, df: pd.DataFrame) -> tuple[float, str, dict[str, Any]]:
        close = df["close"]
        intermediate = close.ewm(span=self.config.intermediate_window, adjust=False).mean()
        long_ma = close.ewm(span=self.config.long_window, adjust=False).mean()
        latest_close = float(close.iloc[-1])
        latest_intermediate = float(intermediate.iloc[-1])
        latest_long = float(long_ma.iloc[-1])
        slope_window = min(20, max(1, len(long_ma) - 1))
        long_slope = safe_pct_change(latest_long, float(long_ma.iloc[-1 - slope_window]))
        long_return = safe_pct_change(latest_close, float(close.iloc[max(0, len(close) - self.config.long_window)]))

        bull_checks = [
            latest_close > latest_long,
            latest_intermediate > latest_long,
            long_slope > 0,
            long_return > 0,
        ]
        bear_checks = [
            latest_close < latest_long,
            latest_intermediate < latest_long,
            long_slope < 0,
            long_return < 0,
        ]
        bull_count = sum(bull_checks)
        bear_count = sum(bear_checks)
        if bull_count > bear_count:
            direction = "BULL"
            score = 25 * bull_count
        elif bear_count > bull_count:
            direction = "BEAR"
            score = 25 * bear_count
        else:
            direction = "NEUTRAL"
            score = 25 * max(bull_count, bear_count)

        return float(score), direction, {
            "close": latest_close,
            "intermediate_ema": latest_intermediate,
            "long_ema": latest_long,
            "long_slope_pct": round(long_slope, 4),
            "long_return_pct": round(long_return, 4),
            "bull_checks": bull_count,
            "bear_checks": bear_count,
        }

    def score_strength(self, df: pd.DataFrame, direction: str) -> tuple[float, dict[str, Any]]:
        adx, plus_di, minus_di = calculate_adx(df, self.config.adx_window)
        latest_adx = fill_float(adx.iloc[-1], default=0.0)
        latest_plus = fill_float(plus_di.iloc[-1], default=0.0)
        latest_minus = fill_float(minus_di.iloc[-1], default=0.0)
        adx_component = clamp(latest_adx / 35 * 70, 0, 70)
        if direction == "BULL":
            directional_component = 30 if latest_plus > latest_minus else 0
        elif direction == "BEAR":
            directional_component = 30 if latest_minus > latest_plus else 0
        else:
            directional_component = 0
        return round(adx_component + directional_component, 2), {
            "adx": round(latest_adx, 2),
            "plus_di": round(latest_plus, 2),
            "minus_di": round(latest_minus, 2),
        }

    def score_structure(self, df: pd.DataFrame, direction: str) -> tuple[float, dict[str, Any]]:
        lookback = min(self.config.structure_window, max(2, len(df) - 1))
        close = df["close"]
        high = df["high"]
        low = df["low"]
        prior_high = float(high.iloc[-lookback - 1:-1].max()) if len(df) > lookback else float(high.iloc[:-1].max())
        prior_low = float(low.iloc[-lookback - 1:-1].min()) if len(df) > lookback else float(low.iloc[:-1].min())
        latest_close = float(close.iloc[-1])
        recent = close.iloc[-lookback:]
        midpoint = lookback // 2
        first_half_high = float(high.iloc[-lookback:-lookback + midpoint].max()) if midpoint > 0 else float(high.iloc[-lookback:].max())
        second_half_high = float(high.iloc[-midpoint:].max()) if midpoint > 0 else float(high.iloc[-lookback:].max())
        first_half_low = float(low.iloc[-lookback:-lookback + midpoint].min()) if midpoint > 0 else float(low.iloc[-lookback:].min())
        second_half_low = float(low.iloc[-midpoint:].min()) if midpoint > 0 else float(low.iloc[-lookback:].min())

        if direction == "BULL":
            score = 0
            score += 45 if latest_close >= prior_high else clamp((latest_close - prior_low) / max(prior_high - prior_low, 1e-9) * 35, 0, 35)
            score += 30 if second_half_high > first_half_high else 0
            score += 25 if second_half_low > first_half_low else 0
        elif direction == "BEAR":
            score = 0
            score += 45 if latest_close <= prior_low else clamp((prior_high - latest_close) / max(prior_high - prior_low, 1e-9) * 35, 0, 35)
            score += 30 if second_half_low < first_half_low else 0
            score += 25 if second_half_high < first_half_high else 0
        else:
            range_width = (float(recent.max()) - float(recent.min())) / max(abs(latest_close), 1e-9)
            score = 35 if range_width < 0.08 else 20

        return round(clamp(score, 0, 100), 2), {
            "lookback": lookback,
            "prior_high": round(prior_high, 4),
            "prior_low": round(prior_low, 4),
            "latest_close": round(latest_close, 4),
        }

    def score_momentum(self, df: pd.DataFrame, direction: str) -> tuple[float, dict[str, Any]]:
        close = df["close"]
        components: list[float] = []
        returns: dict[str, float | None] = {}
        for window in self.config.momentum_windows:
            label = f"{window}b"
            if len(close) <= window:
                returns[label] = None
                continue
            value = safe_pct_change(float(close.iloc[-1]), float(close.iloc[-1 - window]))
            returns[label] = round(value, 4)
            if direction == "BULL":
                components.append(clamp(value / 0.20 * 100, 0, 100))
            elif direction == "BEAR":
                components.append(clamp((-value) / 0.20 * 100, 0, 100))
            else:
                components.append(max(0, 40 - abs(value) * 100))
        score = sum(components) / len(components) if components else 0
        return round(score, 2), {"returns": returns, "available_windows": len(components)}

    def score_volatility_regime(self, df: pd.DataFrame) -> tuple[float, str, list[str], dict[str, Any]]:
        close = df["close"]
        returns = close.pct_change().dropna()
        if returns.empty:
            return 0.0, "insufficient", ["insufficient_volatility_data"], {}
        vol_window = min(self.config.volatility_window, len(returns))
        rolling_vol = returns.rolling(vol_window).std() * np.sqrt(252)
        current_vol = fill_float(rolling_vol.iloc[-1], default=float(returns.std() * np.sqrt(252)))
        history = rolling_vol.dropna().tail(self.config.volatility_lookback)
        percentile = percentile_rank(history, current_vol) if len(history) else 50.0
        efficiency_window = min(self.config.efficiency_window, max(2, len(close) - 1))
        net_move = abs(float(close.iloc[-1]) - float(close.iloc[-1 - efficiency_window]))
        path = close.diff().abs().tail(efficiency_window).sum()
        efficiency = float(net_move / path) if path and path > 0 else 0.0

        percentile_score = 100 - abs(percentile - 55) * 1.35
        efficiency_score = clamp(efficiency * 130, 0, 100)
        score = clamp(0.55 * percentile_score + 0.45 * efficiency_score, 0, 100)
        flags: list[str] = []
        if percentile >= 90:
            flags.append("extreme_volatility")
        if percentile <= 10:
            flags.append("compressed_volatility")
        if efficiency < 0.18:
            flags.append("choppy_noise")
        regime = "trend_friendly" if score >= 65 else "choppy" if score < 40 else "mixed"
        return round(score, 2), regime, flags, {
            "volatility_percentile": round(percentile, 2),
            "annualized_volatility": round(current_vol, 4),
            "trend_efficiency": round(efficiency, 4),
        }

    def score_mtf_alignment(
        self,
        df: pd.DataFrame,
        direction: str,
        higher_timeframe: pd.DataFrame | None,
        base_timeframe: str,
        higher_timeframe_name: str,
    ) -> tuple[float, dict[str, Any]]:
        if higher_timeframe is None or higher_timeframe.empty or direction == "NEUTRAL":
            return 50.0 if direction != "NEUTRAL" else 25.0, {"status": "not_provided"}

        try:
            from backtest.strategies.mtf import MTFAligner, MTFConfig
        except ImportError:
            try:
                from agent.backtest.strategies.mtf import MTFAligner, MTFConfig
            except ImportError:
                return 50.0, {"status": "mtf_aligner_unavailable"}

        htf = normalize_ohlcv(higher_timeframe)
        htf = htf.copy()
        htf["major_direction"] = htf["close"].ewm(span=min(20, len(htf)), adjust=False).mean()
        aligned = MTFAligner(MTFConfig(lag_bars=1)).align_htf_to_ltf(
            htf_data=htf[["major_direction"]],
            ltf_data=df[["close"]],
            htf_timeframe=higher_timeframe_name,
            ltf_timeframe=base_timeframe,
            htf_columns=["major_direction"],
        )
        aligned_data = aligned.data.dropna(subset=["htf_major_direction"])
        if aligned_data.empty:
            return 40.0, {"status": "no_aligned_values", "warmup_bars": aligned.warmup_bars}
        latest_htf = float(aligned_data["htf_major_direction"].iloc[-1])
        latest_close = float(aligned_data["close"].iloc[-1])
        agreement = (direction == "BULL" and latest_close >= latest_htf) or (direction == "BEAR" and latest_close <= latest_htf)
        return (90.0 if agreement else 25.0), {
            "status": "aligned",
            "method": aligned.alignment_method,
            "warmup_bars": aligned.warmup_bars,
            "latest_htf_value": round(latest_htf, 4),
            "agreement": agreement,
        }


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
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


def resolve_asset_class(value: str) -> str:
    key = value.strip().lower()
    asset_class = MARKET_ASSET_CLASS.get(key, key)
    if asset_class not in ASSET_WEIGHT_PROFILES:
        raise ValueError(f"unsupported asset class: {value}")
    return asset_class


def get_weight_profile(asset_class: str) -> dict[str, float]:
    resolved = resolve_asset_class(asset_class)
    return dict(ASSET_WEIGHT_PROFILES[resolved])


def validate_weight_profiles() -> None:
    for name, weights in ASSET_WEIGHT_PROFILES.items():
        missing = set(DIMENSIONS) - set(weights)
        if missing:
            raise ValueError(f"weight profile {name} missing dimensions: {sorted(missing)}")
        total = sum(weights.values())
        if round(total, 6) != 100:
            raise ValueError(f"weight profile {name} totals {total}, expected 100")


def classify_trend_state(score: float, direction: str) -> str:
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


def insufficient_data_result(asset_class: str, weights: dict[str, float], bars: int, required: int) -> MajorTrendResult:
    sub_scores = {dimension: 0.0 for dimension in DIMENSIONS}
    raw_scores = {dimension: 0.0 for dimension in DIMENSIONS}
    return MajorTrendResult(
        asset_class=asset_class,
        trend_score=0.0,
        trend_state=TrendState.NEUTRAL_CHOPPY.value,
        direction="NEUTRAL",
        confidence=0.0,
        regime="insufficient",
        sub_scores=sub_scores,
        raw_scores=raw_scores,
        weights=weights,
        top_drivers=[],
        regime_flags=["insufficient_data"],
        explanation=f"Insufficient data: {bars} bars available, {required} required.",
        metadata={"bars": bars, "required_bars": required},
    )


def calculate_adx(df: pd.DataFrame, period: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window=period).mean()
    return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)


def build_top_drivers(sub_scores: dict[str, float], raw_scores: dict[str, float]) -> list[dict[str, Any]]:
    ordered = sorted(sub_scores.items(), key=lambda item: item[1], reverse=True)
    return [
        {"dimension": dimension, "contribution": contribution, "raw_score": round(raw_scores[dimension], 2)}
        for dimension, contribution in ordered[:3]
        if contribution > 0
    ]


def build_explanation(
    trend_state: str,
    direction: str,
    score: float,
    top_drivers: list[dict[str, Any]],
    regime_flags: list[str],
) -> str:
    driver_text = ", ".join(driver["dimension"] for driver in top_drivers) or "no dominant drivers"
    flag_text = f" Regime flags: {', '.join(regime_flags)}." if regime_flags else ""
    return f"{trend_state} ({direction}) with score {score:.1f}; strongest drivers: {driver_text}.{flag_text}"


def safe_pct_change(current: float, prior: float) -> float:
    if prior == 0 or np.isnan(prior):
        return 0.0
    return (current - prior) / abs(prior)


def percentile_rank(values: pd.Series, current: float) -> float:
    clean = values.dropna()
    if clean.empty:
        return 50.0
    return float((clean <= current).mean() * 100)


def fill_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(result) or np.isinf(result):
        return default
    return result


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))
