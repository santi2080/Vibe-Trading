# Phase 03: SuperTrend Enhancement Strategy - Research

**Researched:** 2026-05-30 [VERIFIED: currentDate]
**Domain:** Python quantitative strategy research, multi-timeframe trend filtering, entry-signal backtesting [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md]
**Confidence:** HIGH for local-codebase findings; MEDIUM for strategy efficacy until out-of-sample backtests run [VERIFIED: local files] [ASSUMED]

## User Constraints

- Phase 03 is `SuperTrend Enhancement Strategy`. [VERIFIED: user prompt]
- Required output path requested by user: `/Users/iagent/projects/vibe-trading/.planning/phases/03-supertrend-enhancement-strategy/03-RESEARCH.md`. [VERIFIED: user prompt]
- Current execution environment is isolated in `/Users/iagent/projects/vibe-trading/.claude/worktrees/agent-aab9e180c2ae39817`; the tooling requires editing the worktree copy rather than the shared-checkout path. [VERIFIED: Write tool enforcement]
- Research must support implementation of a new “证券趋势 + 入场信号分析策略组合”. [VERIFIED: user prompt]
- Current background: Phase 02 proved SuperTrend/RangeFilter are strong trend indicators, but SuperTrend direction accuracy is around 50%, so Phase 03 must improve signal quality through combinations. [VERIFIED: user prompt]
- Must cover: standard SuperTrend algorithm differences; SuperTrend as higher-timeframe trend anchor; ADX/Choppiness/ATR percentile/RangeFilter/MTES/EMA pullback/breakout/RSI/MACD combinations; trading metrics; experiment matrix; risks; deliverables and acceptance criteria. [VERIFIED: user prompt]
- Network research, if used, must use `smart-search` / `extract-content`, not WebSearch. [VERIFIED: user prompt]

## Project Constraints (from CLAUDE.md)

- Python code must follow PEP 8, use type hints, include function/class docstrings, target >80% test coverage, use pytest, and use black formatting. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Git commits should use `<type>: <description>` with types such as `feat`, `fix`, `refactor`, `test`, and `docs`; each feature should use an independent branch; tests should run before commit. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Code review principles require surgical changes, no unrequested over-engineering, simple solutions first, and test-first workflow. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Code style preferences include 4-space indentation, 100-character line limit, f-strings over `format()`, and `pathlib` over `os.path`. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Workflow preferences require reading files before modification, running tests after modification, committing important changes, and keeping the working directory clean. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Security guidance forbids committing sensitive information and requires `.env` for configuration secrets. [VERIFIED: /Users/iagent/projects/CLAUDE.md]

## Summary

Phase 02 produced a useful cross-market indicator comparison tool, but its score is not a deployable trading-strategy score: Phase 02 explicitly notes it excludes transaction costs, position management, stop-loss/take-profit, portfolio constraints, and full return/risk metrics. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

Phase 03 should not try to rescue daily SuperTrend as a standalone directional predictor. It should use completed weekly SuperTrend as a higher-timeframe trend anchor, then use daily RangeFilter, regime filters, and entry triggers to decide whether and when to trade. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] This directly follows Phase 02: daily RangeFilter ranked #1 with 52.6% average direction accuracy and 21/25 best-symbol count, while weekly SuperTrend was best in 17/25 symbols despite RangeFilter having a slightly higher weekly average score. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

**Primary recommendation:** implement `Weekly SuperTrend anchor + Daily RangeFilter confirmation + regime filter + entry trigger family + MTES conflict veto/penalty`, and evaluate it with trade-level metrics plus regime split and walk-forward validation before declaring improvement. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] [ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Indicator calculation | Python research/backtest layer | Existing `agent/backtest` strategy layer | Phase 02 indicators currently live in `scripts/backtest_trend_indicators.py`; reusable strategy patterns live under `agent/backtest/strategies/`. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] |
| Multi-timeframe alignment | Python research/backtest layer | Existing MTES/MTF alignment utilities | Existing MTES uses `MTFAligner(MTFConfig(lag_bars=1))` for completed higher-timeframe bars. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |
| Strategy combinations | Python research scripts first | Later reusable strategy module | Phase 03 is a strategy-research/enhancement phase and should stabilize experiment logic before promoting to reusable strategy. [ASSUMED] |
| Trade-level metrics | Existing `backtest.metrics` | New Phase 03 diagnostics | Existing tests validate win rate, profit factor, Sharpe, Sortino, Calmar, max drawdown, trade count, and symbol/exit splits. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] |
| Reports | `reports/` output files | planning summary artifacts | Phase 02 generated CSV + Markdown reports under `reports/`; Phase 03 should follow this convention. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |
| Validation | pytest + fresh backtest commands | Manual report inspection | Project pytest config uses `agent/tests`, and Phase 02 verification used fresh CLI runs and CSV/report checks. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-VERIFICATION.md] |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| P03-R1 | Compare standard SuperTrend algorithm vs current implementation | `Standard SuperTrend Algorithm vs Current Implementation` section. [VERIFIED: user prompt] |
| P03-R2 | Upgrade SuperTrend from single indicator to higher-timeframe anchor | `Architecture Patterns` and `Experiment Matrix` sections. [VERIFIED: user prompt] |
| P03-R3 | Define quality-improving combinations | `Strategy Combination Stack` section. [VERIFIED: user prompt] |
| P03-R4 | Define trading-oriented metrics | `Trading Evaluation Metrics` section. [VERIFIED: user prompt] |
| P03-R5 | Recommend experiment matrix | `Experiment Matrix` section. [VERIFIED: user prompt] |
| P03-R6 | Document risks, deliverables, acceptance criteria | `Common Pitfalls` and `Phase 03 Recommended Deliverables and Acceptance Criteria`. [VERIFIED: user prompt] |

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Python | `>=3.11` project requirement; local `.venv` probed as Python 3.14.4 | Strategy research, indicator calculation, CLI scripts | Project declares Python `>=3.11`; local env has Python. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] [VERIFIED: environment probe] |
| pandas | `>=2.0.0` | OHLCV manipulation, resampling, alignment, report tables | Project dependency and current Phase 02 script use pandas. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] |
| numpy | `>=1.24.0` | Vectorized calculations and metrics | Project dependency and Phase 02 script use numpy. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] |
| pytest | `>=7.0` optional dev dependency | Unit/contract tests | Project pytest config points to `agent/tests`; existing MTES/metrics tests use pytest. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py] |
| Existing `backtest.metrics` | local module | Trade/equity metrics | Existing tests validate the required core metrics. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] |
| Existing MTF alignment via MTES evaluator | local module | Completed higher-timeframe alignment | Existing evaluator routes through `MTFAligner` with `lag_bars=1`. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| `scripts/backtest_trend_indicators.py` | Phase 02 indicator and report reference | Use as baseline and for extracting existing indicator semantics, but harden before Phase 03 trade scoring. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] |
| `agent/src/analysis/major_trend_evaluator.py` | MTES conflict flags, volatility regime scoring, ADX/ATR helpers, MTF alignment | Use for MTES conflict filtering and avoid duplicating MTF semantics. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |
| `agent/backtest/strategies/trend.py` | EMA+ADX and MACD strategy patterns | Use as style/reference for strategy classes and signal-generation conventions. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reusing local pandas/numpy formulas | Add `stock-indicators` package | `stock-indicators` docs are useful for semantics, but adding a new dependency requires package audit and may change warmup/convergence behavior; prefer local formulas + tests for Phase 03. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/] |
| Reusing `backtest.metrics` | Hand-roll metrics in new script | Existing metrics are already tested; hand-rolling creates inconsistency. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] |
| Weekly ST anchor | Daily ST anchor | Phase 02 evidence favors weekly ST as a stronger anchor and daily RangeFilter as better daily confirmation. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |

