# Phase 09: composite-strategy-backtest - Research

**Researched:** 2026-06-06
**Domain:** Python backtest engine integration, TradingSignal contract, YAML-driven strategy configuration
**Confidence:** HIGH

## Summary

Phase 09 is about connecting the Phase 08 `CompositeTrendStrategy` (which outputs `TradingSignal` objects with BULL/BEAR/NEUTRAL + READY/WAIT/BLOCKED semantics) into the existing backtest engine framework. The backtest engine already has a well-structured `SignalEngine` interface via `signal_engine.generate(data_map) -> Dict[str, pd.Series]`, and the existing `BaseEngine` already handles bar-by-bar position management. The main new work is: (1) a `CompositeBacktestSignalEngine` class that adapts `CompositeTrendStrategy` to the engine interface, (2) the trailing-stop position manager that implements D-01/D-02, (3) a YAML config file, and (4) the composite-specific reporting layer (METR-01/02/03, RPT-01/02/03).

The existing `backtest/strategies/composer.py` (StrategyComposer) is an older parallel composition system using the legacy three-layer (Trend+Pullback+Entry) architecture with DataFrame-based signals. It does NOT conflict with `CompositeTrendStrategy` -- they are separate, with `CompositeTrendStrategy` being the newer canonical system. No code from `composer.py` needs to be modified.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TradingSignal-to-position mapping | Backtest engine | CompositeBacktestSignalEngine | Engine owns position lifecycle; adapter translates signals |
| Trailing stop (D-02) | Backtest engine | PositionManager | Engine tracks entry high/low per position |
| YAML config loading | Strategy adapter | registry.py | Adapter reads YAML; registry pattern reused |
| Per-source signal tracking (BKST-03) | Backtest engine | SignalRecorder | Engine accumulates per-bar signals for reporting |
| Metrics computation | Backtest engine | calc_metrics | Existing metrics.py extended for composite |
| Composite comparison report | Reporting layer | StrategyComparator | Existing comparison.py extended |

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01**: BULL + READY = open long; BEAR + READY = open short; otherwise flat
- **D-02**: 2xATR trailing stop from entry high/low (ATR period=14 standard)
- **D-03**: YAML config + existing registry.py pattern
- **D-04**: Key-node signal output only (direction flip or readiness change)

### Claude's Discretion

YAML config format follows existing backtest conventions (registry.py pattern).

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BKST-01 | Backtest supports CompositeTrendStrategy as strategy source | `CompositeTrendStrategy.analyze(df)` interface confirmed; wraps MTESv3+SuperTrend as TrendStrategyBase |
| BKST-02 | Backtest supports MTES v3 + SuperTrend composite config | MTESv3TrendStrategy + EnhancedSuperTrendStrategy both implement TrendStrategyBase; already registered |
| BKST-03 | Backtest outputs per-source and composite signals | Key-node recording approach; `TradingSignal.source_results` contains per-source TrendResult dicts |
| METR-01 | Composite vs single strategy return comparison | StrategyComparator in comparison.py extended; existing `add_from_run_card` reuses metrics dict |
| METR-02 | Win rate, Sharpe, max drawdown | calc_metrics in metrics.py already computes all three |
| METR-03 | Per-strategy-source individual performance | Per-symbol stats already in by_symbol_stats; extendable for per-source breakdown |
| DATA-01 | 2-year data (2024-2026) | Data range passed via config; loader.fetch() supports date range |
| DATA-02 | Watchlist major instruments | Symbol list in YAML config |
| DATA-03 | 1D and 4H timeframes | loader.fetch(interval="1D"/"4H") supported |
| RPT-01 | Composite vs single strategy comparison report | StrategyComparator.to_markdown() + generate_standard_report() in comparison.py |
| RPT-02 | Best strategy combo identification | get_best() / get_winners() in StrategyComparator |
| RPT-03 | Data quality checks | loader.fetch validates data; backtest runner checks data_map |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | existing | DataFrames, OHLCV processing | Core data layer |
| numpy | existing | ATR computation, statistics | Metrics calculations |
| pydantic | existing | YAML config validation | Existing backtest uses pydantic models |
| yaml (PyYAML) | existing | YAML config loading | Existing project convention |

**Installation:** All dependencies are already present in the project environment. No new packages needed.

