# Phase 01: Major Trend Evaluation System - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a cross-asset Major Trend Evaluation System (MTES) for Vibe-Trading. It scores stocks, ETFs, futures, crypto, and FX from 0–100 using six dimensions — direction, strength, structure, momentum, volatility/noise regime, and multi-timeframe alignment — then classifies the asset into one of seven trend states with explainable drivers and validation planning.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**9 requirements are locked.** See `01-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `01-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- MTES scoring specification with six explicit dimensions.
- Asset-class weight profiles for stocks, ETFs, futures, crypto, and FX.
- Trend-state labels and score thresholds.
- Watchlist-compatible output contract for human table and JSON consumers.
- Explainability contract: sub-scores, top drivers, regime flags, and concise explanation text.
- Backtest validation plan comparing MTES to single-indicator baselines.
- Tests or fixtures sufficient to verify scoring, classification, asset profile validation, and MTF look-ahead safety.

**Out of scope (from SPEC.md):**
- Live trading or order execution — this phase evaluates trend state only.
- Portfolio construction and position sizing beyond optional risk metadata — allocation belongs to a separate portfolio/risk phase.
- Optimizing indicator parameters for maximum return — this phase defines robust defaults and validation, not parameter mining.
- Adding new external data vendors — existing data loaders and local data are used.
- Fundamental analysis, news, macro, on-chain, funding, or sentiment integration — these may be later overlays but are excluded from the first MTES phase.
- Visual chart rendering — markdown/JSON reports are in scope; chart UI is separate.
- Replacing existing Trend/Pullback/Entry strategies — MTES complements them as a higher-level evaluation layer.

</spec_lock>

<decisions>
## Implementation Decisions

### Weight Model
- **D-01:** Use Base+Override weight profiles: define one generic six-dimension base profile, then apply asset-class overrides for `stock`, `etf`, `futures`, `crypto`, and `fx`.
- **D-02:** Compute `trend_score` as a weighted sum plus limited penalties for extreme noise/regime problems, multi-timeframe conflicts, and insufficient data. Avoid pure hard-gating as the default composition method.
- **D-03:** Keep direction sign independent from `trend_score`. The score represents trend quality/strength from 0–100; direction is emitted separately as bull/bear/neutral and combined with score bands for the seven-state classification.
- **D-04:** Use a structure-first base profile: direction 15, strength 15, structure 25, momentum 15, volatility/noise regime 15, multi-timeframe alignment 15.

### Direction Definition
- **D-05:** Use MA+Slope+Return as the primary direction framework: price vs long average, intermediate average vs long average, long-average slope, and long-horizon return direction.
- **D-06:** Use asset-class-specific direction periods rather than one global 50/200 style period for every asset class.
- **D-07:** If long-horizon direction data is insufficient, return an insufficient-data/no-score result instead of reallocating direction weights or using shorter proxies.
- **D-08:** Use fixed initial state thresholds across assets. Direction determines the bull/bear side; score bands determine early/confirmed/strong.

### Signal Families
- **D-09:** Structure dimension should combine breakout/range state with swing structure, e.g. Donchian-style breakout or range position plus higher-high/higher-low or lower-low/lower-high logic.
- **D-10:** Momentum dimension should combine absolute 3/6/12-month returns with relative strength ranking when watchlist/cross-sectional context is available. Single-asset analysis must still work from absolute momentum alone.
- **D-11:** Volatility/noise regime should primarily penalize low trend efficiency and high back-and-forth chop. Extreme ATR/HV conditions should be exposed as flags or secondary penalties, not the main regime definition.
- **D-12:** If non-core sub-indicators inside structure, momentum, or regime are unavailable, degrade the affected sub-score and mark metadata. Do not reallocate missing sub-indicator weight. Core OHLC or long-horizon direction insufficiency can still produce no score.

### Multi-Timeframe Alignment
- **D-13:** Use watchlist-specified timeframes as the primary source for base/higher timeframe choices instead of a single global default or hard-coded asset-class defaults.
- **D-14:** Use the existing `MTFAligner` completed-bar lag rule. No MTES implementation may use higher-timeframe values from an incomplete future bar.
- **D-15:** When base and higher timeframe directions conflict, strongly reduce the MTF sub-score and surface `timeframe_conflict` in `top_drivers`/metadata, but do not directly veto the total trend score.

