"""Composite backtest signal engine with D-01 direction mapping and D-02 trailing stop.

Architecture:
    backtest/engines/composite_engine.py
        CompositeBacktestSignalEngine  — bar-by-bar signal + ATR generation
        PositionManager               — D-02 ATR-based trailing stop tracker
        CompositeEngine               — extends BaseEngine, runs backtest + writes artifacts
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from backtest.csv_safety import safe_to_csv
from backtest.signals import KeyNodeSignalRecorder
from src.indicators.standard import atr as compute_atr
from src.strategies.composite.trend_composite import CompositeTrendStrategy
from src.tools.path_utils import safe_run_dir

_MAX_PER_SOURCE_SIGNAL_RECORDS_ENV = "VIBE_TRADING_MAX_PER_SOURCE_SIGNAL_RECORDS"
_DEFAULT_MAX_PER_SOURCE_SIGNAL_RECORDS = 100_000


def _env_int(name: str, default: int) -> int:
    """Return a positive integer environment setting or its default."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _max_per_source_signal_records() -> int:
    """Return the maximum stored per-source signal artifact records."""
    return _env_int(
        _MAX_PER_SOURCE_SIGNAL_RECORDS_ENV,
        _DEFAULT_MAX_PER_SOURCE_SIGNAL_RECORDS,
    )


# ---------------------------------------------------------------------------
# D-02: Position Manager (trailing stop via ATR)
# ---------------------------------------------------------------------------

class PositionManager:
    """Tracks per-symbol entry state for ATR-based trailing stop (D-02).

    State is fully isolated per symbol.  Reset between backtest runs.

    Args:
        atr_multiplier: Stop distance = atr_multiplier * ATR.
        atr_period: ATR period used in compute_atr().
    """

    def __init__(
        self,
        atr_multiplier: float = 2.0,
        atr_period: int = 14,
    ) -> None:
        self.atr_multiplier = atr_multiplier
        self.atr_period = atr_period

        # Per-symbol state
        self._entry_high: Dict[str, float] = {}  # highest high since entry
        self._entry_low: Dict[str, float] = {}   # lowest low since entry
        self._atr: Dict[str, float] = {}          # current ATR value
        self._direction: Dict[str, int] = {}       # 1 (long) / -1 (short) / 0 (flat)
        self._signal_ema_high: Dict[str, float] = {}  # intra-bar tracked high
        self._signal_ema_low: Dict[str, float] = {}   # intra-bar tracked low

    # ------------------------------------------------------------------
    # State update API
    # ------------------------------------------------------------------

    def update_entry(self, symbol: str, bar: pd.Series) -> None:
        """Initialise entry state on bar of position opening."""
        self._entry_high[symbol] = float(bar["high"])
        self._entry_low[symbol] = float(bar["low"])
        self._signal_ema_high[symbol] = float(bar["high"])
        self._signal_ema_low[symbol] = float(bar["low"])

    def update_trailing(self, symbol: str, bar: pd.Series) -> None:
        """Update intra-bar EMA-like high/low for stop-level tracking."""
        if symbol in self._signal_ema_high:
            self._signal_ema_high[symbol] = max(
                self._signal_ema_high[symbol], float(bar["high"])
            )
        if symbol in self._signal_ema_low:
            self._signal_ema_low[symbol] = min(
                self._signal_ema_low[symbol], float(bar["low"])
            )

    def update_atr(self, symbol: str, atr_value: float) -> None:
        """Store the current ATR value for the given symbol."""
        self._atr[symbol] = float(atr_value)

    def set_direction(self, symbol: str, direction: int) -> None:
        """Record current holding direction for the symbol (1 / -1 / 0)."""
        self._direction[symbol] = direction

    def update_all(self, symbol: str, bar: pd.Series) -> None:
        """Convenience: update trailing + ATR in one call."""
        self.update_trailing(symbol, bar)
        if "atr" in bar and pd.notna(bar["atr"]):
            self.update_atr(symbol, bar["atr"])

    # ------------------------------------------------------------------
    # D-02: Check exit
    # ------------------------------------------------------------------

    def check_exit(self, symbol: str, bar: pd.Series) -> tuple[bool, str]:
        """Return (should_exit, reason) based on ATR trailing stop.

        Long:  price drops to or below (signal_ema_high - multiplier*ATR)  → stop hit
        Short: price rises to or above (signal_ema_low  + multiplier*ATR) → stop hit
        Flat / no ATR: no exit.
        """
        direction = self._direction.get(symbol, 0)
        if direction == 0:
            return False, ""

        atr_val = self._atr.get(symbol)
        if atr_val is None or not (atr_val > 0):
            return False, ""

        stop_distance = self.atr_multiplier * atr_val

        if direction == 1:
            stop_level = self._signal_ema_high.get(symbol, float("inf")) - stop_distance
            if float(bar["low"]) <= stop_level:
                return True, "D-02_long_trailing_stop"
        elif direction == -1:
            stop_level = self._signal_ema_low.get(symbol, float("-inf")) + stop_distance
            if float(bar["high"]) >= stop_level:
                return True, "D-02_short_trailing_stop"

        return False, ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_position(self, symbol: str) -> None:
        """Clear all position state for the symbol."""
        self._entry_high.pop(symbol, None)
        self._entry_low.pop(symbol, None)
        self._atr.pop(symbol, None)
        self._direction.pop(symbol, None)
        self._signal_ema_high.pop(symbol, None)
        self._signal_ema_low.pop(symbol, None)

    def reset(self) -> None:
        """Clear all state — call at the start of a new backtest run."""
        self._entry_high.clear()
        self._entry_low.clear()
        self._atr.clear()
        self._direction.clear()
        self._signal_ema_high.clear()
        self._signal_ema_low.clear()


