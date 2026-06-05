# Phase 08: Establish Composite Strategy Signal Layer - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase establishes a composite strategy signal layer that consumes existing canonical trend strategy outputs and produces a unified trading-research signal contract for downstream planning, backtests, reports, watchlist analysis, and later execution adapters.

The phase is about the **signal contract and composition layer**, not a broad rewrite of trend analyzers or market data loaders. Existing trend adapters remain the source of trend evidence:

- `EnhancedSuperTrendStrategy`
- `MTESv2TrendStrategy`
- `MTESv3TrendStrategy`
- Shared `TrendResult` / `TrendStrategyBase`

The first planning target should define and implement the minimal stable public contract for composite signals, then wire it to existing trend adapters with deterministic tests.

</domain>

<decisions>
## Implementation Decisions

### Signal Contract

- **D-01: Direction semantics** — `TradingSignal.direction` uses `BULL / BEAR / NEUTRAL`.
  - Do **not** make `LONG / SHORT / WAIT` or `BUY / SELL / HOLD` the primary direction field in this phase.
  - Execution-specific actions can be derived later by signal execution / backtest adapters from `direction + readiness`.

- **D-02: Separate technical validity from trade readiness** — `TradingSignal` should preserve two status layers:
  - `status`: technical validity / consumability, aligned with existing `TrendResult.status` semantics such as `VALID / NO_SIGNAL / FILTERED / INVALID`.
  - `readiness`: execution readiness, recommended values `READY / WAIT / BLOCKED / EXHAUSTED / UNKNOWN`.
  - Rationale: this keeps “invalid data or failed strategy” separate from “valid signal but not ready to trade.”

- **D-03: Core scoring contract** — use a minimal stable score contract:
  - `signal_score: float` in `-100 ~ +100`, carrying signed directional strength.
  - `confidence: float` in `0.0 ~ 1.0`.
  - `components: dict[str, float]` for strategy contributions such as `mtes_v3`, `mtes_v2`, `enhanced_supertrend`, or future `confluence`.
  - Do not require a top-level `confluence_score` in v0.1; it can live in `components` or `metadata` until the composition algorithm is locked.

- **D-04: Standard explainability fields** — `TradingSignal` should include enough structure for reports, tests, and MCP/tool output:
  - `reasons: list[str]`
  - `warnings: list[str]`
  - `components: dict[str, float]`
  - `source_results: dict[str, Any]` or equivalent serializable source summary
  - `metadata: dict[str, Any]`
  - Avoid storing heavy or non-serializable raw objects as required public fields.

### Claude's Discretion

The user delegated these choices to Claude:

- Whether to include both `status` and `readiness`: decision is yes, because existing `TrendResult` already distinguishes these concepts.
- How to organize score fields: decision is minimal top-level `signal_score + confidence`, with `components`/`metadata` for extension.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current phase source

- `.planning/ROADMAP.md` — Phase 08 is listed as `Establish Composite Strategy Signal Layer`, depends on Phase 7, and currently has no plan.
- `.planning/STATE.md` — records prior phases complete and notes Phase 8 as added roadmap evolution.

### Existing trend strategy contract

- `agent/src/strategies/trend/base.py` — canonical `TrendResult`, `TrendStrategyBase`, status/readiness semantics, confidence and signed-score ranges.
- `agent/src/strategies/trend/enhanced_supertrend.py` — existing trend adapter around Enhanced SuperTrend.
- `agent/src/strategies/trend/mtes_v2.py` — existing trend adapter around MTES v2.
- `agent/src/strategies/trend/mtes_v3.py` — existing trend adapter around MTES v3.

### Existing tests and examples

- `agent/tests/strategies/test_trend_base.py` — expected lifecycle and validation behavior for trend adapters.
- `agent/tests/strategies/test_enhanced_supertrend_strategy.py` — Enhanced SuperTrend adapter expectations.
- `agent/tests/strategies/test_mtes_v2_trend_strategy.py` — MTES v2 adapter expectations.
- `agent/tests/strategies/test_mtes_v3_trend_strategy.py` — MTES v3 adapter expectations.

### Codebase maps

- `.planning/codebase/STACK.md` — stack and dependency context.
- `.planning/codebase/INTEGRATIONS.md` — integration and data-provider context.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `TrendResult` in `agent/src/strategies/trend/base.py` already provides the closest upstream contract: `direction`, `confidence`, `signed_score`, `status`, `strength_rating`, `readiness`, `components`, `warnings`, and `metadata`.
- `TrendStrategyBase.analyze()` already normalizes validation failures and analyzer exceptions into canonical `TrendResult` objects.
- `EnhancedSuperTrendStrategy`, `MTESv2TrendStrategy`, and `MTESv3TrendStrategy` are ready to be used as source strategies for a composite signal layer.

### Established Patterns

- Existing trend strategies are adapter-style classes that normalize native analyzer output into canonical dataclasses.
- Existing tests prefer deterministic fake analyzers / fake indicators and focused pytest contract tests.
- Existing result objects expose `to_dict()` for machine-readable output; Phase 8 should follow that pattern for `TradingSignal`.

### Integration Points

- New composite signal code should likely live under `agent/src/strategies/` rather than `agent/src/analysis/`, because it composes existing strategies instead of implementing a new raw indicator/analyzer.
- Likely candidate paths for planning:
  - `agent/src/strategies/composite/`
  - `agent/src/strategies/composite/base.py`
  - `agent/src/strategies/composite/signal.py`
  - `agent/tests/strategies/test_composite_*.py`
- Downstream integration can later connect to backtest/watchlist/signal execution, but Phase 8 should first lock the Python contract and focused tests.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 8 as a research/trading signal layer, not a direct order-execution layer.
- Keep `BULL / BEAR / NEUTRAL` as the signal direction so it aligns with `TrendResult` and analysis reports.
- Use `readiness` to express whether a signal is ready for execution-style consumers.
- Keep the first public contract small enough to stabilize tests before adding more composite algorithms.

</specifics>

<deferred>
## Deferred Ideas

- `LONG / SHORT / WAIT`, `BUY / SELL / HOLD`, order sizing, stop-loss, and take-profit semantics belong to execution adapters or later signal execution phases, not the primary Phase 8 direction contract.
- Full composition algorithm choices such as weighted voting, gate-first, leader/follower, or confluence thresholds were not discussed yet. Planner/researcher may propose a minimal implementation, but if the choice is high-impact, ask before locking it.
- Broad MCP/tool/CLI exposure is not locked by this context. Start with the Python contract unless planning finds a simple existing integration point.

</deferred>

---

*Phase: 08-establish-composite-strategy-signal-layer*
*Context gathered: 2026-06-05*
