# Phase 1: Major Trend Evaluation System — Specification

**Created:** 2026-05-28
**Ambiguity score:** 0.11 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

Vibe-Trading can assign each watchlist asset a cross-asset major-trend score from 0–100, classify its trend state, explain the component drivers, and define a backtest validation plan for stocks, ETFs, futures, crypto, and FX.

## Background

Vibe-Trading already has pieces of a trend-following stack:

- `agent/backtest/strategies/trend.py` provides `TrendEmaAdxStrategy`, `TrendMacdStrategy`, and `TrendDualEmaStrategy`.
- `agent/src/skills/trend/ema_trend/SKILL.md` defines EMA-based trend detection.
- `agent/src/skills/trend/adx_trend/SKILL.md` defines ADX/+DI/-DI trend-strength detection.
- `agent/src/skills/entry/range_filter/SKILL.md` defines Range Filter noise filtering and direction detection.
- `agent/backtest/strategies/entry.py` provides breakout, volume spike, VWAP, and confluence entry strategies.
- `agent/backtest/strategies/pullback.py` provides RSI, Bollinger, Stochastic, and Fibonacci pullback strategies.
- `agent/src/skills/volatility/SKILL.md` defines historical volatility percentile regime logic.
- `agent/backtest/strategies/mtf.py` provides multi-timeframe alignment with look-ahead prevention.
- `agent/src/analysis/watchlist_analyzer.py` already performs batch watchlist analysis using EMA + ADX + RSI + ATR.
- `agent/src/skills/multi-factor/SKILL.md` and `agent/src/skills/alpha-zoo/SKILL.md` provide cross-sectional momentum/factor infrastructure.

The missing capability is a unified major-trend evaluation layer. Existing watchlist output classifies a simple trend and trade signal, but it does not produce a cross-asset, explainable, weighted, multi-dimensional trend score suitable for ranking assets and separating true major trends from choppy conditions.

## Requirements

1. **MTES score model**: Define a Major Trend Evaluation System score from 0–100 using six locked dimensions: direction, strength, structure, momentum, volatility/noise regime, and multi-timeframe alignment.
   - Current: Trend status is primarily inferred from EMA + ADX in `WatchlistAnalyzer.analyze_trend`; no unified 0–100 major-trend score exists.
   - Target: Each analyzed asset receives a `trend_score` between 0 and 100, plus per-dimension sub-scores whose sum equals the total score.
   - Acceptance: For a sample OHLCV DataFrame, evaluator output contains `trend_score` and six named sub-scores; the total equals the sum of sub-scores within rounding tolerance.

2. **Trend state classification**: Classify each asset into one of seven trend states based on score and direction: `BULL_STRONG`, `BULL_CONFIRMED`, `BULL_EARLY`, `NEUTRAL_CHOPPY`, `BEAR_EARLY`, `BEAR_CONFIRMED`, `BEAR_STRONG`.
   - Current: Existing output uses `UP`, `DOWN`, `SIDEWAYS`, and trade signals such as `LONG`, `SHORT`, `NEUTRAL`.
   - Target: Major-trend evaluation produces a trend-state label that distinguishes early, confirmed, and strong trends in both directions.
   - Acceptance: Deterministic fixtures covering strong bull, early bull, choppy, early bear, and strong bear cases map to the expected seven-state labels.

3. **Cross-asset weighting profiles**: Provide asset-class-specific scoring weights for stocks, ETFs, futures, crypto, and FX.
   - Current: Existing strategies declare supported markets, but trend scoring does not adjust weights by asset class.
   - Target: The system has explicit weight profiles for `stock`, `etf`, `futures`, `crypto`, and `fx`; each profile totals 100 and changes emphasis by asset class.
   - Acceptance: Loading each supported asset profile returns six dimension weights totaling 100; unsupported asset classes fail with a clear validation error.