**Installation:** no new external package is recommended. [VERIFIED: current project dependencies]

## Package Legitimacy Audit

No external package installation is recommended for Phase 03. [VERIFIED: Standard Stack]

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| none | — | — | — | — | — | No external install needed |

**Packages removed due to slopcheck [SLOP] verdict:** none. [VERIFIED: no install recommended]
**Packages flagged as suspicious [SUS]:** none. [VERIFIED: no install recommended]

## Standard SuperTrend Algorithm vs Current Implementation

### Standard SuperTrend requirements

- SuperTrend uses ATR band thresholds to determine primary close-price trend and can indicate reversal/trailing stop behavior when trend changes. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/]
- Standard SuperTrend exposes a contiguous `super_trend` line plus separate `upper_band` and `lower_band` values to mark bearish and bullish segments. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/]
- Common parameters are ATR lookback `N` around 7-14 and multiplier around 2-3. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/]
- SuperTrend has warmup/convergence uncertainty: docs require at least `N+100` periods and recommend `N+250` prior periods for better precision. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/]

### Current implementation differences and Phase 03 corrections

| Area | Current implementation | Phase 03 correction |
|------|------------------------|---------------------|
| ATR smoothing | Current ST uses `tr.rolling(self.period).mean()`. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Lock ATR smoothing semantics and test them. Wilder-style smoothing is standard in ATR lineage, but final choice must be documented. [CITED: https://ta-lib.github.io/ta-doc/indicator/ATR.htm] [ASSUMED] |
| Final upper/lower bands | Current ST computes basic upper/lower bands but does not carry forward stateful final upper/lower bands. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Implement explicit `st_final_upper`, `st_final_lower`, `st_trend`, and `supertrend` columns. [ASSUMED] |
| Trend state transitions | Current direction flips from `close[i] > prev_st`, not prior final-band crossing. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Transition bullish/bearish only when price crosses the relevant completed prior/final band; test with fixtures. [ASSUMED] |
| Warmup handling | Phase 02 naturally ignores NaNs but does not explicitly remove ST convergence bars. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Drop/document at least `period + 100` warmup bars for ST metrics. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/] |
| No future function | Current scoring uses `future_returns` for evaluation labels, while indicators use current/past data. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Maintain strict separation: indicators/triggers use only current/past bars; future returns only labels/metrics. [VERIFIED: local implementation pattern] |
| Weekly/daily alignment | Existing MTES evaluator uses completed-bar lag, but Phase 02 script’s standalone MTES does direct weekly `ffill`. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Reuse `MTFAligner` or equivalent completed-week lag; never feed incomplete weekly ST into same-week daily decisions. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py] |

## Architecture Patterns

### System Architecture Diagram

```text
Local OHLCV parquet/csv
        |
        v
Data loader + column normalization
        |
        +-------------------------------+
        |                               |
        v                               v
Weekly indicator engine            Daily indicator engine
(SuperTrend final bands,           (RangeFilter, ADX, Chop,
 completed-week lag)                ATR percentile, EMA, RSI, MACD)
        |                               |
        v                               v
Higher-timeframe trend anchor       Regime + entry trigger features
        |                               |
        +---------------+---------------+
                        |
                        v
Decision layer
- allow only anchor-aligned trades
- reject/penalize MTES conflicts
- choose entry family: pullback / breakout / momentum recovery
                        |
                        v
Trade simulator
- entries/exits
- transaction cost/slippage assumptions
- holding-day and exposure accounting
                        |
                        v
Metrics + diagnostics
- win rate, PF, MDD, Sharpe/Sortino, CAGR/Calmar
- whipsaw count, regime split, symbol split, walk-forward split
                        |
                        v
CSV + Markdown research report
```