# ---------------------------------------------------------------------------
# D-01: Signal Engine
# ---------------------------------------------------------------------------

class CompositeBacktestSignalEngine:
    """Bar-by-bar signal generator using CompositeTrendStrategy + D-02 trailing stop.

    Each ``generate()`` call creates a fresh recorder + position manager to
    ensure clean state between runs.

    Args:
        composite: Configured CompositeTrendStrategy instance.
        atr_multiplier: ATR multiplier for trailing stop (D-02).
        atr_period: ATR period passed to ``compute_atr()``.
    """

    def __init__(
        self,
        composite: CompositeTrendStrategy,
        atr_multiplier: float = 2.0,
        atr_period: int = 14,
    ) -> None:
        self.composite = composite
        self.atr_multiplier = atr_multiplier
        self.atr_period = atr_period
        self._position_mgr = PositionManager(
            atr_multiplier=atr_multiplier,
            atr_period=atr_period,
        )
        self._recorder = KeyNodeSignalRecorder(emit_all=False)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """Generate direction signals for all symbols across all bars.

        Processes bars one-by-one to enable per-bar position-manager updates.
        Returns a dict mapping symbol → Series of direction values (1 / -1 / 0).

        D-01 mapping:
            BULL + READY  → open/hold long
            BEAR + READY  → open/hold short
            otherwise      → keep current position until D-02 trailing stop exits

        Args:
            data_map: symbol → OHLCV DataFrame (must contain 'high', 'low').

        Returns:
            Dict of symbol → pd.Series (index = df index, values = -1/0/1).
        """
        # Fresh per-run state
        self._position_mgr.reset()
        self._recorder.reset()
        self._per_source_signals: Dict[str, List[dict]] = {}
        self._per_source_record_count = 0
        self._per_source_record_limit = _max_per_source_signal_records()

        result_map: Dict[str, pd.Series] = {}

        for symbol, df in data_map.items():
            if df.empty:
                continue

            df = df.copy()
            if "atr" not in df.columns:
                df["atr"] = compute_atr(df, self.atr_period)

            values: List[float] = []
            current_direction = 0

            for bar_idx, bar in df.iterrows():
                bar_ts = pd.Timestamp(bar_idx)
                if "atr" in bar and pd.notna(bar["atr"]):
                    self._position_mgr.update_atr(symbol, float(bar["atr"]))

                try:
                    signal = self.composite.analyze(df.loc[:bar_idx])
                except Exception:
                    signal = None

                action = "HOLD"
                next_direction = current_direction

                if signal is not None:
                    signal.metadata["timestamp"] = bar_ts

                    if signal.direction == "BULL" and signal.readiness == "READY":
                        next_direction = 1
                        action = "OPEN_LONG" if current_direction != 1 else "HOLD"
                    elif signal.direction == "BEAR" and signal.readiness == "READY":
                        next_direction = -1
                        action = "OPEN_SHORT" if current_direction != -1 else "HOLD"
                    elif current_direction != 0:
                        # D-02: no eligible signal means hold until trailing stop.
                        self._position_mgr.update_trailing(symbol, bar)
                        should_exit, _reason = self._position_mgr.check_exit(symbol, bar)
                        if should_exit:
                            next_direction = 0
                            action = "CLOSE"
                    else:
                        next_direction = 0
                        action = "HOLD"

                    # Direction changes reset or clear trailing-stop state.
                    if current_direction == 0 and next_direction != 0:
                        self._position_mgr.update_entry(symbol, bar)
                    elif current_direction != 0 and next_direction == 0:
                        self._position_mgr.close_position(symbol)
                    elif current_direction != 0 and next_direction != 0 and current_direction != next_direction:
                        self._position_mgr.close_position(symbol)
                        self._position_mgr.update_entry(symbol, bar)
                    elif next_direction != 0:
                        self._position_mgr.update_trailing(symbol, bar)

                    self._position_mgr.set_direction(symbol, next_direction)

                    atr_stop = self._current_trailing_stop(symbol, next_direction)
                    self._recorder.record(symbol, signal, action, atr_trailing_stop=atr_stop)

                    for src_name, src_result in signal.source_results.items():
                        if self._per_source_record_count < self._per_source_record_limit:
                            self._per_source_signals.setdefault(src_name, []).append(src_result)
                            self._per_source_record_count += 1
                else:
                    next_direction = current_direction
                    if current_direction != 0:
                        self._position_mgr.update_trailing(symbol, bar)
                        should_exit, _reason = self._position_mgr.check_exit(symbol, bar)
                        if should_exit:
                            next_direction = 0
                            self._position_mgr.close_position(symbol)
                    self._position_mgr.set_direction(symbol, next_direction)

                current_direction = next_direction
                values.append(float(current_direction))

            if values:
                result_map[symbol] = pd.Series(values, index=df.index)

        self._latest_direction_map = {
            sym: series.iloc[-1] if len(series) > 0 else 0.0
            for sym, series in result_map.items()
        }

        return result_map

    def _current_trailing_stop(self, symbol: str, direction: int) -> float | None:
        """Return current D-02 trailing-stop level for artifact output."""
        atr_val = self._position_mgr._atr.get(symbol)
        if atr_val is None or not (atr_val > 0):
            return None
        distance = self.atr_multiplier * atr_val
        if direction == 1 and symbol in self._position_mgr._signal_ema_high:
            return self._position_mgr._signal_ema_high[symbol] - distance
        if direction == -1 and symbol in self._position_mgr._signal_ema_low:
            return self._position_mgr._signal_ema_low[symbol] + distance
        return None

    # ------------------------------------------------------------------
    # Artifact helpers (used by CompositeEngine._write_signal_artifacts)
    # ------------------------------------------------------------------

    def get_recorder(self) -> KeyNodeSignalRecorder:
        """Return the KeyNodeSignalRecorder for artifact writing."""
        return self._recorder

    def get_per_source_signals(self) -> Dict[str, List[dict]]:
        """Return per-source signal results collected during generation."""
        return getattr(self, "_per_source_signals", {})

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset recorder and position manager — called automatically by generate()."""
        self._recorder.reset()
        self._position_mgr.reset()


# ---------------------------------------------------------------------------
# D-01/D-02: CompositeEngine — extends BaseEngine
# ---------------------------------------------------------------------------

class CompositeEngine:
    """Backtest engine wiring D-01 direction mapping + D-02 trailing stop.

    Subclasses BaseEngine's shared bar-by-bar execution loop while adding
    composite-signal generation and key-node artifact writing.

    Args:
        config: Backtest configuration dict (passed to BaseEngine).
        codes: List of instrument codes.
        composite: Configured CompositeTrendStrategy instance.
        **engine_kwargs: Passed through to the underlying market engine.
    """

    def __init__(
        self,
        config: dict,
        codes: List[str],
        composite: CompositeTrendStrategy,
        **engine_kwargs: Any,
    ) -> None:
        from backtest.engines._market_hooks import _detect_market
        from backtest.engines.composite import _build_rule_engines

        # Detect market type and instantiate the appropriate engine
        markets = {_detect_market(c) for c in codes}
        if len(markets) == 1:
            market = next(iter(markets))
            rule_engine = _build_rule_engines(config, codes).get(market)
            if rule_engine is None:
                raise ValueError(f"No rule engine found for market type: {market}")
            self._engine = rule_engine
        else:
            # Multi-market: use CompositeEngine from composite.py
            from backtest.engines.composite import CompositeEngine as CE
            self._engine = CE(config, codes)

        self.config = config
        self.codes = codes
        self.composite = composite
        self._signal_engine: CompositeBacktestSignalEngine | None = None
        self._atr_multiplier = engine_kwargs.get("atr_multiplier", 2.0)
        self._atr_period = engine_kwargs.get("atr_period", 14)

    def run_backtest(
        self,
        loader: Any,
        run_dir: Path,
        bars_per_year: int = 252,
    ) -> Dict[str, Any]:
        """Run the full backtest pipeline.

        Creates a fresh CompositeBacktestSignalEngine, delegates execution to
        BaseEngine.run_backtest(), then writes key-node signal artifacts.

        Args:
            loader: DataLoader with ``fetch()`` method.
            run_dir: Artifacts output directory.
            bars_per_year: Annualisation factor.

        Returns:
            Metrics dictionary from BaseEngine.
        """
        run_dir = safe_run_dir(str(run_dir))
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create fresh signal engine for each backtest run
        self._signal_engine = CompositeBacktestSignalEngine(
            composite=self.composite,
            atr_multiplier=self._atr_multiplier,
            atr_period=self._atr_period,
        )

        # Delegate to BaseEngine.run_backtest() — CompositeBacktestSignalEngine
        # conforms to the signal_engine interface via .generate(data_map)
        metrics = self._engine.run_backtest(
            config=self.config,
            loader=loader,
            signal_engine=self._signal_engine,
            run_dir=run_dir,
            bars_per_year=bars_per_year,
        )

        # Write D-01 / D-02 signal artifacts
        self._write_signal_artifacts(run_dir)

        return metrics

    def _write_signal_artifacts(self, run_dir: Path) -> None:
        """Write key-node signal CSV and per-source JSON artifacts."""
        if self._signal_engine is None:
            return

        out = run_dir / "artifacts"
        out.mkdir(parents=True, exist_ok=True)

        # Key-node signals DataFrame
        recorder = self._signal_engine.get_recorder()
        kn_df = recorder.to_dataframe()
        if not kn_df.empty:
            safe_to_csv(kn_df, out / "signals_key_nodes.csv", index=False)

        # Per-source raw signals JSON
        per_source = self._signal_engine.get_per_source_signals()
        import json
        (out / "signals_per_source.json").write_text(
            json.dumps(per_source, indent=2, default=str),
            encoding="utf-8",
        )
