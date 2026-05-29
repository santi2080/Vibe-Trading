# Phase 01: Major Trend Evaluation System - Research

**Researched:** 2026-05-29
**Domain:** Python quantitative trend scoring, watchlist analysis, and backtest validation
**Confidence:** MEDIUM-HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
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

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

### Reviewed Todos (not folded)
- `Implement watchlist local data health check` — reviewed because it matched watchlist/backtest keywords, but the user chose not to handle it in this MTES phase. Keep it as a separate data-readiness gate task.
</user_constraints>

## Summary

Phase 01 should be planned as a reuse-and-normalize phase, not a greenfield indicator library: the repository already has watchlist batch analysis, trend baselines, multi-timeframe alignment, strategy registration, comparison helpers, validation helpers, and an untracked draft MTES evaluator plus tests. [VERIFIED: codebase grep + git status] The planner should convert the draft into a spec-compliant, reviewable implementation by reconciling it with locked decisions, especially Base+Override weights, structure-first base profile, asset-class-specific direction periods, strict long-horizon insufficient-data handling, and a separate backtest strategy wrapper. [CITED: .planning/phases/01-major-trend-evaluation-system/01-CONTEXT.md]

The most important architectural boundary is: core scoring belongs in a reusable analysis module; backtest validation belongs in a strategy wrapper under the existing `BaseStrategy`/`StrategyRegistry` pattern; watchlist integration belongs in a thin adapter that augments `AnalysisResult`/JSON/table output without replacing existing trend/pullback/signal behavior. [VERIFIED: agent/backtest/strategies/__init__.py; agent/src/analysis/watchlist_analyzer.py] Multi-timeframe scoring must call `MTFAligner` rather than performing ad hoc joins, because `MTFAligner` centralizes the mandatory lag and backward merge behavior used to prevent look-ahead bias. [VERIFIED: agent/backtest/strategies/mtf.py]

**Primary recommendation:** Plan MTES in waves: first lock evaluator schema/config/tests, then fix/rewrite the draft core evaluator to satisfy locked scoring decisions, then add a registered backtest strategy wrapper, then update watchlist/report/tool adapters, then add the validation-plan artifact and robustness tests. [VERIFIED: codebase structure + CONTEXT decisions]

## Project Constraints (from CLAUDE.md)

- No project-root `CLAUDE.md` exists at `/Users/iagent/projects/vibe-trading/CLAUDE.md`; workspace-level `/Users/iagent/projects/CLAUDE.md` was loaded by the environment. [VERIFIED: Read /Users/iagent/projects/vibe-trading/CLAUDE.md; CITED: /Users/iagent/projects/CLAUDE.md]
- Python code should follow PEP 8, use type hints, include docstrings for functions/classes, use pytest, and target >80% test coverage. [CITED: /Users/iagent/projects/CLAUDE.md]
- Prefer 4-space indentation, line length 100 where practical, f-strings, and `pathlib` over `os.path`. [CITED: /Users/iagent/projects/CLAUDE.md]
- Use precise/surgical changes; avoid over-engineering and unrequested features. [CITED: /Users/iagent/projects/CLAUDE.md]
- Run tests before claiming completion. [CITED: /Users/iagent/projects/CLAUDE.md]
- Do not commit sensitive information; use `.env` for secrets. [CITED: /Users/iagent/projects/CLAUDE.md]

## Phase Requirements