### Recommended Project Structure

```text
scripts/
├── backtest_supertrend_enhancement.py      # Phase 03 experiment runner CLI [ASSUMED]
agent/backtest/strategies/
├── supertrend_enhancement.py               # Optional reusable strategy after research stabilizes [ASSUMED]
agent/tests/
├── test_supertrend_calculation.py          # ST final-band and no-lookahead fixtures [ASSUMED]
├── test_supertrend_enhancement_strategy.py # Strategy decision and MTF alignment tests [ASSUMED]
├── test_supertrend_enhancement_metrics.py  # New diagnostics if not already in metrics [ASSUMED]
reports/
├── supertrend_enhancement_comparison_*.csv
└── supertrend_enhancement_report_*.md
```

### Pattern 1: SuperTrend as Higher-Timeframe Anchor

**What:** Compute SuperTrend on weekly bars, align only completed weekly states to daily bars, and allow daily entries only when the daily trigger direction agrees with weekly state. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md]

**When to use:** Use for all Phase 03 candidate strategies except baseline controls because Phase 02 showed SuperTrend is stronger as a weekly indicator than as daily standalone. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

**Implementation rule:** prefer existing `MTFAligner` completed-bar lag behavior over manual weekly-to-daily `ffill`. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py]

### Pattern 2: Separate Regime Filter from Entry Trigger

**What:** First classify whether the market is trend-following-friendly, then evaluate pullback/breakout/momentum entry triggers. [ASSUMED]

**When to use:** Use whenever a trend-following strategy can be damaged by sideways markets; Phase 02’s current noise score can over-reward low switching. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

**Regime candidates:** ADX trend strength, Choppiness Index, trend efficiency, ATR percentile, and MTES volatility regime. [CITED: https://python.stockindicators.dev/indicators/Adx/] [CITED: https://python.stockindicators.dev/indicators/Chop/] [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py]

### Pattern 3: Evaluate Strategy Families, Not Only Indicators

**What:** Every experiment should produce trade records and equity curves, not only direction labels. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

**When to use:** Use for every Phase 03 matrix row after baseline replication. [ASSUMED]

**Required outputs:** trade list, equity curve, metrics row, symbol split, regime split, whipsaw diagnostics, and parameter set. [ASSUMED]

### Anti-Patterns to Avoid

- **Using weekly values before week close:** direct weekly `ffill` into daily decisions can leak future weekly information; use completed-bar lag. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py]
- **Optimizing and reporting on the same full sample:** parameter grids need train/test or walk-forward splits. [ASSUMED]
- **Rewarding “never switch” indicators:** Phase 02 noise score rewards stability; trade metrics and whipsaw counts must counterbalance this. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]
- **Opaque combined score:** keep anchor, regime, trigger, confirmation, and conflict filters as separately reportable columns. [ASSUMED]

## Strategy Combination Stack

### Baselines

| Strategy | Logic | Purpose |
|----------|-------|---------|
| Buy-and-hold / always long | Long from first tradable bar to final bar | Market beta benchmark. [ASSUMED] |
| Daily SuperTrend standalone | Daily corrected ST as position/trade direction | Compare against Phase 02 daily ST weakness. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |
| Weekly SuperTrend anchor only | Daily position follows completed weekly ST | Test whether weekly ST improves trade metrics. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |
| Daily RangeFilter standalone | Daily RF direction as position | Compare against Phase 02 daily winner. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |

### Regime Filters

| Filter | Recommended rule | Rationale |
|--------|------------------|-----------|
| ADX | Trade only when ADX is above threshold and DI agrees with direction. [ASSUMED] | ADX is documented as a trend-strength measure with +DI/-DI components. [CITED: https://python.stockindicators.dev/indicators/Adx/] |
| Choppiness Index | Avoid trend entries when Chop is high; allow when Chop is low or falling. [ASSUMED] | Choppiness Index measures trendiness vs choppiness from 0-100. [CITED: https://python.stockindicators.dev/indicators/Chop/] |
| ATR percentile | Avoid extreme low volatility and extreme high volatility; test middle/high-normal percentile bands. [ASSUMED] | Existing MTES already flags `high_atr` and `extreme_volatility`. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |
| Trend efficiency | Prefer high net-move/path-ratio regimes. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] | Existing MTES uses trend efficiency as primary chop penalty. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |

### Confirmation Filters

| Filter | Recommended rule | Rationale |
|--------|------------------|-----------|
| Daily RangeFilter | Require daily RF direction to agree with completed weekly ST before entry. [ASSUMED] | RangeFilter ranked first on daily average and best in 21/25 symbols. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |
| MTES conflict filter | Reject or down-rank trades when MTES direction conflicts with weekly ST or daily trigger. [ASSUMED] | MTES exposes `timeframe_conflict` metadata and reduces MTF score on conflict. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py] |
| EMA context | Require close above key EMA for long and below key EMA for short, or fast EMA above/below slow EMA. [ASSUMED] | Existing `TrendEmaAdxStrategy` uses EMA fast/slow and ADX confirmation. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] |

### Entry Trigger Families