---

## Architecture Patterns

### System Architecture Diagram

```
[composite_backtest.yaml]
         │
         ▼
[CompositeBacktestSignalEngine]          # New: adapts TradingSignal → engine interface
    │
    ├── reads config (YAML)
    ├── instantiates MTESv3TrendStrategy + EnhancedSuperTrendStrategy
    ├── instantiates CompositeTrendStrategy([sources])
    │
    ▼
[BaseEngine._execute_bars()]             # Existing: bar-by-bar loop
    │
    ├── for each bar:
    │     engine.generate(data_map) → signal_map
    │       → CompositeTrendStrategy.analyze(df) → TradingSignal
    │       → CompositeBacktestSignalEngine._to_series(signal) → pd.Series
    │
    │     _rebalance(target_weight)
    │       → [PositionManager] checks D-01 (BULL+READY/BEAR+READY → flat)
    │       → [PositionManager] checks 2xATR trailing stop
    │
    │     _close_position(exit_reason="trailing_stop")
    │
    │     [SignalRecorder] records key-node signals
    │
    ▼
[Output]
    ├── TradeRecord list + EquitySnapshot series (existing)
    ├── signals_key_nodes.csv (NEW: key-node signal records)
    ├── signals_per_source.json (NEW: per-source breakdowns)
    ├── metrics.csv (existing calc_metrics)
    └── run_card.json (existing)
```

### Recommended Project Structure

```
agent/backtest/
├── engines/
│   └── composite_engine.py          # New: CompositeBacktestSignalEngine + PositionManager
├── strategies/
│   └── (no changes needed)
├── configs/
│   └── composite_backtest.yaml      # New: YAML config for composite backtest
├── signals.py                       # New: key-node signal models + recorder
└── (existing files unchanged)
```

### Pattern 1: SignalEngine Adapter

**What:** A class that wraps `CompositeTrendStrategy` and implements the engine interface `generate(data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]`.

**When to use:** Connecting the Phase 08 TradingSignal contract to the existing backtest engine.

**Source:** Inferred from existing engine patterns in `backtest/engines/base.py` and `runner.py`.

```python
# Source: based on existing SignalEngine interface (runner.py line 400-403)
class CompositeBacktestSignalEngine:
    """Adapts CompositeTrendStrategy to the backtest engine signal interface."""

    def __init__(self, composite: "CompositeTrendStrategy"):
        self.composite = composite

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signals = {}
        for symbol, df in data_map.items():
            ts = self.composite.analyze(df)
            # Convert TradingSignal → float signal series (-1, 0, 1)
            # D-01: BULL + READY → 1, BEAR + READY → -1, else 0
            direction_map = {"BULL": 1, "BEAR": -1, "NEUTRAL": 0}
            direction_val = direction_map.get(ts.direction, 0)
            readiness_ok = ts.readiness == "READY"
            signals[symbol] = pd.Series(
                [direction_val if readiness_ok else 0],
                index=[df.index[-1]]
            )
        return signals
```

### Pattern 2: PositionManager with Trailing Stop (D-02)

**What:** Manages positions with 2xATR trailing stop. Tracks entry_highest/entry_lowest per position and exits when price crosses the stop level.

**When to use:** For the trailing stop logic required by D-02.

```python
# Source: D-02 from CONTEXT.md
class PositionManager:
    """Manages positions with D-01/D-02 logic."""

    ATR_PERIOD = 14  # standard ATR period

    def __init__(self, atr_multiplier: float = 2.0):
        self.atr_multiplier = atr_multiplier
        self._entry_highest: Dict[str, float] = {}  # symbol → highest high since entry
        self._entry_lowest: Dict[str, float] = {}   # symbol → lowest low since entry
        self._atr: Dict[str, float] = {}             # symbol → current ATR

    def update(self, symbol: str, bar: pd.Series) -> Optional[str]:
        """Check trailing stop. Returns exit reason if should exit, else None."""
        if symbol not in self._entry_highest:
            return None
        high, low, close = bar["high"], bar["low"], bar["close"]
        self._entry_highest[symbol] = max(self._entry_highest[symbol], high)
        self._entry_lowest[symbol] = min(self._entry_lowest[symbol], low)

        # Update ATR
        from src.indicators.standard import atr as _atr_func
        # Note: ATR computed from df in engine, not here

        pos = self.positions.get(symbol)
        if pos is None:
            return None

        stop_level = self._calc_stop(symbol, pos.direction)
        if pos.direction == 1 and low <= stop_level:
            return "trailing_stop_long"
        if pos.direction == -1 and high >= stop_level:
            return "trailing_stop_short"
        return None

    def record_entry(self, symbol: str, direction: int, bar: pd.Series) -> None:
        self._entry_highest[symbol] = bar["high"]
        self._entry_lowest[symbol] = bar["low"]

    def _calc_stop(self, symbol: str, direction: int) -> float:
        if direction == 1:
            return self._entry_highest[symbol] - self.atr_multiplier * self._atr[symbol]
        else:
            return self._entry_lowest[symbol] + self.atr_multiplier * self._atr[symbol]
```

