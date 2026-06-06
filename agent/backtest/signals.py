"""Key-node signal infrastructure for backtest engines.

Records directional/readiness state transitions as KeyNodeSignals —
the critical inflection points where the composite strategy's opinion
of the market changes meaningfully (D-01 / D-02).

Architecture:
    backtest/signals.py  ←  KeyNodeSignal, CompositeSignalOutput, KeyNodeSignalRecorder
    backtest/models.py  ←  TradeRecord, Position (output models)
    src/strategies/composite/base.py  ←  TradingSignal (upstream contract)
"""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

if TYPE_CHECKING:
    from src.strategies.composite.base import TradingSignal


# ---------------------------------------------------------------------------
# Signal contracts
# ---------------------------------------------------------------------------

@dataclass
class KeyNodeSignal:
    """A significant state transition at a specific timestamp.

    Emitted whenever the composite strategy's direction or readiness
    changes in a meaningful way, or on the first bar of a backtest.

    Args:
        timestamp: Bar timestamp.
        symbol: Instrument identifier.
        direction: BULL/BEAR/NEUTRAL (mirrors TradingSignal.direction).
        readiness: READY/WAIT/BLOCKED/EXHAUSTED/UNKNOWN.
        signal_score: Composite score (-100..100, direction-aware).
        components: Per-source score contributions.
        entry_action: OPEN_LONG / OPEN_SHORT / CLOSE / HOLD.
        reason: Human-readable explanation of why this is a key node.
        atr_trailing_stop: Optional ATR-based trailing stop level.
    """

    timestamp: pd.Timestamp
    symbol: str
    direction: Literal["BULL", "BEAR", "NEUTRAL"]
    readiness: Literal["READY", "WAIT", "BLOCKED", "EXHAUSTED", "UNKNOWN"]
    signal_score: float
    components: dict[str, float]
    entry_action: Literal["OPEN_LONG", "OPEN_SHORT", "CLOSE", "HOLD"]
    reason: str
    atr_trailing_stop: Optional[float] = None


@dataclass
class CompositeSignalOutput:
    """Complete output of the key-node signal recorder.

    Encapsulates all recorded key nodes plus raw per-source signal data
    and configuration metadata for downstream consumers.

    Args:
        key_nodes: Chronological list of KeyNodeSignals.
        per_source_signals: source_name → list of TrendResult dicts.
        metadata: atr_period, atr_multiplier, recorder config.
    """

    key_nodes: List[KeyNodeSignal] = field(default_factory=list)
    per_source_signals: dict[str, List[dict]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Action mapping helpers
# ---------------------------------------------------------------------------

def _direction_readiness_to_action(
    direction: str,
    readiness: str,
) -> Literal["OPEN_LONG", "OPEN_SHORT", "HOLD"]:
    """Map direction + readiness to an entry action (D-01 / D-02).

    BULL + READY  → OPEN_LONG
    BEAR + READY  → OPEN_SHORT
    otherwise      → HOLD
    """
    if direction == "BULL" and readiness == "READY":
        return "OPEN_LONG"
    if direction == "BEAR" and readiness == "READY":
        return "OPEN_SHORT"
    return "HOLD"


# ---------------------------------------------------------------------------
# KeyNodeSignalRecorder
# ---------------------------------------------------------------------------

class KeyNodeSignalRecorder:
    """Records significant directional / readiness state transitions.

    This is the "key node" filter: a record is stored only when the
    composite strategy's direction or readiness changes meaningfully
    (or on the very first bar, where there is no prior state).

    Usage::

        rec = KeyNodeSignalRecorder(emit_all=False)
        rec.record("GC=F", signal, "OPEN_LONG", atr_trailing_stop=1850.0)
        rec.record("GC=F", signal2, "CLOSE")
        df = rec.to_dataframe()
        output = rec.to_output(per_source={"trend_fusion": [...]})
    """

    def __init__(self, emit_all: bool = False) -> None:
        """Initialise the recorder.

        Args:
            emit_all: If True, emit a KeyNodeSignal on every bar (debug).
                      If False (default), emit only on state transitions.
        """
        self.emit_all = emit_all
        self._prev: Dict[str, "TradingSignal"] = {}  # symbol → last signal
        self._records: List[KeyNodeSignal] = []

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def record(
        self,
        symbol: str,
        signal: "TradingSignal",
        action: Literal["OPEN_LONG", "OPEN_SHORT", "CLOSE", "HOLD"],
        atr_trailing_stop: Optional[float] = None,
    ) -> None:
        """Store a KeyNodeSignal for the given bar, if it is a key node.

        Args:
            symbol: Instrument identifier.
            signal: Current TradingSignal from the composite strategy.
            action: Computed entry action for this bar.
            atr_trailing_stop: Optional ATR trailing stop level.
        """
        if self.emit_all or self._is_key_node(symbol, signal):
            self._records.append(
                KeyNodeSignal(
                    timestamp=signal.metadata.get("timestamp", pd.Timestamp("NaT")),
                    symbol=symbol,
                    direction=signal.direction,
                    readiness=signal.readiness,
                    signal_score=signal.signal_score,
                    components=signal.components,
                    entry_action=action,
                    reason=self._build_reason(signal),
                    atr_trailing_stop=atr_trailing_stop,
                )
            )
        self._prev[symbol] = signal

    def _is_key_node(self, symbol: str, signal: "TradingSignal") -> bool:
        """Return True when direction or readiness changed (or first bar)."""
        prev = self._prev.get(symbol)
        if prev is None:
            return True
        return prev.direction != signal.direction or prev.readiness != signal.readiness

    def _build_reason(self, signal: "TradingSignal") -> str:
        """Build a human-readable reason string for the signal."""
        parts = [
            f"direction={signal.direction}",
            f"readiness={signal.readiness}",
            f"score={signal.signal_score:.1f}",
        ]
        if signal.reasons:
            parts.append(f"reasons={signal.reasons}")
        if signal.warnings:
            parts.append(f"warnings={signal.warnings}")
        return "; ".join(parts)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """Convert all recorded KeyNodeSignals to a pandas DataFrame."""
        if not self._records:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "symbol",
                    "direction",
                    "readiness",
                    "signal_score",
                    "components",
                    "entry_action",
                    "reason",
                    "atr_trailing_stop",
                ]
            )
        rows = [
            {
                "timestamp": r.timestamp,
                "symbol": r.symbol,
                "direction": r.direction,
                "readiness": r.readiness,
                "signal_score": r.signal_score,
                "components": r.components,
                "entry_action": r.entry_action,
                "reason": r.reason,
                "atr_trailing_stop": r.atr_trailing_stop,
            }
            for r in self._records
        ]
        return pd.DataFrame(rows)

    def to_output(
        self,
        per_source: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CompositeSignalOutput:
        """Build a CompositeSignalOutput from recorded signals.

        Args:
            per_source: source_name → list of TrendResult dicts.
            metadata: Recorder / engine metadata (atr_period, atr_multiplier, ...).
        """
        return CompositeSignalOutput(
            key_nodes=list(self._records),
            per_source_signals=per_source or {},
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all state — call at the start of a new backtest run."""
        self._prev.clear()
        self._records.clear()

    def __len__(self) -> int:
        """Return the number of recorded key-node signals."""
        return len(self._records)