| Trigger | Long example | Short example | Why it belongs |
|---------|--------------|---------------|----------------|
| EMA pullback | Weekly ST bull + daily RF bull + price pulls near EMA20/EMA50 then closes above EMA20. [ASSUMED] | Weekly ST bear + daily RF bear + price rallies near EMA20/EMA50 then closes below EMA20. [ASSUMED] | Converts trend state into lower-risk timing. [ASSUMED] |
| Breakout | Weekly ST bull + close breaks prior N-day high / Donchian high. [ASSUMED] | Weekly ST bear + close breaks prior N-day low. [ASSUMED] | Existing MTES structure scoring uses prior high/low breakout state. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |
| RSI recovery | Weekly ST bull + RSI recovers from pullback zone. [ASSUMED] | Weekly ST bear + RSI rolls down from bounce zone. [ASSUMED] | RSI is a 0-100 oscillator and can identify momentum recovery after pullback. [CITED: https://ta-lib.github.io/ta-doc/indicator/RSI.htm] [ASSUMED] |
| MACD recovery | Weekly ST bull + MACD histogram crosses above 0 or MACD crosses above signal after pullback. [ASSUMED] | Weekly ST bear + MACD histogram crosses below 0 or MACD crosses below signal. [ASSUMED] | Existing `TrendMacdStrategy` uses MACD-signal crosses and zero-line context. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] |

## Trading Evaluation Metrics

Phase 03 must upgrade from Phase 02 indicator scores to trade-level metrics because Phase 02 was not a full trading-strategy backtest. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

| Metric | Guidance | Why Required |
|--------|----------|--------------|
| Win rate | Winning trades / total trades; existing `win_rate_and_stats` covers this. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Direction accuracy is not trade profitability. [ASSUMED] |
| Profit factor | Gross profit / gross loss; existing tests validate it. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Captures payoff quality beyond win rate. [ASSUMED] |
| Max drawdown | Worst equity peak-to-trough decline; existing tests validate negative drawdown. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Rejects fragile strategies. [ASSUMED] |
| Sharpe | Risk-adjusted return from equity curve; existing tests validate positive Sharpe on growth. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Compares return per volatility. [ASSUMED] |
| Sortino | Downside-risk-adjusted return; existing tests validate it. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Penalizes downside volatility. [ASSUMED] |
| CAGR / annual return | Annualized compounded return; use existing `annual_return` if exposed by `calc_metrics`. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Needed for capital-growth comparison and Calmar. [ASSUMED] |
| Calmar | Annual return / absolute max drawdown; existing tests validate behavior. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Trend systems often fail by drawdown. [ASSUMED] |
| Trade count | Number of trades; existing `calc_metrics` includes it. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Prevents over-pruned strategies. [ASSUMED] |
| Holding days/bars | Average and distribution; existing tests validate average holding bars. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Distinguishes swing strategy vs buy-and-hold. [ASSUMED] |
| Exposure | % bars with open position. [ASSUMED] | Measures capital efficiency and idle time. [ASSUMED] |
| Whipsaw count | Count trades exited quickly after adverse reversal or ST/RF flip within N bars. [ASSUMED] | Directly measures false trend-entry damage. [ASSUMED] |
| Regime split | Metrics grouped by ADX/Chop/ATR percentile/MTES regime. [ASSUMED] | Confirms whether filters help target regimes. [ASSUMED] |
| Symbol / market split | Metrics by symbol/market; existing metrics support symbol stats. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] | Prevents one asset class dominating averages. [ASSUMED] |

## Experiment Matrix

| Experiment ID | Name | Core Logic | Acceptance Signal |
|---------------|------|------------|-------------------|
| E0 | Phase 02 replication | Re-run current indicator scores for same sample. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] | Matches Phase 02 outputs within expected sample/timestamp differences. [ASSUMED] |
| E1 | Corrected daily ST baseline | Daily corrected final-band ST as position/trades. [ASSUMED] | Establishes corrected ST trade baseline. [ASSUMED] |
| E2 | Weekly ST anchor | Completed weekly ST direction gates daily exposure. [ASSUMED] | Improves drawdown/whipsaw vs daily ST without collapsing trade count. [ASSUMED] |
| E3 | SuperTrend + regime | Weekly ST + ADX/Chop/ATR percentile/trend-efficiency filter. [ASSUMED] | Better profit factor/drawdown than E2 in choppy regimes. [ASSUMED] |
| E4 | Weekly ST + Daily RF | Weekly ST anchor + daily RangeFilter confirmation. [ASSUMED] | Improves trade quality vs E2 and uses Phase 02 daily winner. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |
| E5 | Pullback entry | E4 + EMA pullback/recovery trigger. [ASSUMED] | Higher win rate or lower initial adverse excursion than E4. [ASSUMED] |
| E6 | Breakout entry | E4 + N-day Donchian breakout trigger. [ASSUMED] | Higher CAGR in trend-friendly regimes with tolerable whipsaws. [ASSUMED] |
| E7 | Momentum recovery | E4 + RSI/MACD recovery trigger. [ASSUMED] | Improves timing after pullbacks without excessive lag. [ASSUMED] |
| E8 | MTES conflict filter | Best of E5-E7 + reject/penalize MTES conflict. [ASSUMED] | Fewer losing trades/whipsaws when MTES conflicts with ST/RF. [ASSUMED] |
| E9 | Parameter grid | Grid ST period/multiplier, RF period/mult, ADX threshold, Chop threshold, breakout length, EMA periods. [ASSUMED] | Robust plateau, not single-parameter spike. [ASSUMED] |
| E10 | Walk-forward | Rolling train/test parameter selection by symbol/market. [ASSUMED] | Out-of-sample metrics remain positive and not materially worse than in-sample. [ASSUMED] |

### Suggested Parameter Ranges