### Pattern 3: Key-Node Signal Recorder (D-04)

**What:** Records only bars where direction flips or readiness changes, not every bar.

**When to use:** Per-bar signal recording for BKST-03 and downstream reporting.

```python
# Source: D-04 from CONTEXT.md
@dataclass
class KeyNodeSignal:
    timestamp: pd.Timestamp
    symbol: str
    direction: str          # BULL/BEAR/NEUTRAL
    readiness: str          # READY/WAIT/BLOCKED
    signal_score: float
    components: dict        # per-source scores
    entry_action: str       # OPEN/CLOSE/HOLD
    reason: str             # why the action was taken

class KeyNodeSignalRecorder:
    """Records signals only at key nodes (direction flip or readiness change)."""

    def __init__(self):
        self._prev_signals: Dict[str, TradingSignal] = {}
        self._records: List[KeyNodeSignal] = []

    def record(self, symbol: str, signal: TradingSignal, action: str, timestamp: pd.Timestamp):
        prev = self._prev_signals.get(symbol)
        # Key-node: direction changed OR readiness changed
        is_key = (
            prev is None
            or prev.direction != signal.direction
            or prev.readiness != signal.readiness
        )
        if is_key:
            self._records.append(KeyNodeSignal(
                timestamp=timestamp,
                symbol=symbol,
                direction=signal.direction,
                readiness=signal.readiness,
                signal_score=signal.signal_score,
                components=signal.components,
                entry_action=action,
                reason=f"direction={signal.direction}, readiness={signal.readiness}",
            ))
        self._prev_signals[symbol] = signal

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "timestamp": r.timestamp,
            "symbol": r.symbol,
            "direction": r.direction,
            "readiness": r.readiness,
            "signal_score": r.signal_score,
            "entry_action": r.entry_action,
        } for r in self._records])
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ATR computation | Custom ATR rolling window | `src.indicators.standard.atr(df)` | Already implemented via ta-lib adapter; tested |
| Metrics calculation | Custom Sharpe/max-drawdown | `backtest/metrics.calc_metrics()` | Already handles annualization, Sortino, Calmar |
| Strategy comparison table | Custom comparison logic | `backtest/strategies/comparison.py` | Already has `StrategyComparator`, `to_markdown()`, `to_dataframe()` |
| YAML config loading | ad-hoc YAML parsing | Extend existing `registry.py` pattern | Consistent with project conventions |
| Run card generation | Custom JSON output | `backtest/run_card.write_run_card()` | Already handles config hashing, artifact listing |

**Key insight:** The backtest engine is well-structured with clear extension points. The new code adds one adapter class and one position manager -- everything else reuses existing infrastructure.

---

## Runtime State Inventory

> Not applicable — Phase 09 is a greenfield feature addition, not a rename/refactor/migration.

---

## Common Pitfalls

### Pitfall 1: Misusing CompositeSignal vs TradingSignal
**What goes wrong:** `backtest/strategies/composer.py` has a `CompositeSignal` dataclass that is completely different from the Phase 08 `TradingSignal`. Both names exist in the codebase.
**Why it happens:** Two different composition systems with similar names.
**How to avoid:** The new adapter explicitly uses `TradingSignal` (from `src.strategies.composite.base`) and `CompositeTrendStrategy` (from `src.strategies.composite.trend_composite`). Never import from `backtest.strategies.composer` for Phase 09.
**Warning signs:** TypeError about missing `state` attribute on TradingSignal.

### Pitfall 2: ATR Per-Bar vs Lookback ATR
**What goes wrong:** ATR is computed over a lookback window, but the trailing stop needs the "current bar's ATR." Using `df.iloc[-1]` for ATR gives the value at the close of the last completed bar, which is correct for signal purposes.
**Why it happens:** ATR is a trailing indicator; the value at bar N is computed using bars N-ATR_period to N.
**How to avoid:** Compute ATR as a column on the DataFrame before calling `analyze()`. `CompositeTrendStrategy` receives the full df with ATR available in `df["atr"]` if the loader provides it, or compute it in the adapter. Standard ATR period is 14.
**Warning signs:** ATR value changes unexpectedly between calls.

### Pitfall 3: Position Manager Not Reset Between Symbols
**What goes wrong:** `_entry_highest` and `_entry_lowest` dicts accumulate across symbols, causing wrong trailing stop levels for a symbol that had a previous position.
**Why it happens:** Shared dict state not cleared per symbol.
**How to avoid:** Clear entry tracking when a position closes, not just when opened. Use `_on_close` hook in PositionManager.
**Warning signs:** First trade after a previous symbol's position has wrong entry_highest.

### Pitfall 4: signal_engine.py Path Assumption
**What goes wrong:** `runner.py` loads `run_dir / "code" / "signal_engine.py"` and the engine class must be named exactly `SignalEngine`. If the file uses a different class name, the runner silently fails.
**Why it happens:** `getattr(signal_module, "SignalEngine", None)` returns None and prints an error.
**How to avoid:** Name the class `SignalEngine` in the generated `signal_engine.py` file. Document this constraint clearly in the YAML config comment.
**Warning signs:** `json.dumps({"error": "SignalEngine class not found..."})` in output.

---

## Code Examples

### Example: signal_engine.py Skeleton (for the YAML-generated file)

```python
"""Auto-generated signal engine for composite backtest."""