### Integration Shape
- **D-16:** Build the core MTES evaluator as reusable logic, then expose two adapters: a backtest strategy wrapper as the preferred strategy-validation path, and a `WatchlistAnalyzer`/watchlist output adapter to satisfy the SPEC watchlist JSON/table contract.
- **D-17:** The backtest adapter must remain an evaluation strategy, not live execution or position-sizing logic.
- **D-18:** The watchlist local data health gate todo was reviewed but explicitly not folded into this phase. Do not implement it as part of MTES planning.

### Claude's Discretion
- Planner/researcher may choose exact class/module names, fixture layout, and internal dataclass schema, provided the output contract and decisions above are preserved.
- Planner/researcher may propose initial asset-class override values, but the base profile and structure-first emphasis are locked.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked GSD Scope
- `.planning/phases/01-major-trend-evaluation-system/01-SPEC.md` — Locked requirements, boundaries, constraints, acceptance criteria, ambiguity report, and interview log for this phase.
- `.planning/ROADMAP.md` — Current milestone and Phase 1 goal.
- `.planning/STATE.md` — Current focus and accumulated context.
- `.planning/REQUIREMENTS.md` — Existing project requirement record; note that REQ-001 watchlist data gate was reviewed but not folded into this phase.

### Existing Vibe-Trading Code
- `agent/src/analysis/watchlist_analyzer.py` — Existing watchlist batch analysis path and current EMA+ADX trend output shape.
- `agent/backtest/strategies/trend.py` — Existing trend strategy family: EMA+ADX, MACD, Dual EMA.
- `agent/backtest/strategies/mtf.py` — Existing MTF alignment with lagged completed-bar rule; MUST be respected for MTES MTF scoring.
- `agent/backtest/validation.py` — Existing statistical validation helpers for backtest outputs.

### Reviewed But Not Folded
- `.planning/todos/pending/watchlist-local-data-health-check.md` — Watchlist local data health gate; reviewed and intentionally deferred/not folded for this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WatchlistAnalyzer` in `agent/src/analysis/watchlist_analyzer.py`: existing batch entry point for watchlist analysis and natural place to add MTES watchlist adapter output.
- `AnalysisResult` in `agent/src/analysis/watchlist_analyzer.py`: current result dataclass can be extended or wrapped to include MTES fields such as `trend_score`, `trend_state`, `direction`, `regime`, `sub_scores`, and `top_drivers`.
- `TrendEmaAdxStrategy`, `TrendMacdStrategy`, and `TrendDualEmaStrategy` in `agent/backtest/strategies/trend.py`: reusable baselines and backtest comparison candidates.
- `MTFAligner` and `MTFComposer` in `agent/backtest/strategies/mtf.py`: reusable multi-timeframe alignment infrastructure with look-ahead prevention.
- `run_validation`, `monte_carlo_test`, `bootstrap_sharpe_ci`, and `walk_forward_analysis` in `agent/backtest/validation.py`: reusable validation tooling for the MTES backtest validation plan.

### Established Patterns
- Backtest strategies live under `agent/backtest/strategies/` and expose strategy classes with parameters, tags, supported markets, and signal-generation methods.
- Watchlist analysis currently reads local or client-loaded OHLCV data and returns per-symbol results through `AnalysisResult` objects.
- Multi-timeframe logic is centralized in `MTFAligner`; do not duplicate ad hoc MTF joins that could bypass lag safety.
- The project already supports multiple market families through loaders/engines; MTES should use explicit asset-class mapping rather than assuming one market convention.

### Integration Points
- Core evaluator: new reusable scoring logic should be importable by both the backtest strategy wrapper and watchlist adapter.
- Backtest integration: add a wrapper strategy in the existing strategy architecture rather than embedding scoring inside the runner.
- Watchlist integration: extend or wrap `WatchlistAnalyzer.analyze_single` / `analyze_all` output so JSON/table consumers receive MTES fields.
- Validation planning: compare MTES to existing single-indicator baselines from `trend.py` plus other simple baselines required by SPEC.

</code_context>

<specifics>
## Specific Ideas

- User specifically chose a structure-first scoring bias, so structure should have the highest base weight among the six dimensions.
- User prefers asset-specific direction periods over one fixed global direction horizon.
- User prefers strict handling of insufficient long-horizon direction data: no score rather than a fallback proxy.
- User prefers backtest strategy integration as the main validation path, while still requiring watchlist output compatibility through a second adapter.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `Implement watchlist local data health check` — reviewed because it matched watchlist/backtest keywords, but the user chose not to handle it in this MTES phase. Keep it as a separate data-readiness gate task.

</deferred>

---

*Phase: 01-major-trend-evaluation-system*
*Context gathered: 2026-05-28*