| Parameter | Range | Notes |
|-----------|-------|-------|
| ST period | 7, 10, 14 | Docs say typical ATR lookback is 7-14. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/] |
| ST multiplier | 2.0, 2.5, 3.0, 3.5 | Docs say multiplier is usually around 2-3; 3.5 is sensitivity boundary. [CITED: https://python.stockindicators.dev/indicators/SuperTrend/] [ASSUMED] |
| RF period | 10, 20, 40 | Current Phase 02 uses 20. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] |
| RF multiplier | 1.5, 2.0, 2.5 | Current Phase 02 uses 2.0. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] |
| ADX threshold | 20, 25, 30 | Existing strategy default is 25; Phase 02 sets ADX signal to 0 below 20. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py] |
| Chop threshold | fixed bands or quantiles | Quantiles reduce cross-asset scale fragility. [CITED: https://python.stockindicators.dev/indicators/Chop/] [ASSUMED] |
| Breakout length | 20, 55 | Existing MTES defaults include swing window 20 and structure window 55. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |
| EMA pullback | EMA20/EMA50 | Existing strategy metadata uses EMA fast 20 and slow 50. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trade/equity metrics | A separate one-off metrics module | Existing `backtest.metrics` plus added Phase 03 diagnostics | Existing tests validate core metrics. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] |
| MTF alignment | Raw weekly `reindex(..., method='ffill')` for daily decisions | Existing `MTFAligner` completed-bar lag behavior | Existing tests lock completed higher-timeframe usage. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py] |
| MTES conflict semantics | New opaque conflict score | Existing MTES direction/regime/`timeframe_conflict` metadata | Current evaluator exposes conflict metadata and flags. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py] |
| ADX/MACD patterns | New unregistered conventions | Existing `TrendEmaAdxStrategy` and `TrendMacdStrategy` style | Existing classes show metadata, parameters, and signal generation. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py] |
| Report conventions | Arbitrary output directories | `reports/` CSV + Markdown naming pattern | Phase 02 already uses this convention. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md] |

**Key insight:** Phase 03 should hand-roll only new combination logic and diagnostics; metrics, MTF alignment, and strategy conventions already exist locally. [VERIFIED: local files]

## Runtime State Inventory

This is a greenfield strategy-research phase, not a rename/refactor/migration phase. Runtime state inventory is omitted. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md]

## Common Pitfalls

### Pitfall 1: Treating Phase 02 overall score as a trading edge

**What goes wrong:** Low-switching or all-long indicators can score well on noise filtering while offering poor entries/exits. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]

**Why it happens:** Phase 02 `noise_score` uses trend-change stability. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py]

**How to avoid:** Require trade-level metrics, exposure, whipsaw count, and trade count for every experiment. [ASSUMED]

**Warning signs:** 100% bullish rate, one trend change, high noise score, and no meaningful trade list. [VERIFIED: /Users/iagent/projects/vibe-trading/reports/trend_indicator_report_20260530_204518.md]

### Pitfall 2: Parameter search leakage

**What goes wrong:** Parameters are selected and reported on the same full dataset. [ASSUMED]

**How to avoid:** Use walk-forward splits with train-only parameter selection and test-only reporting. [ASSUMED]

**Warning signs:** One exact parameter combination wins with no sensitivity plateau or out-of-sample result. [ASSUMED]

### Pitfall 3: Weekly/daily alignment lookahead

**What goes wrong:** Daily bars inside a week see final weekly SuperTrend for that same week. [ASSUMED]

**How to avoid:** Use `MTFAligner` with `lag_bars=1` or explicit completed-week shift. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py]

**Warning signs:** Weekly state changes appear on Monday before the weekly bar is complete. [ASSUMED]

### Pitfall 4: Choppy-market sample split is too shallow

**What goes wrong:** Aggregate averages improve while the strategy still fails in sideways regimes. [ASSUMED]

**How to avoid:** Split by ADX buckets, Chop buckets, trend efficiency, ATR percentile, symbol/market, and year. [ASSUMED]

**Warning signs:** Report has only aggregate metrics and no regime split. [ASSUMED]

### Pitfall 5: Corrected SuperTrend changes the baseline

**What goes wrong:** “Improvement” comes from changed indicator semantics rather than strategy combination. [ASSUMED]

**Why it happens:** Current Phase 02 ST uses simplified bands and `close > prev_st` logic. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py]

**How to avoid:** Include bridge baselines: current ST vs corrected ST on same sample. [ASSUMED]

## Code Examples

### Corrected SuperTrend Calculation Skeleton

```python
# Sources:
# - https://python.stockindicators.dev/indicators/SuperTrend/
# - /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Calculate stateful SuperTrend final bands without future bars."""
    data = df.copy()
    high, low, close = data["high"], data["low"], data["close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = pd.Series(index=data.index, dtype="float64")
    final_lower = pd.Series(index=data.index, dtype="float64")
    trend = pd.Series(index=data.index, dtype="float64")
    supertrend = pd.Series(index=data.index, dtype="float64")

    for i in range(len(data)):
        if i < period or pd.isna(atr.iloc[i]):
            continue
        if i == period:
            final_upper.iloc[i] = basic_upper.iloc[i]
            final_lower.iloc[i] = basic_lower.iloc[i]
            trend.iloc[i] = 1
            supertrend.iloc[i] = final_lower.iloc[i]
            continue

        prev_close = close.iloc[i - 1]
        prev_upper = final_upper.iloc[i - 1]
        prev_lower = final_lower.iloc[i - 1]
        final_upper.iloc[i] = basic_upper.iloc[i] if (basic_upper.iloc[i] < prev_upper or prev_close > prev_upper) else prev_upper
        final_lower.iloc[i] = basic_lower.iloc[i] if (basic_lower.iloc[i] > prev_lower or prev_close < prev_lower) else prev_lower

        if trend.iloc[i - 1] == -1 and close.iloc[i] > final_upper.iloc[i]:
            trend.iloc[i] = 1
        elif trend.iloc[i - 1] == 1 and close.iloc[i] < final_lower.iloc[i]:
            trend.iloc[i] = -1
        else:
            trend.iloc[i] = trend.iloc[i - 1]

        supertrend.iloc[i] = final_lower.iloc[i] if trend.iloc[i] == 1 else final_upper.iloc[i]

    data["st_final_upper"] = final_upper
    data["st_final_lower"] = final_lower
    data["st_trend"] = trend
    data["supertrend"] = supertrend
    return data
```