from __future__ import annotations
from typing import Dict
import pandas as pd

from src.strategies.trend.mtes_v3 import MTESv3, MTESv3Config
from src.strategies.trend.enhanced_supertrend import EnhancedSuperTrend
from src.strategies.trend.base import TrendStrategyConfig
from src.strategies.trend.mtes_v3 import MTESv3TrendStrategy
from src.strategies.trend.enhanced_supertrend import EnhancedSuperTrendStrategy
from src.strategies.composite.trend_composite import CompositeTrendStrategy
from agent.backtest.engines.composite_engine import CompositeBacktestSignalEngine


def make_engine(config: dict):
    """Factory: build CompositeBacktestSignalEngine from config dict."""
    # MTES v3 source
    mtes_config = MTESv3Config(**config.get("mtes_config", {}))
    mtes_strategy = MTESv3TrendStrategy(
        mtes_config=mtes_config,
        strategy_config=TrendStrategyConfig(),
    )

    # Enhanced SuperTrend source
    st_config = config.get("supertrend_config", {})
    st_strategy = EnhancedSuperTrendStrategy(
        config=None,  # use defaults, override below
        strategy_config=TrendStrategyConfig(),
    )

    # Composite
    composite = CompositeTrendStrategy(
        sources=[mtes_strategy, st_strategy],
    )

    return CompositeBacktestSignalEngine(
        composite=composite,
        atr_multiplier=config.get("atr_multiplier", 2.0),
        atr_period=config.get("atr_period", 14),
    )


class SignalEngine:
    """Entry point called by runner.py."""

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._engine = make_engine(self._config)

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        return self._engine.generate(data_map)
```

### Example: YAML Config (D-03)

```yaml
# Source: D-03 from CONTEXT.md — YAML config + existing registry pattern
# agent/backtest/configs/composite_backtest.yaml

# ── Backtest parameters ──────────────────────────────────────
codes:
  - "GC=F"      # Gold
  - "SI=F"      # Silver
  - "CL=F"      # Crude oil

start_date: "2024-01-01"
end_date: "2026-01-01"
interval: "1D"
source: "yfinance"

# ── Capital & fees ────────────────────────────────────────────
initial_cash: 1000000
commission: 0.001    # 0.1% per side

