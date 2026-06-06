"""Auto-generated signal engine for composite backtest.

Copy this file to ``run_dir/code/signal_engine.py`` before running
``python -m backtest.runner <run_dir>``.

The runner instantiates ``SignalEngine()`` with no arguments, so this module
loads ``run_dir/config.json`` relative to its copied location when no explicit
config is provided.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd

from backtest.engines.composite_engine import CompositeBacktestSignalEngine
from src.analysis.mtes_v3 import MTESv3Config
from src.strategies.composite.trend_composite import CompositeTrendStrategy
from src.strategies.trend.base import TrendStrategyConfig
from src.strategies.trend.enhanced_supertrend import (
    EnhancedSuperTrendStrategy,
    EnhancedSuperTrendStrategyConfig,
)
from src.strategies.trend.mtes_v3 import MTESv3TrendStrategy


def _load_adjacent_config() -> dict:
    """Load ``run_dir/config.json`` when this file lives in ``run_dir/code``."""
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _nested_config(config: dict, key: str) -> dict:
    """Return a nested config dict, or {} when absent/invalid."""
    value = config.get(key, {})
    return value if isinstance(value, dict) else {}


def _build_mtes_config(config: dict) -> MTESv3Config:
    """Map user-facing YAML keys onto the current MTESv3Config contract."""
    raw = _nested_config(config, "mtes_config")
    adx_threshold = float(raw.get("adx_threshold", raw.get("adx_prefilter_threshold", 20.0)))
    return MTESv3Config(
        adx_prefilter_threshold=adx_threshold,
        adx_ready_threshold=float(raw.get("adx_ready_threshold", adx_threshold)),
        adx_strong_threshold=float(raw.get("adx_strong_threshold", max(30.0, adx_threshold))),
        rsi_oversold=float(raw.get("rsi_oversold", 35.0)),
        rsi_overbought=float(raw.get("rsi_overbought", 65.0)),
    )


def _build_supertrend_config(config: dict) -> EnhancedSuperTrendStrategyConfig:
    """Build EnhancedSuperTrendStrategyConfig from nested config."""
    raw = _nested_config(config, "supertrend_config")
    return EnhancedSuperTrendStrategyConfig(
        st_period=int(raw.get("st_period", 10)),
        st_multiplier=float(raw.get("st_multiplier", 3.0)),
        adx_period=int(raw.get("adx_period", 14)),
        adx_threshold=float(raw.get("adx_threshold", 25.0)),
        tm_cci_period=int(raw.get("tm_cci_period", 20)),
        tm_atr_period=int(raw.get("tm_atr_period", 10)),
        tm_atr_mult=float(raw.get("tm_atr_mult", 1.0)),
    )


def make_engine(config: dict):
    """Factory: build CompositeBacktestSignalEngine from config dict."""
    variant = str(config.get("strategy_variant", "composite")).lower()

    sources = []
    if variant in ("composite", "mtes", "mtes_only", "mtesv3", "mtesv3_only"):
        sources.append(
            MTESv3TrendStrategy(
                mtes_config=_build_mtes_config(config),
                strategy_config=TrendStrategyConfig(
                    min_valid_confidence=float(
                        _nested_config(config, "mtes_config").get("min_valid_confidence", 0.30)
                    )
                ),
            )
        )

    if variant in ("composite", "supertrend", "supertrend_only", "st", "st_only"):
        sources.append(
            EnhancedSuperTrendStrategy(
                config=_build_supertrend_config(config),
                strategy_config=TrendStrategyConfig(),
            )
        )

    if not sources:
        raise ValueError(f"Unsupported strategy_variant: {variant!r}")

    composite = CompositeTrendStrategy(sources=sources)
    return CompositeBacktestSignalEngine(
        composite=composite,
        atr_multiplier=float(config.get("atr_multiplier", 2.0)),
        atr_period=int(config.get("atr_period", 14)),
    )


class SignalEngine:
    """Entry point called by ``backtest.runner``."""

    def __init__(self, config: dict | None = None):
        self._config = config or _load_adjacent_config()
        self._engine = make_engine(self._config)

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """Generate composite signals for backtest."""
        return self._engine.generate(data_map)

    def get_signal_output(self):
        """Return key-node signal output for downstream artifact writers."""
        per_source = getattr(self._engine, "_per_source_signals", {})
        return self._engine._recorder.to_output(per_source)