### Completed-Weekly Anchor Alignment Rule

```python
# Source: project pattern in MajorTrendEvaluator.score_mtf_alignment
# /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py

from backtest.strategies.mtf import MTFAligner, MTFConfig

aligned = MTFAligner(MTFConfig(lag_bars=1)).align_htf_to_ltf(
    htf_data=weekly_signals[["weekly_st_trend"]],
    ltf_data=daily_df[["close"]],
    htf_timeframe="1w",
    ltf_timeframe="1d",
    htf_columns=["weekly_st_trend"],
)
daily_df["weekly_st_trend_completed"] = aligned.data["htf_weekly_st_trend"]
```

### Strategy Decision Layer Skeleton

```python
# Source: Phase 03 architecture recommendation using local strategy conventions.
# /Users/iagent/projects/vibe-trading/agent/backtest/strategies/trend.py

long_allowed = (
    (daily_df["weekly_st_trend_completed"] == 1)
    & (daily_df["rf_direction"] == 1)
    & (daily_df["regime_allowed"])
    & (~daily_df["mtes_conflict"])
)

long_pullback_entry = (
    long_allowed
    & (daily_df["low"] <= daily_df["ema20"])
    & (daily_df["close"] > daily_df["ema20"])
)

long_breakout_entry = (
    long_allowed
    & (daily_df["close"] > daily_df["high"].shift(1).rolling(20).max())
)

long_momentum_recovery = (
    long_allowed
    & (daily_df["macd_hist"] > 0)
    & (daily_df["macd_hist"].shift(1) <= 0)
)
```

## State of the Art

| Old Approach | Current Phase 03 Approach | Impact |
|--------------|---------------------------|--------|
| Single indicator direction accuracy | Trade-level return/risk strategy evaluation | Avoids overvaluing stable but non-tradable indicators. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-VERIFICATION.md] |
| Daily SuperTrend standalone | Weekly SuperTrend anchor plus daily confirmation/entries | Uses Phase 02 weekly ST and daily RF evidence. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] |
| Raw MTF forward fill | Completed higher-timeframe lag alignment | Reduces weekly/daily lookahead risk. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py] |
| Aggregate-only score | Regime/symbol/time split metrics | Detects hidden regime and asset-class failures. [ASSUMED] |

**Deprecated/outdated:**
- Using Phase 02 `overall_score` as final strategy ranking is deprecated for Phase 03 because Phase 02 lacks full trading metrics. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]
- Direct weekly-to-daily `ffill` of current weekly state is deprecated for Phase 03 decisions; completed-bar alignment is required. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py]

## Phase 03 Recommended Deliverables and Acceptance Criteria

| Deliverable | Suggested Path | Acceptance Criteria |
|-------------|----------------|---------------------|
| Corrected SuperTrend implementation/tests | `agent/tests/test_supertrend_calculation.py` and planner-chosen implementation path | Tests cover final upper/lower bands, trend flips, warmup removal, and no future-bar use. [ASSUMED] |
| Experiment runner | `scripts/backtest_supertrend_enhancement.py` | CLI supports symbol/all/timeframe/matrix modes and writes CSV + Markdown reports to `reports/`. [ASSUMED] |
| Combination feature columns | output CSV | Rows include anchor trend, daily confirmation, regime flags, entry family, MTES conflict, and parameter set. [ASSUMED] |
| Trade metrics | output CSV/Markdown | Includes win rate, profit factor, MDD, Sharpe, Sortino, CAGR/annual return, Calmar, trade count, holding days/bars, exposure, whipsaw count, and regime split. [ASSUMED] |
| Experiment matrix report | `reports/supertrend_enhancement_comparison_*.csv` and `.md` | Includes E0-E10 or documented subset with reason. [ASSUMED] |
| Walk-forward validation | report section | Parameter grid uses train/test or rolling windows and reports out-of-sample separately. [ASSUMED] |
| Verification artifact | `.planning/phases/03-supertrend-enhancement-strategy/03-VERIFICATION.md` | Fresh commands reproduce outputs; tests pass; no lookahead failures. [ASSUMED] |

### Minimum Phase Gate

- At least one baseline and three combination strategies should run across the same Phase 02 25-symbol universe where sufficient warmup data exists. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-VERIFICATION.md] [ASSUMED]
- Reports must compare against daily ST, weekly ST, daily RF, and buy-and-hold baselines. [ASSUMED]
- A strategy must not be declared better unless it improves at least two risk-adjusted/trade-quality dimensions without collapsing trade count below a documented minimum. [ASSUMED]
- Every MTF experiment must document completed-week alignment and include a test/diagnostic proving no same-week leakage. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Weekly ST anchor plus daily confirmation is better architecture than daily ST standalone. | Summary / Architecture Patterns | Could underperform if weekly ST lags too much; matrix must validate. |
| A2 | Wilder-style ATR smoothing should be considered for corrected ST. | Standard SuperTrend Algorithm | If rolling ATR is intentionally preferred, corrected ST may reduce comparability. |
| A3 | EMA pullback, breakout, and RSI/MACD recovery are appropriate entry families. | Strategy Combination Stack | Could add complexity without edge; must be pruned if tests fail. |
| A4 | Suggested grid ranges are sufficient first-pass ranges. | Experiment Matrix | Could miss robust regions; planner may widen if runtime allows. |
| A5 | Exposure and whipsaw count should be added if absent from current metrics. | Trading Evaluation Metrics | If existing equivalents exist under different names, avoid duplicate columns. |
| A6 | Phase gate should target the same 25 symbols where data and warmup allow. | Phase Gate | Some symbols may be excluded after warmup; exclusions must be documented. |