| ID | Requirement | Research Support |
|----|-------------|------------------|
| MTES-01 | Six-dimension 0-100 MTES score with sub-scores summing to total. | Existing untracked evaluator already has six dimensions, but weights are not locked Base+Override and must be revised. [VERIFIED: agent/src/analysis/major_trend_evaluator.py; CITED: 01-SPEC.md] |
| MTES-02 | Seven trend states. | Draft has `TrendState` enum and threshold function covering the seven labels. [VERIFIED: agent/src/analysis/major_trend_evaluator.py] |
| MTES-03 | Asset-class profiles for stock/ETF/futures/crypto/FX totaling 100. | Draft has per-asset profiles totaling 100 but lacks the locked generic base profile + overrides shape. [VERIFIED: agent/src/analysis/major_trend_evaluator.py; CITED: 01-CONTEXT.md] |
| MTES-04 | Direction using long average, intermediate-vs-long, slope, and long return. | Draft implements these checks but only requires 50 bars before evaluating despite a 200-bar long window, contradicting strict long-horizon insufficiency. [VERIFIED: agent/src/analysis/major_trend_evaluator.py; CITED: 01-CONTEXT.md] |
| MTES-05 | Structure and momentum dimensions with insufficient-lookback metadata. | Draft includes Donchian/range-style structure and 63/126/252-bar momentum windows, but metadata should be strengthened for missing sub-indicators and cross-sectional relative strength. [VERIFIED: agent/src/analysis/major_trend_evaluator.py; CITED: 01-CONTEXT.md] |
| MTES-06 | Volatility/noise regime. | Draft uses volatility percentile plus trend efficiency and flags extreme/compressed/choppy regimes. [VERIFIED: agent/src/analysis/major_trend_evaluator.py] |
| MTES-07 | Look-ahead-safe MTF alignment. | Draft calls `MTFAligner(MTFConfig(lag_bars=1)).align_htf_to_ltf`; tests assert `backward_lag`, but conflict metadata/top-driver handling needs improvement. [VERIFIED: agent/src/analysis/major_trend_evaluator.py; agent/tests/test_major_trend_evaluator.py] |
| MTES-08 | Watchlist batch JSON/table output. | Draft extends `AnalysisResult.mtes`, `to_dict()`, `ReportGenerator` table columns, and watchlist tool summary output. [VERIFIED: agent/src/analysis/watchlist_analyzer.py; agent/src/analysis/report_generator.py; agent/src/tools/watchlist_tool.py] |
| MTES-09 | Backtest validation plan against baselines. | Draft `docs/MTES_BACKTEST_VALIDATION_PLAN.md` names universes, baselines, metrics, costs, perturbations, delays, and pass/fail checks; no backtest strategy wrapper exists yet. [VERIFIED: docs/MTES_BACKTEST_VALIDATION_PLAN.md; codebase search] |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Core MTES scoring | Analysis / Backend | Backtest strategy wrapper | Scoring is reusable domain logic consumed by both watchlist and backtest paths. [VERIFIED: agent/src/analysis layout; 01-CONTEXT.md D-16] |
| Asset-class config and weight validation | Analysis / Backend | Tests | The evaluator should own deterministic profiles and validation; tests should enforce totals and unsupported-class errors. [VERIFIED: agent/src/analysis/major_trend_evaluator.py; agent/tests/test_major_trend_evaluator.py] |
| MTF completed-bar alignment | Backtest strategy infrastructure | Analysis evaluator | `MTFAligner` already owns lag/backward-merge semantics; evaluator should call it rather than reimplement alignment. [VERIFIED: agent/backtest/strategies/mtf.py] |
| Watchlist output | Analysis adapter / CLI tools | Report generator | `WatchlistAnalyzer`, `ReportGenerator`, and `watchlist_tool.py` are current output surfaces. [VERIFIED: agent/src/analysis/watchlist_analyzer.py; agent/src/analysis/report_generator.py; agent/src/tools/watchlist_tool.py] |
| Strategy validation | Backtest strategy layer | Validation/comparison helpers | Existing `BaseStrategy`, `StrategyRegistry`, `StrategyComparator`, and `run_validation` are backtest integration points. [VERIFIED: agent/backtest/strategies/__init__.py; agent/backtest/strategies/comparison.py; agent/backtest/validation.py] |
| Data readiness gate | Out of scope | Separate pending todo | User explicitly deferred the watchlist local data health gate from this phase. [CITED: 01-CONTEXT.md D-18; .planning/todos/pending/watchlist-local-data-health-check.md] |

## Existing Assets

