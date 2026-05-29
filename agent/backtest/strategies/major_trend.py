"""MTES backtest strategy wrapper.

This strategy adapts the reusable MajorTrendEvaluator to the existing
BaseStrategy backtest contract. It is evaluation-only: it surfaces MTES
metrics and directional evaluation signals, but it does not include live
execution, position sizing, or portfolio allocation logic.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from . import BaseStrategy, StrategyType
from src.analysis.major_trend_evaluator import MajorTrendEvaluator, TrendState


class MajorTrendEvaluationStrategy(BaseStrategy):
    """Evaluation-only strategy that exposes MTES backtest signals.

    The wrapper runs the MTES evaluator on the full OHLCV frame and maps the
    resulting trend state into directional evaluation signals:

    - BULL_CONFIRMED / BULL_STRONG -> 1
    - BEAR_CONFIRMED / BEAR_STRONG -> -1
    - all other states -> 0
    """

    def __init__(self, parameters: Dict[str, Any] | None = None):
        """Initialize the MTES strategy wrapper.

        Args:
            parameters: Optional strategy parameters.
        """
        params = parameters.copy() if parameters else {}
        asset_class = str(params.get("asset_class", "stock"))
        params.setdefault("asset_class", asset_class)
        params.setdefault("market", "all")
        params.setdefault("base_timeframe", "1d")
        params.setdefault("higher_timeframe_name", "1w")

        super().__init__(
            name="major_trend_evaluation",
            strategy_type=StrategyType.TREND,
            parameters=params,
        )
        self.asset_class = asset_class
        self.base_timeframe = str(params["base_timeframe"])
        self.higher_timeframe_name = str(params["higher_timeframe_name"])
        self.evaluator = MajorTrendEvaluator()
        self.tags = ["trend", "mtes", "evaluation_only", "multi_timeframe"]
        self.timeframes = ["1d", "4h", "1h"]
        self.supported_markets = [
            "stock",
            "etf",
            "futures",
            "crypto",
            "fx",
            "a_stock",
            "us_stock",
            "us_futures",
            "cn_futures",
        ]

    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate MTES indicators for the full OHLCV frame.

        The wrapper evaluates the entire frame once and broadcasts the result
        across the returned indicator series so the existing BaseStrategy
        contract can expose MTES columns alongside the generated signals.
        """
        result = self.evaluator.evaluate(
            df,
            asset_class=self.asset_class,
            base_timeframe=self.base_timeframe,
            higher_timeframe_name=self.higher_timeframe_name,
        )
        return self._result_to_indicators(df, result.to_dict())

    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """Map MTES states to evaluation-only directional signals."""
        state = indicators["mtes_state"]
        mapping = {
            TrendState.BULL_STRONG.value: 1,
            TrendState.BULL_CONFIRMED.value: 1,
            TrendState.BEAR_STRONG.value: -1,
            TrendState.BEAR_CONFIRMED.value: -1,
        }
        return state.map(mapping).fillna(0).astype(int)

    def _result_to_indicators(
        self, df: pd.DataFrame, result: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """Convert a MTES result dictionary into per-row indicator series."""
        index = df.index
        sub_scores = result.get("sub_scores", {})
        raw_scores = result.get("raw_scores", {})

        indicators: Dict[str, pd.Series] = {
            "mtes_score": self._constant_series(index, result.get("trend_score", 0.0)),
            "mtes_state": self._constant_series(index, result.get("trend_state", TrendState.NEUTRAL_CHOPPY.value)),
            "mtes_direction": self._constant_series(index, result.get("direction", "NEUTRAL")),
            "mtes_regime": self._constant_series(index, result.get("regime", "insufficient")),
            "mtes_confidence": self._constant_series(index, result.get("confidence", 0.0)),
            "mtes_direction_score": self._constant_series(index, sub_scores.get("direction", 0.0)),
            "mtes_strength_score": self._constant_series(index, sub_scores.get("strength", 0.0)),
            "mtes_structure_score": self._constant_series(index, sub_scores.get("structure", 0.0)),
            "mtes_momentum_score": self._constant_series(index, sub_scores.get("momentum", 0.0)),
            "mtes_volatility_regime_score": self._constant_series(
                index, sub_scores.get("volatility_regime", 0.0)
            ),
            "mtes_mtf_score": self._constant_series(index, sub_scores.get("mtf", 0.0)),
            "mtes_direction_raw": self._constant_series(index, raw_scores.get("direction", 0.0)),
            "mtes_strength_raw": self._constant_series(index, raw_scores.get("strength", 0.0)),
            "mtes_structure_raw": self._constant_series(index, raw_scores.get("structure", 0.0)),
            "mtes_momentum_raw": self._constant_series(index, raw_scores.get("momentum", 0.0)),
            "mtes_volatility_regime_raw": self._constant_series(
                index, raw_scores.get("volatility_regime", 0.0)
            ),
            "mtes_mtf_raw": self._constant_series(index, raw_scores.get("mtf", 0.0)),
        }
        return indicators

    @staticmethod
    def _constant_series(index: pd.Index, value: Any) -> pd.Series:
        """Create a constant series aligned to the provided index."""
        return pd.Series([value] * len(index), index=index)


__all__ = ["MajorTrendEvaluationStrategy"]