4. **Direction dimension**: Score major trend direction using long-horizon price/average relationships and slope, not only fast EMA crossover.
   - Current: EMA fast/slow crossover exists, but long-horizon MA/EMA state and slope are not exposed as major-trend direction components.
   - Target: Direction scoring includes price vs long moving average, intermediate vs long moving average, long average slope, and long-horizon return direction.
   - Acceptance: A fixture where price is above rising long averages scores positive direction; a fixture below falling long averages scores bearish direction; a flat fixture scores neutral/low.

5. **Structure and momentum dimensions**: Score trend quality using price structure and return momentum, not only smoothed indicators.
   - Current: Breakout and multi-factor momentum tools exist separately; no major-trend score combines Donchian/swing structure with 3/6/12-month momentum.
   - Target: Structure scoring includes breakout/range state or higher-high/higher-low logic; momentum scoring includes at least 3M, 6M, and 12M returns when enough data exists.
   - Acceptance: The evaluator reports separate `structure` and `momentum` sub-scores and marks insufficient lookback data without crashing.

6. **Volatility/noise regime dimension**: Detect whether the asset is suitable for trend-following instead of merely directional.
   - Current: ATR, Range Filter, and HV percentile exist in separate modules/skills.
   - Target: Regime scoring uses volatility percentile, ATR percentage or equivalent volatility normalization, and a noise/trend-efficiency or Range Filter component.
   - Acceptance: Choppy fixtures receive lower regime scores than smooth directional fixtures with similar net return; extreme volatility fixtures are flagged in output metadata.

7. **Multi-timeframe alignment**: Include high-timeframe confirmation without look-ahead bias.
   - Current: `MTFAligner` can align higher-timeframe data to lower-timeframe data with lag, but watchlist trend scoring does not use a locked MTF score.
   - Target: The score model includes an MTF dimension that rewards agreement between configured higher and base timeframes while preserving the existing lagged alignment rule.
   - Acceptance: Tests verify higher-timeframe values used by a lower-timeframe bar come only from completed higher-timeframe bars; aligned bull/bear fixtures receive higher MTF scores than conflicting fixtures.

8. **Watchlist batch output**: Extend watchlist analysis output with major-trend score, state, direction, confidence, regime, and top drivers.
   - Current: Watchlist reports include trend, pullback, signal, price, stop loss, ATR, and confidence.
   - Target: Watchlist output supports human-readable tables and machine-readable JSON with MTES fields for every asset.
   - Acceptance: Running watchlist analysis on a fixture watchlist returns JSON containing `symbol`, `asset_class`, `trend_score`, `trend_state`, `direction`, `confidence`, `regime`, `sub_scores`, and `top_drivers` for every analyzable row.

9. **Backtest validation plan**: Define a reproducible validation plan comparing the MTES model against single-indicator baselines.
   - Current: Backtest infrastructure and metrics exist, but no validation plan exists for MTES versus MA, EMA/ADX, Donchian, Supertrend-like trailing, Range Filter, or momentum baselines.
   - Target: This phase produces a documented validation plan specifying baseline strategies, asset universes, time splits, metrics, transaction-cost assumptions, parameter perturbation, and delay robustness tests.
   - Acceptance: The plan names at least five baselines, five validation metrics, supported asset universes, and pass/fail robustness checks for parameter sensitivity and signal delay.

## Boundaries

**In scope:**

- MTES scoring specification with six explicit dimensions.
- Asset-class weight profiles for stocks, ETFs, futures, crypto, and FX.
- Trend-state labels and score thresholds.
- Watchlist-compatible output contract for human table and JSON consumers.
- Explainability contract: sub-scores, top drivers, regime flags, and concise explanation text.
- Backtest validation plan comparing MTES to single-indicator baselines.
- Tests or fixtures sufficient to verify scoring, classification, asset profile validation, and MTF look-ahead safety.

**Out of scope:**