| Asset | What exists | How planner should use it |
|-------|-------------|---------------------------|
| `agent/src/analysis/watchlist_analyzer.py` | Existing batch watchlist flow with `AnalysisResult`, `analyze_single`, `analyze_all`, local parquet fallback, trend/pullback/signal fields, and uncommitted MTES payload injection. [VERIFIED: codebase] | Keep as the watchlist adapter surface; avoid embedding scoring decisions directly here. [VERIFIED: codebase] |
| `agent/src/analysis/major_trend_evaluator.py` | Untracked draft evaluator with dataclasses, six dimensions, asset profiles, classifier, OHLC normalization, ADX, structure, momentum, regime, and MTF scoring. [VERIFIED: git status + codebase] | Treat as draft to refactor, not final: it passes focused tests but conflicts with locked Base+Override and strict long-window decisions. [VERIFIED: pytest; CITED: 01-CONTEXT.md] |
| `agent/backtest/strategies/__init__.py` | `BaseStrategy` requires `_calculate()` and `_generate_signals()` and produces a DataFrame with `signal` and indicator columns. [VERIFIED: codebase] | Implement `MajorTrendEvaluationStrategy` or similarly named wrapper using this interface and register it. [VERIFIED: codebase; CITED: 01-CONTEXT.md D-16] |
| `agent/backtest/strategies/trend.py` | Existing trend baselines: EMA+ADX, MACD, Dual EMA. [VERIFIED: codebase] | Use as validation baselines and examples for strategy metadata, supported markets, tags, and signal generation. [VERIFIED: codebase] |
| `agent/backtest/strategies/mtf.py` | `MTFAligner` applies mandatory HTF lag, backward merge, and forward fill; `MTFConfig.lag_bars` defaults to 1. [VERIFIED: codebase] | Use directly for MTES MTF dimension and tests; do not create a custom merge. [VERIFIED: codebase] |
| `agent/backtest/validation.py` | Monte Carlo permutation, bootstrap Sharpe CI, walk-forward analysis, and `run_validation` exist. [VERIFIED: codebase] | Reference these in the validation plan and optionally call them in later validation execution. [VERIFIED: codebase] |
| `agent/backtest/strategies/comparison.py` | Strategy metrics/comparison tables and report generation exist. [VERIFIED: codebase] | Reuse for MTES-vs-baseline reporting rather than writing a new comparison formatter. [VERIFIED: codebase] |
| `agent/src/data/watchlist.py` | `WatchlistReader` parses watchlist CSV, raw items, timeframes, and trade config. [VERIFIED: codebase] | Use for watchlist-specified base/higher timeframe decisions. [VERIFIED: codebase; CITED: 01-CONTEXT.md D-13] |
| Strategy skills | EMA trend, ADX trend, Range Filter, and volatility skill docs define existing logic and defaults. [VERIFIED: agent/src/skills/*/SKILL.md] | Treat as local documentation/source for indicator family semantics, but keep MTES scoring in Python modules. [VERIFIED: codebase] |
| Draft validation plan | `docs/MTES_BACKTEST_VALIDATION_PLAN.md` already covers baselines, universes, splits, costs, metrics, perturbation, signal delay, and pass/fail guidance. [VERIFIED: codebase] | Move/keep as the required artifact, but ensure it is tied into phase deliverables and not treated as implementation validation completion. [VERIFIED: codebase] |

## Draft Implementation Status

### Files with MTES-relevant uncommitted changes

| File | Status | Planner treatment |
|------|--------|-------------------|
| `agent/src/analysis/major_trend_evaluator.py` | Untracked draft. [VERIFIED: git status] | Review and refactor into spec-compliant core evaluator; do not assume it satisfies locked decisions. [VERIFIED: code review] |
| `agent/tests/test_major_trend_evaluator.py` | Untracked focused tests; 11 tests pass. [VERIFIED: pytest `agent/tests/test_major_trend_evaluator.py -q`] | Keep as seed tests, then add stricter cases for base+override, long-window insufficiency, cross-sectional momentum, and timeframe conflict metadata. [VERIFIED: test review] |
| `agent/src/analysis/watchlist_analyzer.py` | Modified to inject MTES payload into `AnalysisResult`. [VERIFIED: git diff] | Convert to thin adapter and pass watchlist timeframes/higher timeframe data when available. [VERIFIED: code review] |
| `agent/src/analysis/report_generator.py` | Modified table includes MTES score/state columns. [VERIFIED: codebase] | Keep table integration; verify no emoji-only semantics in machine output. [VERIFIED: code review] |
| `agent/src/tools/watchlist_tool.py` | Untracked tool adapter returns `mtes` array in summary JSON. [VERIFIED: codebase] | Keep or integrate if tool registration is in scope; tests already cover registry output. [VERIFIED: pytest focused suite] |
| `docs/MTES_BACKTEST_VALIDATION_PLAN.md` | Untracked validation plan. [VERIFIED: git status] | Use as starting artifact for SPEC requirement 9; consider relocating only if project convention demands. [VERIFIED: codebase] |
| `agent/src/data/watchlist_data_health.py`, `scripts/check_watchlist_data.py`, `agent/tests/test_watchlist_data_health.py` | Untracked deferred data health gate implementation. [VERIFIED: git status] | Explicitly exclude from MTES implementation tasks unless user separately decides to include it. [CITED: 01-CONTEXT.md D-18] |
| `agent/backtest/loaders/client.py`, `agent/backtest/loaders/registry.py` | Modified loader imports/registry behavior. [VERIFIED: git status + codebase] | Treat as unrelated working-tree changes unless a task directly needs loader import fixes. [VERIFIED: git diff] |

### Test status observed during research

- `agent/tests/test_major_trend_evaluator.py -q` passed: 11 passed. [VERIFIED: pytest]
- `agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q` passed: 17 passed. [VERIFIED: pytest]
- Focused affected suite `agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py agent/tests/test_watchlist_data_health.py agent/tests/test_mcp_regression.py -q` passed: 35 passed. [VERIFIED: pytest]
- Full `agent/tests -q` fails during collection in `agent/tests/backtest/loaders/cache/test_cache.py` due to mixed `agent.backtest.*` and `backtest.*` imports causing a circular import around `yfinance_loader._to_yfinance_interval`. [VERIFIED: pytest; agent/backtest/loaders/registry.py; agent/backtest/loaders/yfinance_loader.py]
- The full-suite failure appears pre-existing or caused by unrelated uncommitted loader import changes, not by the MTES-focused tests themselves; planner should record it as an environment/working-tree blocker if phase gate requires full suite green. [VERIFIED: git diff + pytest]

## Recommended Architecture

### Target project structure

```text
agent/src/analysis/
├── major_trend_evaluator.py      # Core evaluator, config, result schema, scoring helpers
├── watchlist_analyzer.py         # Existing watchlist adapter; calls evaluator, no scoring internals
└── report_generator.py           # Human table/report output

agent/backtest/strategies/
├── major_trend.py                # New MTES evaluation strategy wrapper
├── registry.py / __init__.py     # Register/export strategy wrapper
├── trend.py                      # Existing baselines
├── mtf.py                        # Existing no-look-ahead aligner
└── comparison.py                 # Existing comparison reports

agent/tests/
├── test_major_trend_evaluator.py # Core + watchlist contract seed tests
└── backtest/... or test_mtes_strategy.py # Strategy wrapper and MTF tests

docs/
└── MTES_BACKTEST_VALIDATION_PLAN.md # Required validation-plan artifact
```

All paths above match existing package organization or untracked draft files. [VERIFIED: codebase]

### Core evaluator contract

Use a pure, deterministic evaluator API like this shape: [VERIFIED: current draft schema; CITED: 01-SPEC.md]

```python
result = MajorTrendEvaluator(config).evaluate(
    df,
    asset_class="futures",
    higher_timeframe=higher_df,
    base_timeframe="1d",
    higher_timeframe_name="1w",
    cross_section_context=None,
)
```

Planner should require the result object/dict to include `asset_class`, `trend_score`, `trend_state`, `direction`, `confidence`, `regime`, `sub_scores`, `raw_scores`, `weights`, `top_drivers`, `regime_flags`, `explanation`, and `metadata`. [VERIFIED: current draft; CITED: 01-SPEC.md]

### Scoring composition

- Implement weight profiles as `BASE_WEIGHTS = {direction: 15, strength: 15, structure: 25, momentum: 15, volatility_regime: 15, mtf: 15}` plus asset-class override deltas or full override maps derived from the base. [CITED: 01-CONTEXT.md D-01, D-04]
- Validate every final profile has exactly the six locked dimensions and totals 100. [CITED: 01-SPEC.md]
- Keep `trend_score` as a 0-100 quality/strength number and emit `direction` independently as `BULL`, `BEAR`, or `NEUTRAL`. [CITED: 01-CONTEXT.md D-03]
- Avoid hard-vetoing by MTF conflicts; reduce MTF sub-score and add `timeframe_conflict` to metadata/top drivers. [CITED: 01-CONTEXT.md D-15]
- Do not reallocate missing non-core sub-indicator weights; mark degraded metadata. [CITED: 01-CONTEXT.md D-12]
- For core OHLC or long-horizon direction insufficiency, return no-score/insufficient status instead of using short proxies. [CITED: 01-CONTEXT.md D-07]

### Dimension implementation guidance

| Dimension | Plan the implementation around | Existing support |
|-----------|--------------------------------|------------------|
| Direction | Price vs long average, intermediate vs long average, long average slope, long-horizon return, asset-class-specific periods. [CITED: 01-CONTEXT.md D-05, D-06] | Draft implements checks but needs strict required bars and per-asset periods. [VERIFIED: major_trend_evaluator.py] |
| Strength | ADX plus DI agreement with direction. [VERIFIED: adx skill + trend.py] | Draft has local `calculate_adx`; `TrendEmaAdxStrategy` has another ADX implementation. [VERIFIED: codebase] |
| Structure | Donchian/range position plus swing higher-high/higher-low or lower-low/lower-high logic. [CITED: 01-CONTEXT.md D-09] | Draft has prior high/low and half-window swing checks. [VERIFIED: major_trend_evaluator.py] |
| Momentum | Absolute 3/6/12-month returns and relative strength when watchlist context is available. [CITED: 01-CONTEXT.md D-10] | Draft only implements absolute 63/126/252-bar returns. [VERIFIED: major_trend_evaluator.py] |
| Volatility/noise regime | Prioritize trend efficiency/chop penalties, with extreme ATR/HV as flags/secondary penalties. [CITED: 01-CONTEXT.md D-11] | Draft uses HV percentile and efficiency flags. [VERIFIED: major_trend_evaluator.py] |
| MTF alignment | Use watchlist-specified timeframes and `MTFAligner` completed-bar lag. [CITED: 01-CONTEXT.md D-13, D-14] | Draft calls `MTFAligner`; watchlist currently does not load/pass secondary/higher timeframe data to evaluator. [VERIFIED: major_trend_evaluator.py; watchlist_analyzer.py] |

### Backtest strategy wrapper

Create a wrapper under `agent/backtest/strategies/` rather than embedding MTES in runners. [CITED: 01-CONTEXT.md D-16, D-17] The wrapper should subclass `BaseStrategy`, expose metadata/tags/supported markets, call `MajorTrendEvaluator`, and generate directional evaluation signals such as `1` for confirmed/strong bull, `-1` for confirmed/strong bear, `0` otherwise. [VERIFIED: BaseStrategy API; CITED: docs/MTES_BACKTEST_VALIDATION_PLAN.md]

Do not add live execution, order sizing, or portfolio allocation logic to the wrapper. [CITED: 01-SPEC.md out-of-scope; 01-CONTEXT.md D-17]

### Watchlist adapter

Keep `WatchlistAnalyzer` responsible for loading per-symbol data and formatting existing analysis output; inject MTES by calling the evaluator and merging `result.to_dict()` into `AnalysisResult.to_dict()`. [VERIFIED: current draft in watchlist_analyzer.py] Planner should add tasks to pass watchlist timeframes and, if local higher timeframe data exists, pass it into the evaluator so D-13 is satisfied. [VERIFIED: WatchlistReader.get_timeframes; CITED: 01-CONTEXT.md D-13]

## Validation Strategy

### Unit and contract validation

- Core score tests: assert six sub-scores exist, all are numeric, sum equals `trend_score`, and score is within `[0, 100]`. [CITED: 01-SPEC.md; VERIFIED: current test pattern]
- Profile tests: assert `stock`, `etf`, `futures`, `crypto`, and `fx` profiles total 100 and unsupported classes raise a clear `ValueError`. [CITED: 01-SPEC.md; VERIFIED: current tests]
- Classification tests: deterministic fixtures should cover all seven states, not just thresholds. Current tests cover thresholds and strong/choppy fixtures but not every fixture class explicitly. [VERIFIED: agent/tests/test_major_trend_evaluator.py]
- Direction insufficiency tests: add a test where length is between intermediate and long-window requirements; expected result should be insufficient/no-score. Current draft fails this locked design because it permits evaluation with only `intermediate_window` bars. [VERIFIED: major_trend_evaluator.py; CITED: 01-CONTEXT.md D-07]
- Missing component tests: missing `volume` must not crash; missing non-core sub-indicators should mark metadata and not reallocate. [CITED: 01-SPEC.md; VERIFIED: current missing-volume test]
- MTF safety tests: use synthetic base/higher frames to assert `MTFAligner` method is `backward_lag` and no lower-timeframe decision uses an incomplete future HTF value. [VERIFIED: mtf.py; current test]
- Watchlist JSON contract test: assert every analyzed result includes `symbol`, `asset_class`, `trend_score`, `trend_state`, `direction`, `confidence`, `regime`, `sub_scores`, and `top_drivers`. [CITED: 01-SPEC.md; VERIFIED: current test]

### Backtest validation plan

The validation-plan artifact should include at least these baselines: SMA 200 direction, Dual EMA 50/200, EMA+ADX, Donchian breakout, Range Filter direction, 12-month momentum, and MACD. [VERIFIED: docs/MTES_BACKTEST_VALIDATION_PLAN.md] It should include at least these metrics: annualized/CAGR return, max drawdown, Sharpe, Calmar, turnover, whipsaw/false-signal rate, win rate, exposure, signal-delay robustness, and cross-asset hit rate. [VERIFIED: docs/MTES_BACKTEST_VALIDATION_PLAN.md]

Use the existing `run_validation`, `monte_carlo_test`, `bootstrap_sharpe_ci`, and `walk_forward_analysis` helpers for future execution tasks rather than reimplementing statistical validation. [VERIFIED: agent/backtest/validation.py]

### Parameter discipline

This phase should use robust defaults and perturbation checks, not parameter mining. [CITED: 01-SPEC.md out-of-scope] The draft validation plan already defines ±20% window perturbations and +1/+2/+5-bar delay tests. [VERIFIED: docs/MTES_BACKTEST_VALIDATION_PLAN.md]

## Risks/Pitfalls

| Risk | What goes wrong | Prevention in plan |
|------|-----------------|--------------------|
| Draft accepted as final | Current draft conflicts with locked Base+Override and structure-first base profile. [VERIFIED: major_trend_evaluator.py; CITED: 01-CONTEXT.md D-01/D-04] | Add explicit refactor tasks before integration tasks. |
| Long-window lookback leakage by proxy | Evaluator uses long-window EMA/return without requiring enough long-horizon bars. [VERIFIED: major_trend_evaluator.py] | Add Wave 0/1 test for strict long-horizon insufficiency. |
| MTF look-ahead | A custom merge or unlagged HTF field leaks future completed values. [VERIFIED: mtf.py documents prevention mechanism] | Require all MTF scoring to call `MTFAligner` and include negative-control tests. |
| Hard indicator AND stack | Too many lagging confirmations delay signals and contradict weighted-scoring decision. [CITED: 01-SPEC.md constraints; 01-CONTEXT.md D-02] | Keep weighted composition; MTF conflict is a penalty/driver, not a veto. |
| Watchlist adapter becomes core logic | Scoring becomes duplicated in `WatchlistAnalyzer`. [VERIFIED: watchlist_analyzer.py current adapter surface] | Keep `WatchlistAnalyzer` as a caller only. |
| Relative strength scope creep | Cross-sectional momentum can require a watchlist context, but single-asset analysis must still work. [CITED: 01-CONTEXT.md D-10] | Plan optional `cross_section_context` input and metadata fallback. |
| Deferred health gate contamination | Existing untracked data-health implementation is related to watchlists but explicitly out of scope. [VERIFIED: git status; CITED: 01-CONTEXT.md D-18] | Exclude from MTES tasks unless user separately reopens it. |
| Full suite blocked by unrelated import issue | `agent/tests -q` currently fails collection in cache tests due to loader import circularity. [VERIFIED: pytest] | Use focused tests for MTES progress, but treat full-suite fix as a separate blocker if required for phase gate. |
| Emoji/human formatting in machine output | Reports use emojis in tables and console output. [VERIFIED: report_generator.py; watchlist_analyzer.py] | Ensure JSON output remains plain machine-readable fields. |

## Planning Implications

1. **Wave 0 should stabilize tests and decisions before code movement.** Include tasks to codify locked weights, required bars, state thresholds, and MTF safety fixtures before changing adapters. [CITED: 01-CONTEXT.md; VERIFIED: current tests]
2. **Wave 1 should refactor the core evaluator.** Replace draft per-asset full profiles with Base+Override, add asset-specific direction period config, strict long-horizon insufficiency, metadata for degraded components, and conflict drivers. [VERIFIED: major_trend_evaluator.py; CITED: 01-CONTEXT.md]
3. **Wave 2 should add the backtest wrapper.** Implement/export/register a strategy wrapper using `BaseStrategy`; generate signals from MTES states and preserve the evaluation-only boundary. [VERIFIED: BaseStrategy API; CITED: 01-CONTEXT.md D-16/D-17]
4. **Wave 3 should update watchlist/report/tool output.** Keep current draft adapter changes but pass timeframes/higher timeframe data where feasible and assert JSON contract. [VERIFIED: watchlist_analyzer.py; watchlist_tool.py]
5. **Wave 4 should finalize validation artifacts.** Use existing draft validation plan, ensure it names required baselines/metrics/universes/robustness checks, and link it from phase output if needed. [VERIFIED: docs/MTES_BACKTEST_VALIDATION_PLAN.md]
6. **Wave 5 should run focused and then gate tests.** Focused MTES tests pass today, while full suite has a loader collection error that planner should isolate as non-MTES or schedule as prerequisite if `/gsd:verify-work` requires full green. [VERIFIED: pytest]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in project `.venv`; pyproject declares `pytest>=7.0`. [VERIFIED: `.venv/bin/python -m pytest --version`; pyproject.toml] |
| Config file | `/Users/iagent/projects/vibe-trading/pyproject.toml` with `testpaths = ["agent/tests"]` and `pythonpath = ["agent"]`. [VERIFIED: pyproject.toml] |
| Quick run command | `cd /Users/iagent/projects/vibe-trading && .venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q` [VERIFIED: pytest] |
| Focused integration command | `cd /Users/iagent/projects/vibe-trading && .venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q` [VERIFIED: pytest] |
| Affected suite command | `cd /Users/iagent/projects/vibe-trading && .venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py agent/tests/test_watchlist_data_health.py agent/tests/test_mcp_regression.py -q` [VERIFIED: pytest] |
| Full suite command | `cd /Users/iagent/projects/vibe-trading && .venv/bin/python -m pytest agent/tests -q` currently fails collection in loader cache tests. [VERIFIED: pytest] |

### Requirement-to-test map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| MTES-01 | Six sub-scores sum to `trend_score`. | unit | `pytest agent/tests/test_major_trend_evaluator.py::test_strong_bull_fixture_scores_and_classifies -q` | ✅ [VERIFIED: codebase] |
| MTES-02 | Seven state labels and thresholds. | unit | `pytest agent/tests/test_major_trend_evaluator.py::test_classification_thresholds_cover_seven_states -q` | ✅ [VERIFIED: codebase] |
| MTES-03 | Asset profile totals and unsupported class error. | unit | `pytest agent/tests/test_major_trend_evaluator.py::test_asset_profiles_total_100 agent/tests/test_major_trend_evaluator.py::test_unsupported_asset_class_fails_clearly -q` | ✅ [VERIFIED: codebase] |
| MTES-04 | Direction long-horizon strict insufficiency. | unit | Add new test, e.g. `test_long_horizon_direction_requires_long_window`. | ❌ Wave 0 [VERIFIED: code review] |
| MTES-05 | Structure/momentum metadata and missing lookbacks. | unit | Add/extend `test_momentum_insufficient_windows_mark_metadata`. | ❌ Wave 0 [VERIFIED: code review] |
| MTES-06 | Choppy and extreme volatility regime flags. | unit | Existing choppy test plus add extreme-vol fixture. | ⚠️ partial [VERIFIED: codebase] |
| MTES-07 | MTF completed-bar safety and conflict driver. | unit/integration | Existing `test_mtf_alignment_uses_completed_higher_timeframe_bars`; add conflict metadata test. | ⚠️ partial [VERIFIED: codebase] |
| MTES-08 | Watchlist JSON/table MTES fields. | integration | `pytest agent/tests/test_major_trend_evaluator.py::test_watchlist_analyzer_includes_mtes_fields agent/tests/test_major_trend_evaluator.py::test_watchlist_tool_summary_includes_machine_readable_mtes -q` | ✅ [VERIFIED: codebase] |
| MTES-09 | Validation plan names baselines/metrics/robustness. | artifact test/manual | Add a doc contract test or manual checklist against `docs/MTES_BACKTEST_VALIDATION_PLAN.md`. | ⚠️ artifact exists, no test [VERIFIED: codebase] |

### Sampling Rate

- **Per task commit:** run the quick MTES test command for core changes or focused integration command for adapter changes. [VERIFIED: pytest]
- **Per wave merge:** run the affected suite command. [VERIFIED: pytest]
- **Phase gate:** run full `agent/tests -q` after resolving or explicitly waiving the unrelated loader circular import collection failure. [VERIFIED: pytest]

### Wave 0 Gaps

- [ ] Add tests for Base+Override weights and structure-first base profile. [CITED: 01-CONTEXT.md D-01/D-04]
- [ ] Add strict long-horizon insufficiency test. [CITED: 01-CONTEXT.md D-07]
- [ ] Add asset-class-specific direction-period test. [CITED: 01-CONTEXT.md D-06]
- [ ] Add MTF conflict metadata/top-driver test. [CITED: 01-CONTEXT.md D-15]
- [ ] Add cross-sectional momentum-context fallback test. [CITED: 01-CONTEXT.md D-10]
- [ ] Add backtest wrapper registration/generate-output test. [VERIFIED: BaseStrategy API]
- [ ] Add validation-plan artifact checklist test or explicit manual acceptance step. [CITED: 01-SPEC.md]
- [ ] Decide whether full-suite loader import circularity is in or out of this phase gate. [VERIFIED: pytest]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Tests and implementation | ✓ | system Python 3.14.4; project requires >=3.11. [VERIFIED: command + pyproject.toml] | Use `.venv/bin/python`. |
| pytest | Validation | ✓ | 9.0.3 in `.venv`. [VERIFIED: command] | none needed |
| pandas | OHLCV calculations | ✓ | 3.0.3 in `.venv`. [VERIFIED: command] | Project dependency `pandas>=2.0.0`. [VERIFIED: pyproject.toml] |
| numpy | Indicator calculations | ✓ | 2.4.6 in `.venv`. [VERIFIED: command] | Project dependency `numpy>=1.24.0`. [VERIFIED: pyproject.toml] |
| Git | Working-tree/draft detection | ✓ | 2.49.0. [VERIFIED: command] | none |
| graphify knowledge graph | Graph context | ✗ | disabled. [VERIFIED: gsd-tools graphify status] | Continue with codebase grep/read. |
| External packages to install | None for MTES | n/a | n/a | Use existing pandas/numpy/project modules. [VERIFIED: pyproject.toml; codebase] |

**Missing dependencies with no fallback:** none for focused MTES implementation. [VERIFIED: environment audit]

**Missing dependencies with fallback:** graphify disabled; research used direct code reads and grep instead. [VERIFIED: gsd-tools graphify status]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Higher-to-lower timeframe joining | A custom `merge_asof`/forward-fill implementation | `MTFAligner.align_htf_to_ltf()` | It already applies mandatory lag, backward merge, warmup, and validation metadata. [VERIFIED: agent/backtest/strategies/mtf.py] |
| Strategy registry mechanics | A separate MTES runner registry | Existing `BaseStrategy`/`StrategyRegistry` | Existing strategies are discoverable and comparable through project conventions. [VERIFIED: agent/backtest/strategies/__init__.py; registry.py] |
| Strategy comparison report | New markdown/table formatter for baseline comparison | `StrategyComparator` / `generate_standard_report` | Existing comparison helpers cover metrics tables and recommendations. [VERIFIED: agent/backtest/strategies/comparison.py] |
| Statistical validation helpers | New Monte Carlo/bootstrap/walk-forward code | `agent/backtest/validation.py` | Existing functions cover required validation families. [VERIFIED: agent/backtest/validation.py] |
| Watchlist CSV parser | New CSV parser | `WatchlistReader` | Existing parser handles raw rows and timeframe extraction. [VERIFIED: agent/src/data/watchlist.py] |
| Data health gate | Fold health checks into MTES | Separate deferred todo | User explicitly kept it out of this phase. [CITED: 01-CONTEXT.md D-18] |

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | MTES is local analysis/backtest logic and does not add auth. [VERIFIED: phase scope] |
| V3 Session Management | no | MTES does not introduce sessions. [VERIFIED: phase scope] |
| V4 Access Control | low | Watchlist tool path handling should keep existing watchlist-directory escape protection. [VERIFIED: agent/src/tools/watchlist_tool.py] |
| V5 Input Validation | yes | Validate OHLC columns, asset class, weights, and timeframe strings before scoring. [VERIFIED: major_trend_evaluator.py; watchlist.py] |
| V6 Cryptography | no | No crypto primitives are introduced. [VERIFIED: phase scope] |

Known threat pattern: path traversal in watchlist tools is mitigated by `_resolve_watchlist_path()` requiring resolved paths to remain under the watchlist directory. [VERIFIED: agent/src/tools/watchlist_tool.py]

## Sources

### Primary (HIGH confidence)

- `/Users/iagent/projects/vibe-trading/.planning/phases/01-major-trend-evaluation-system/01-SPEC.md` — locked requirements, boundaries, acceptance criteria. [CITED]
- `/Users/iagent/projects/vibe-trading/.planning/phases/01-major-trend-evaluation-system/01-CONTEXT.md` — locked implementation decisions and deferred scope. [CITED]
- `/Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py` — untracked draft evaluator. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/src/analysis/watchlist_analyzer.py` — watchlist adapter and current draft MTES injection. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/backtest/strategies/mtf.py` — MTF lag/backward alignment implementation. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/backtest/strategies/__init__.py` — strategy base and registry API. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py` — trend baseline strategies. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/backtest/validation.py` — statistical validation helpers. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py` — draft MTES tests. [VERIFIED]
- pytest runs listed in Draft Implementation Status. [VERIFIED]

### Secondary (MEDIUM confidence)

- `/Users/iagent/projects/vibe-trading/agent/src/skills/trend/ema_trend/SKILL.md` — EMA trend semantics. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/src/skills/trend/adx_trend/SKILL.md` — ADX semantics. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/src/skills/entry/range_filter/SKILL.md` — Range Filter semantics. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/src/skills/volatility/SKILL.md` — HV percentile volatility semantics. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/docs/MTES_BACKTEST_VALIDATION_PLAN.md` — untracked draft validation artifact. [VERIFIED]

### Tertiary (LOW confidence)

- None. This research is codebase-only; no web/package discovery was needed. [VERIFIED: research method]

## Metadata

**Confidence breakdown:**
- Existing assets: HIGH — verified by direct file reads, grep, git status, and focused pytest runs. [VERIFIED]
- Draft implementation status: HIGH — verified by git status, code reads, and test commands. [VERIFIED]
- Recommended architecture: MEDIUM-HIGH — based on existing project APIs and locked decisions; exact class/module names remain planner discretion. [VERIFIED + CITED]
- Validation architecture: MEDIUM — focused tests pass, but full suite currently fails due to a loader circular import collection issue outside MTES-focused tests. [VERIFIED]

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 for codebase structure; revisit sooner if the untracked draft is committed, reverted, or heavily modified. [ASSUMED]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Research remains valid until 2026-06-28 unless the draft changes. | Metadata | Planner may rely on stale draft status if working tree changes before planning. |