## Open Questions (RESOLVED)

1. **Long-only vs long/short defaults — RESOLVED**
   - Decision: Phase 03 uses configurable `--mode long_only|long_short|auto`.
   - Default behavior: `auto` maps stock/ETF/A-share/US-stock markets to `long_only`; futures markets map to `long_short`.
   - Plan coverage: `03-03-PLAN.md` defines `resolve_trading_mode(market, config)` and tests market-specific defaults; `03-04-PLAN.md` exposes runner CLI `--mode`.

2. **Transaction cost/slippage assumptions — RESOLVED**
   - Decision: Phase 03 uses conservative configurable defaults of `transaction_cost_bps=5.0` and `slippage_bps=5.0`.
   - These assumptions must appear in feature output, CSV rows, Markdown reports, and validation artifacts.
   - Plan coverage: `03-03-PLAN.md` exposes fields in `EnhancementConfig`; `03-04-PLAN.md` requires CLI flags and report columns.

3. **Reusable code location — RESOLVED**
   - Decision: Stable reusable SuperTrend calculation goes into `agent/src/analysis/supertrend.py`.
   - Stable reusable enhancement feature/signal logic goes into `agent/src/analysis/supertrend_enhancement.py`.
   - Phase 03 experiment orchestration stays in `scripts/backtest_supertrend_enhancement.py` until research results justify promoting a registered strategy module.
   - Plan coverage: `03-01-PLAN.md`, `03-03-PLAN.md`, and `03-04-PLAN.md` follow this boundary.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Research/backtest runner | ✓ | 3.14.4 local and `.venv` [VERIFIED: environment probe] | Project requires `>=3.11`. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] |
| pandas | Indicator/report calculations | ✓ via dependency | `>=2.0.0` declared [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] | None needed. |
| numpy | Indicator/metrics calculations | ✓ via dependency | `>=1.24.0` declared [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] | None needed. |
| pytest | Validation | ✓ via dev dependency declaration | `>=7.0` declared [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] | Script smoke tests if pytest unavailable. [ASSUMED] |
| smart-search | Network research per project rule | ✓ | command available [VERIFIED: environment probe] | `extract-content` for known URLs. |
| extract-content | Docs extraction | ✓ | command available [VERIFIED: environment probe] | None needed. |
| graphify | Semantic project graph | ✗ disabled | graphify reported disabled [VERIFIED: graphify status] | Direct local file reads. |

**Missing dependencies with no fallback:** none for planning/research. [VERIFIED: environment probe]

**Missing dependencies with fallback:** graphify disabled; direct file reads were used. [VERIFIED: graphify status]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=7.0` declared. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] |
| Config file | `pyproject.toml`, `testpaths = ["agent/tests"]`, `pythonpath = ["agent"]`. [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] |
| Quick run command | `/Users/iagent/projects/vibe-trading/.venv/bin/python3 -m pytest agent/tests/test_supertrend_calculation.py -q` [ASSUMED] |
| Full suite command | `/Users/iagent/projects/vibe-trading/.venv/bin/python3 -m pytest agent/tests -q` [VERIFIED: /Users/iagent/projects/vibe-trading/pyproject.toml] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| P03-R1 | SuperTrend final bands, trend flips, warmup, no future bars | unit | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_calculation.py -q` | ❌ Wave 0 [ASSUMED] |
| P03-R2 | Completed weekly ST anchor alignment | unit/integration | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_strategy.py -q` | ❌ Wave 0 [ASSUMED] |
| P03-R3 | Regime/confirmation/entry filters emit expected fixture signals | unit | same as above | ❌ Wave 0 [ASSUMED] |
| P03-R4 | Trade metrics include required Phase 03 fields | unit | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_metrics.py -q` | ❌ Wave 0 [ASSUMED] |
| P03-R5 | Matrix CLI writes CSV/Markdown reports | smoke | `.venv/bin/python3 scripts/backtest_supertrend_enhancement.py --symbol GC=F --matrix baseline --output reports` | ❌ Wave 0 [ASSUMED] |
| P03-R6 | Walk-forward separates train/test outputs | integration | `.venv/bin/python3 scripts/backtest_supertrend_enhancement.py --all --walk-forward --output reports` | ❌ Wave 0 [ASSUMED] |

### Sampling Rate

- **Per task commit:** run the specific new test file plus single-symbol smoke run. [ASSUMED]
- **Per wave merge:** run all new Phase 03 tests and 2-3 symbol matrix smoke. [ASSUMED]
- **Phase gate:** run full Phase 03 matrix on available Phase 02 symbol universe and all new/affected tests. [ASSUMED]

### Wave 0 Gaps

- [ ] `agent/tests/test_supertrend_calculation.py` — covers P03-R1. [ASSUMED]
- [ ] `agent/tests/test_supertrend_enhancement_strategy.py` — covers P03-R2/P03-R3. [ASSUMED]
- [ ] `agent/tests/test_supertrend_enhancement_metrics.py` — covers P03-R4. [ASSUMED]
- [ ] `scripts/backtest_supertrend_enhancement.py` smoke command — covers P03-R5/P03-R6. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Phase 03 is local research/backtest code, not auth flow. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] |
| V3 Session Management | no | No session handling planned. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] |
| V4 Access Control | no | No new API or access-control surface planned. [ASSUMED] |
| V5 Input Validation | yes | Validate CLI args, symbol names, timeframe choices, and output paths. [ASSUMED] |
| V6 Cryptography | no | No cryptographic feature planned. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal through output path | Tampering | Resolve/check report paths and default to project `reports/`. [ASSUMED] |
| Secret leakage in reports | Information Disclosure | Never print env vars/API keys; project forbids committed secrets. [VERIFIED: /Users/iagent/projects/CLAUDE.md] |
| Unbounded grid-search runtime | Denial of Service | Cap grid size, support symbol filters, log matrix size before running. [ASSUMED] |
| Lookahead leakage | Integrity | Enforce completed-bar alignment tests and feature-generation tests. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py] |