# ── MTES v3 configuration (source 1) ──────────────────────────
mtes_config:
  fast_ema: 12
  slow_ema: 26
  adx_period: 14
  adx_threshold: 25.0

# ── Enhanced SuperTrend configuration (source 2) ──────────────
supertrend_config:
  st_period: 10
  st_multiplier: 3.0
  adx_period: 14
  adx_threshold: 25.0
  tm_cci_period: 20
  tm_atr_period: 10
  tm_atr_mult: 1.0

# ── Composite composition ─────────────────────────────────────
composition:
  type: "unanimous"   # all sources must agree (D-01 semantic)

# ── Position management ───────────────────────────────────────
position:
  atr_multiplier: 2.0    # D-02: 2xATR trailing stop
  atr_period: 14          # standard ATR period

# ── Reporting ─────────────────────────────────────────────────
reporting:
  output_dir: "runs/composite_gc/"
  emit_key_nodes: true    # D-04: only direction flip / readiness change
  compare_single: true      # METR-01: also run MTESv3 alone + SuperTrend alone
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Backtest strategies use BaseStrategy.generate(df) → DataFrame | CompositeTrendStrategy.analyze(df) → TradingSignal | Phase 08 | Signal contract now typed, composable, with explainability |
| StrategyComposer chains Trend+Pullback+Entry on same df | CompositeTrendStrategy aggregates two trend strategies | Phase 08 | Different composition semantics; no conflict, separate code paths |
| Exit only on signal reversal | 2xATR trailing stop from entry high/low | Phase 09 (D-02) | Positions get room to breathe; adapts to volatility |

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ATR column is available in data_map DataFrames (or can be added by the adapter) | Pitfall 2 | ATR would need to be computed inside the adapter; low risk — ta library is already installed |
| A2 | `backtest/configs/` directory does not exist yet and should be created | Standard Stack | If directory already exists, configs go there; minimal risk |
| A3 | The `SignalEngine` class in `signal_engine.py` must be named exactly `SignalEngine` (not `CompositeSignalEngine`) | Pitfall 4 | Runner would fail to find the class; documented constraint |
| A4 | Key-node signal recording can be done as a side-effect of `_execute_bars` without modifying `BaseEngine` itself | Architecture | If BaseEngine needs modification, more invasive; monitor this |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **ATR in data_map DataFrames**: Does the data loader (yfinance/tushare) already provide an `atr` column, or must the adapter compute it? The MTES v3 and SuperTrend strategies internally compute ATR, but the trailing stop needs it at the engine level.
   - What we know: `src/indicators/standard.atr(df)` exists and works. The adapter can call it on `df` before passing to `CompositeTrendStrategy.analyze()`.
   - What's unclear: Whether ATR needs to be stored per-bar for the position manager to use.
   - Recommendation: Compute ATR in the adapter's `generate()` loop before calling `analyze()`, attach to df as `df["atr"]`.

2. **BKST-03 per-source signal output format**: The requirement says "per-source independent signals." Should this be one CSV with all signals (composite + per-source), or separate files?
   - What we know: `TradingSignal.source_results` contains serializable TrendResult dicts per source.
   - What's unclear: Preferred output format for downstream consumers.
   - Recommendation: Write `signals_per_source.json` (structured, easy to parse) + flatten to `signals_per_source.csv` (tabular, easy to visualize).

3. **Comparison vs single strategy runs**: METR-01 requires running MTESv3 alone and SuperTrend alone. Should this be done in one backtest run or three separate runs?
   - What we know: `StrategyComparator` can compare from separate run_card.json files.
   - What's unclear: Whether the single-run approach (all three strategies produce signals, only composite is traded) can also emit per-source metrics.
   - Recommendation: Three separate backtest runs for clean isolation, then use `StrategyComparator` for METR-01. This matches how `comparison.py` is designed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pandas | All backtest components | Yes (existing) | pinned | None needed |
