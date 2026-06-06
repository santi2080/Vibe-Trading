# Phase 09: composite-strategy-backtest - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers backtest infrastructure that integrates CompositeTrendStrategy with the existing backtest system, supports MTES v3 + SuperTrend composite configuration, and outputs per-bar trading signals for performance analysis.

The phase is about **connecting the CompositeTrendStrategy signal layer (Phase 08) to the backtest engine**, not about writing a new backtest engine from scratch. Existing backtest infrastructure (engines, strategies/, loaders/, models.py) and the Phase 08 TradingSignal contract are the foundation.
</domain>

<decisions>
## Implementation Decisions

### Signal-to-Position Mapping

- **D-01: Direction + Readiness drives position** — BULL + READY → open long; BEAR + READY → open short; all other cases → flat (no position).
  - Rationale: aligns with TradingSignal semantics where direction + readiness together represent execution eligibility.

### Non-Signal / Exit Handling

- **D-02: Default trailing stop exit** — when no directional signal or readiness condition is met, use 2×ATR trailing stop from entry high/low:
  - Long: exit when price drops to entry_highest_since_entry − 2×ATR
  - Short: exit when price rises to entry_lowest_since_entry + 2×ATR
  - Rationale: simple, adaptive, avoids premature exit on NEUTRAL noise.

### Backtest Configuration

- **D-03: YAML config + existing registry** — composite strategy config lives in a YAML file, loaded via the existing `backtest/strategies/registry.py` pattern.
  - YAML defines: MTESv3 + SuperTrend sources, weights, readiness thresholds, symbol list, timeframe, date range.
  - No new config format — reuse registry and loader patterns already in place.

### Signal Output

- **D-04: Key-node signal output only** — backtest emits signal records only on state changes (direction flip or readiness status change).
  - Each signal record: bar timestamp, direction, readiness, signal_score, components (per-source scores), entry action (OPEN/CLOSE/HOLD).
  - Rationale: storage-efficient, clear for downstream reporting (METR-01/02/03, RPT-01/02).

### Claude's Discretion

The user delegated configuration format (YAML + registry) to Claude — the pattern follows existing backtest conventions.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.1 Requirements

- `.planning/REQUIREMENTS.md` — BKST-01/02/03 (backtest infra), METR-01/02/03 (metrics), DATA-01/02/03 (data coverage), RPT-01/02/03 (reporting).

### Phase 08 decisions (signal contract — locked)

- `.planning/phases/08-establish-composite-strategy-signal-layer/08-CONTEXT.md` — D-01/D-02/D-03/D-04 lock TradingSignal direction semantics (BULL/BEAR/NEUTRAL), readiness separation, score contract, explainability fields.

### Existing backtest infrastructure

- `agent/backtest/models.py` — Position, TradeRecord, EquitySnapshot dataclasses (output target for backtest results).
- `agent/backtest/strategies/registry.py` — strategy registration pattern (extend to support composite).
- `agent/backtest/strategies/__init__.py` — existing strategy wrappers: major_trend.py, trend.py, pullback.py, entry.py, composer.py, comparison.py.
- `agent/backtest/engines/base.py` — backtest engine base class.
- `agent/backtest/runner.py` — existing backtest runner entry point.

### Strategy contract (Phase 08)

- `agent/src/strategies/trend/base.py` — canonical TrendResult, TrendStrategyBase (upstream of CompositeTrendStrategy).
- `agent/src/strategies/composite/` — CompositeTrendStrategy location (Phase 08 output).

### MTES v3 (Phase 06)

- `.planning/phases/06-mtes-v3-layered-system/06-CONTEXT.md` — MTES v3 layered evaluation architecture.
- `agent/src/strategies/trend/mtes_v3.py` — MTES v3 strategy implementation.

### SuperTrend (Phase 03)

- `.planning/phases/03-supertrend-enhancement-strategy/03-CONTEXT.md` — Enhanced SuperTrend strategy.
- `agent/src/strategies/trend/enhanced_supertrend.py` — Enhanced SuperTrend implementation.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backtest/models.py` — TradeRecord already captures: symbol, direction, entry/exit price, entry/exit time, pnl, pnl_pct, holding_bars, commission. Align backtest output with this schema.
- `backtest/strategies/registry.py` — existing strategy registration. CompositeTrendStrategy should be registered similarly with a config-driven factory.
- `backtest/strategies/composer.py` — existing composition logic may overlap with CompositeTrendStrategy. Check before building parallel code.
- `backtest/strategies/comparison.py` — existing strategy comparison. May be reusable for METR-01 (composite vs single).
- `backtest/metrics.py` — existing metric computation helpers (sharpe, max drawdown, win rate). Extend rather than rewrite.

### Established Patterns

- Backtest strategies are registered in registry.py with a name → class mapping.
- Backtest runner loads strategy from config + registry, runs over data loader, emits TradeRecord list + EquitySnapshot series.
- Phase 08 TradingSignal contract uses BULL/BEAR/NEUTRAL + READY/WAIT/BLOCKED — backtest adapter translates these to position actions.

### Integration Points

- New code: `agent/backtest/strategies/composite_signal_adapter.py` — adapts CompositeTrendStrategy to backtest engine interface.
- New config: `agent/backtest/configs/composite_backtest.yaml` — YAML config for composite backtest run.
- Extension: `agent/backtest/metrics.py` — add composite vs single comparison metrics (METR-01/02/03).
- Output: backtest results saved as CSV/JSON for RPT-01/RPT-02 downstream reporting.
</code_context>

<specifics>
## Specific Ideas

- 2×ATR trailing stop from entry high/low (D-02) — this is a simple trailing stop that adapts to volatility and gives positions room to breathe.
- Key-node signal output (D-04) — only emit when direction flips or readiness changes, not every bar. Reduces output by ~90% for typical 1D backtest.
- YAML config + registry (D-03) — keeps backtest parameters (symbol list, date range, strategy weights) outside Python code for easy tuning.

</specifics>

<deferred>
## Deferred Ideas

None — all ideas fit within Phase 09 scope (backtest infrastructure).

</deferred>

---

*Phase: 09-composite-strategy-backtest*
*Context gathered: 2026-06-06*