## Sources

### Primary (HIGH confidence)

- `/Users/iagent/projects/vibe-trading/.planning/ROADMAP.md` — Phase 03 goal, dependencies, pending research path. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/.planning/STATE.md` — Phase 02 completion and latest report paths. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md` — Phase 02 rankings, recommendations, limitations. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-VERIFICATION.md` — fresh verification and gaps. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py` — current ST/RF/ADX/MTES/scoring. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/reports/trend_indicator_report_20260530_204518.md` — latest daily report. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/reports/trend_indicator_report_20260530_204526.md` — latest weekly report. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py` — MTES, regime, MTF alignment. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/tests/test_major_trend_evaluator.py` — MTF no-lookahead and MTES contract tests. [VERIFIED]
- `/Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py` — existing metrics tests. [VERIFIED]

### Secondary (MEDIUM confidence)

- `https://python.stockindicators.dev/indicators/SuperTrend/` — SuperTrend parameters, warmup, ATR-band purpose, upper/lower band outputs. [CITED]
- `https://python.stockindicators.dev/indicators/Adx/` — ADX parameters, +DI/-DI/ADX fields, trend-strength purpose. [CITED]
- `https://python.stockindicators.dev/indicators/Chop/` — Choppiness Index purpose/output. [CITED]
- `https://ta-lib.github.io/ta-doc/indicator/ATR.htm` — ATR documentation/reference. [CITED]
- `https://ta-lib.github.io/ta-doc/indicator/MACD.htm` — MACD documentation/reference. [CITED]
- `https://ta-lib.github.io/ta-doc/indicator/RSI.htm` — RSI documentation/reference. [CITED]

### Tertiary (LOW confidence)

- Pullback, breakout, RSI/MACD recovery, parameter grid, and acceptance-gate heuristics are marked `[ASSUMED]` and must be validated by Phase 03 experiments. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — dependencies and tests are explicit in local project files. [VERIFIED]
- Architecture: HIGH — roadmap, Phase 02 outputs, MTES/MTF/metrics code align. [VERIFIED]
- SuperTrend correction details: MEDIUM — docs confirm semantics/warmup/bands, but exact final-band implementation must be locked by fixtures. [CITED] [ASSUMED]
- Strategy combinations: MEDIUM — ingredients are supported, but efficacy is experimental. [VERIFIED] [ASSUMED]
- Pitfalls: HIGH for local scoring/alignment risks; MEDIUM for overfitting/grid-search risks. [VERIFIED] [ASSUMED]

**Research date:** 2026-05-30 [VERIFIED: currentDate]
**Valid until:** 2026-06-29 for local architecture; 2026-06-06 for strategy-efficacy assumptions because trading results are sample-sensitive. [ASSUMED]

## RESEARCH COMPLETE

**Phase:** 03 - SuperTrend Enhancement Strategy [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md]
**Confidence:** HIGH for implementation architecture; MEDIUM for expected trading efficacy pending backtests. [VERIFIED] [ASSUMED]

### Key Findings

- Phase 02’s ranking is not sufficient for strategy selection because it lacks transaction costs, position management, return/risk metrics, and walk-forward validation. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]
- Current Phase 02 SuperTrend is simplified: rolling-mean ATR, basic bands, and no explicit final upper/lower band state. [VERIFIED: /Users/iagent/projects/vibe-trading/scripts/backtest_trend_indicators.py]
- Phase 03 should use completed weekly SuperTrend as trend anchor and daily RangeFilter/regime/entry filters for timing. [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/ROADMAP.md] [VERIFIED: /Users/iagent/projects/vibe-trading/.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md]
- Existing project modules already provide foundations: `backtest.metrics`, MTES conflict/regime metadata, and `MTFAligner` completed higher-timeframe alignment. [VERIFIED: /Users/iagent/projects/vibe-trading/agent/tests/test_metrics.py] [VERIFIED: /Users/iagent/projects/vibe-trading/agent/src/analysis/major_trend_evaluator.py]
- Planner should create Wave 0 tests for SuperTrend correctness, MTF no-lookahead alignment, strategy signal fixtures, and Phase 03 metrics before running the full matrix. [ASSUMED]

### File Created

`/Users/iagent/projects/vibe-trading/.claude/worktrees/agent-aab9e180c2ae39817/.planning/phases/03-supertrend-enhancement-strategy/03-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Local dependencies and test config are explicit. [VERIFIED] |
| Architecture | HIGH | Roadmap, Phase 02 outputs, MTES/metrics/strategy modules align. [VERIFIED] |
| Pitfalls | HIGH/MEDIUM | Lookahead and Phase 02 scoring risks are verified locally; overfitting risks are general but material. [VERIFIED] [ASSUMED] |

### Open Questions (RESOLVED)

- Long-only vs long/short defaults: RESOLVED as configurable `--mode long_only|long_short|auto`; `auto` uses long-only for stock/ETF/A-share/US-stock markets and long-short for futures.
- Transaction cost/slippage assumptions: RESOLVED as configurable conservative defaults `transaction_cost_bps=5.0` and `slippage_bps=5.0`.
- Reusable code location: RESOLVED as `agent/src/analysis/supertrend.py` for canonical SuperTrend, `agent/src/analysis/supertrend_enhancement.py` for reusable feature/signal logic, and `scripts/backtest_supertrend_enhancement.py` for experiment orchestration.

### Ready for Planning

Research complete. Planner can now create PLAN.md files.