- Live trading or order execution — this phase evaluates trend state only.
- Portfolio construction and position sizing beyond optional risk metadata — allocation belongs to a separate portfolio/risk phase.
- Optimizing indicator parameters for maximum return — this phase defines robust defaults and validation, not parameter mining.
- Adding new external data vendors — existing data loaders and local data are used.
- Fundamental analysis, news, macro, on-chain, funding, or sentiment integration — these may be later overlays but are excluded from the first MTES phase.
- Visual chart rendering — markdown/JSON reports are in scope; chart UI is separate.
- Replacing existing Trend/Pullback/Entry strategies — MTES complements them as a higher-level evaluation layer.

## Constraints

- The scoring model must be deterministic for a fixed input DataFrame and configuration.
- Each asset-class profile must total 100 across the six scoring dimensions.
- Missing optional columns such as `volume` must not crash the evaluator; unavailable components must be marked and handled predictably.
- Multi-timeframe alignment must preserve the existing no-look-ahead principle from `MTFAligner`.
- The default model must avoid hard AND confirmation across many similar lagging indicators; the phase uses weighted scoring to reduce unnecessary lag.
- The output contract must remain usable by watchlist batch analysis and future backtest runners.
- This phase should reuse existing project modules where practical instead of duplicating indicator logic without reason.

## Acceptance Criteria

- [ ] MTES output contains `trend_score` in `[0, 100]` and six named sub-scores for every asset with sufficient data.
- [ ] Sub-score weights for `stock`, `etf`, `futures`, `crypto`, and `fx` profiles each total 100.
- [ ] Output classifies assets into the seven locked trend states.
- [ ] Direction, strength, structure, momentum, volatility/noise, and MTF dimensions are independently visible in JSON output.
- [ ] Watchlist batch output includes MTES fields for every successfully analyzed symbol.
- [ ] Insufficient data produces a clear status or warning instead of an unhandled exception.
- [ ] Multi-timeframe scoring uses only completed higher-timeframe bars.
- [ ] Explainability output includes at least three top drivers or all available drivers if fewer than three exist.
- [ ] Backtest validation plan compares MTES against at least five single-indicator baselines.
- [ ] Validation plan includes return, drawdown, Sharpe/Calmar or equivalent, turnover, false-signal or whipsaw rate, and signal-delay robustness.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.93  | 0.75 | ✓      | Goal is a concrete 0–100 scoring/evaluation system with defined outputs. |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | In/out scope explicitly separates scoring from execution, allocation, and external data work. |
| Constraint Clarity | 0.82  | 0.65 | ✓      | Determinism, asset profile totals, missing data, and no-look-ahead constraints are locked. |
| Acceptance Criteria| 0.88  | 0.70 | ✓      | Pass/fail checks cover scoring, output contract, MTF safety, explainability, and validation plan. |
| **Ambiguity**      | 0.11  | ≤0.20| ✓      | Gate passed. |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | What exists in Vibe-Trading today related to trend evaluation? | Existing modules include EMA/ADX trend, Range Filter, volatility, MTF alignment, watchlist analysis, and factor infrastructure. |
| 2 | Simplifier | What is the simplest useful version? | A six-dimension weighted score with watchlist output and explanation is the MVP; no live trading or portfolio allocation. |
| 3 | Boundary Keeper | What should not be done in this phase? | Execution, portfolio sizing, external data vendors, fundamentals/news/macro overlays, and chart UI are excluded. |
| 4 | Failure Analyst | What would make the system invalid? | Hard AND stacking of lagging indicators, no asset-specific weighting, look-ahead in MTF, or unexplainable scores would fail verification. |
| 5 | Seed Closer | How should different assets be handled? | Stocks, ETFs, futures, crypto, and FX get separate six-dimension weight profiles totaling 100. |
| 6 | Seed Closer | How should completion be verified? | Use deterministic fixtures, JSON contract checks, MTF safety tests, and a documented backtest validation plan versus baselines. |

---

*Phase: 01-major-trend-evaluation-system*
*Spec created: 2026-05-28*
*Next step: /gsd:discuss-phase 1 — implementation decisions (how to build what's specified above)*