| numpy | Metrics, ATR | Yes (existing) | pinned | None needed |
| pydantic | Config validation | Yes (existing) | pinned | None needed |
| PyYAML | YAML config loading | Yes (existing) | pinned | None needed |
| ta library | ATR computation | Yes (existing) | pinned | None needed |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini (existing at agent root) |
| Quick run command | `python -m pytest agent/backtest/ -x -q --tb=short` |
| Full suite command | `python -m pytest agent/ -x -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BKST-01 | CompositeTrendStrategy wired into backtest | unit | `pytest agent/backtest/engines/test_composite_engine.py -x` | Wave 0 (new file) |
| BKST-02 | MTESv3 + SuperTrend config loaded from YAML | unit | `pytest agent/backtest/engines/test_composite_engine.py -k yaml -x` | Wave 0 (new file) |
| BKST-03 | Per-source and composite signals in output | unit | `pytest agent/backtest/engines/test_composite_engine.py -k signals -x` | Wave 0 (new file) |
| D-01 | BULL+READY→long, BEAR+READY→short, else flat | unit | `pytest agent/backtest/engines/test_composite_engine.py -k direction -x` | Wave 0 (new file) |
| D-02 | 2xATR trailing stop triggers exit | unit | `pytest agent/backtest/engines/test_composite_engine.py -k trailing -x` | Wave 0 (new file) |
| D-04 | Only key-node signals recorded | unit | `pytest agent/backtest/engines/test_composite_engine.py -k keynode -x` | Wave 0 (new file) |
| METR-01 | StrategyComparator compares composite vs single | unit | `pytest agent/backtest/strategies/test_comparison.py -x` | existing test file? |
| METR-02 | calc_metrics returns Sharpe/maxDD/win_rate | unit | `pytest agent/backtest/test_metrics.py -x` | existing test file? |

### Sampling Rate
- **Per task commit:** `python -m pytest agent/backtest/engines/test_composite_engine.py -x -q`
- **Per wave merge:** `python -m pytest agent/backtest/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `agent/backtest/engines/test_composite_engine.py` — tests for CompositeBacktestSignalEngine, PositionManager, D-01/D-02/D-04
- [ ] `agent/backtest/engines/test_signal_recorder.py` — tests for KeyNodeSignalRecorder
- Framework install: already present (pytest.ini exists)

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

---

## Security Domain

> Not applicable — Phase 09 is a backtesting infrastructure phase with no external input, network access, or user data.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — backtest runs offline |
| V3 Session Management | No | N/A — no sessions |
| V4 Access Control | No | N/A — local computation only |
| V5 Input Validation | Yes | YAML config validated with pydantic; DataFrame columns checked by validate() |
| V6 Cryptography | No | N/A — no sensitive data |

---

## Sources

### Primary (HIGH confidence)

- `agent/src/strategies/composite/base.py` — TradingSignal contract, SignalDirection, SignalReadiness (D-01/D-02, Phase 08)
- `agent/src/strategies/composite/trend_composite.py` — CompositeTrendStrategy interface, `analyze(df) -> TradingSignal`
- `agent/src/strategies/trend/base.py` — TrendStrategyBase, TrendResult (Phase 08)
- `agent/backtest/engines/base.py` — BaseEngine, `_execute_bars`, `_rebalance`, `_close_position` (existing engine interface)
- `agent/backtest/runner.py` — runner main(), SignalEngine class discovery, data loading (existing)
- `agent/backtest/models.py` — Position, TradeRecord, EquitySnapshot (existing output schema)
- `agent/backtest/strategies/comparison.py` — StrategyComparator, StrategyMetrics, `generate_standard_report()` (METR-01)
- `agent/backtest/metrics.py` — calc_metrics, win_rate_and_stats (METR-02)

### Secondary (MEDIUM confidence)

- `agent/backtest/run_card.py` — write_run_card, run_card schema (extension point for new outputs)
- `agent/src/strategies/trend/mtes_v3.py` — MTESv3TrendStrategy implements TrendStrategyBase (BKST-02)
- `agent/src/strategies/trend/enhanced_supertrend.py` — EnhancedSuperTrendStrategy implements TrendStrategyBase (BKST-02)
- `agent/src/indicators/standard.py` — `atr()` function via ta adapter (D-02)

### Tertiary (LOW confidence)

- `agent/backtest/strategies/composer.py` — StrategyComposer (older composition system, confirmed non-conflicting through file inspection)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies verified in existing project
- Architecture: HIGH — all patterns based on verified existing code
- Pitfalls: HIGH — identified through codebase analysis of actual class interfaces

**Research date:** 2026-06-06
**Valid until:** 2026-07-06 (30 days — backtest engine patterns are stable)
