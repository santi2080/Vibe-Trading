# SuperTrend Enhancement Validation Plan

**Phase:** 03-supertrend-enhancement-strategy
**Created:** 2026-05-31

## Objective

Validate whether the SuperTrend enhancement strategy (weekly SuperTrend anchor + daily RangeFilter confirmation + regime filters + entry triggers) improves trading performance versus:
1. A legacy Phase 02 simplified SuperTrend baseline (bridge baseline).
2. The canonical corrected SuperTrend computed by the Phase 03 module.
3. A no-confirmation weekly SuperTrend anchor baseline.

This is a strategy-research validation plan. It defines what evidence is required before any claim of improvement can be made.

---

## Bridge Baseline: Legacy vs Corrected SuperTrend

### Why the Bridge Baseline is Required

Phase 02 experiments used a simplified SuperTrend implementation that differs from the canonical SuperTrend formula. Before comparing enhanced combinations, we must establish a **bridge baseline** to separate:
- Improvement from correcting the SuperTrend formula itself.
- Improvement from the enhancement strategy logic.

### Legacy Phase 02 SuperTrend

The Phase 02 simplified SuperTrend used:
- Basic (non-stateful) final bands.
- Recalculated bands at each bar, not carry-forward state.
- No explicit warmup period handling.

### Corrected Canonical SuperTrend (Phase 03)

The Phase 03 canonical SuperTrend uses:
- **Stateful final bands** that carry forward (only move up in bull, only move down in bear).
- Trend flips only when close crosses the **relevant final band**, not the basic band.
- Explicit warmup period: `period × 3 + warmup_extra` (default 130 bars).
- Weekly anchor: uses only completed weekly bars with 1-bar lag (no same-week lookahead).

### Bridge Baseline Comparison

The validation must include a **legacy Phase 02 SuperTrend vs corrected SuperTrend** comparison to quantify the contribution of the formula correction alone. This comparison uses the same weekly alignment and entry triggers to isolate the effect of the SuperTrend calculation itself.

---

## Asset Universe

| Universe | Symbols | Data Source |
|----------|---------|-------------|
| US Futures | GC=F, SI=F, CL=F, ES=F, NQ=F | local `data/us_futures` cache |
| CN Futures | al0, rb0, ru0, cu0, au0 | local `data/cn_futures` cache |
| ETFs | SPY, QQQ, GLD, TLT | local `data/etf` cache |
| Stocks | Liquid US/CN names | existing local loaders/cache |

---

## Data Windows

- **Training / calibration:** first 40% of available history (threshold tuning only; no strategy selection).
- **Validation:** middle 30% for parameter perturbation and implementation checks.
- **Out-of-sample test:** final 30% for primary results.
- **Walk-forward:** rolling 12-month evaluation windows with 3-month step where sufficient history exists.

---

## Baseline Experiments

### B1: Weekly SuperTrend Only (Baseline)

Weekly SuperTrend anchor without daily confirmation, regime filters, or entry triggers.

### B2: Weekly ST + Daily RangeFilter (Bridge)

Weekly SuperTrend anchor + daily RangeFilter confirmation. **This is the primary bridge baseline** for comparing enhancement logic against.

### B3: Legacy Phase 02 SuperTrend (Bridge Baseline)

The simplified Phase 02 SuperTrend with the same weekly alignment and entry triggers as B2. **Required to quantify the contribution of the canonical SuperTrend correction.**

---

## Enhanced Experiments

### E1: Weekly ST Only

See B1.

### E2: Weekly ST + Daily RangeFilter

See B2.

### E3: E2 + ADX/Choppiness Regime Filters

E2 plus regime gating: ADX > 25, Choppiness < 61.8.

### E4: E3 + EMA Pullback Entry

E3 plus EMA pullback trigger for long entries.

### E5: E3 + Donchian Breakout Entry

E3 plus breakout trigger.

### E6: E3 + RSI Recovery Entry

E3 plus RSI recovery trigger.

### E7: E3 + MACD Recovery Entry

E3 plus MACD recovery trigger.

### E8: E4 + MTES Conflict Filter

E4 plus MTES conflict metadata veto.

---

## Signal Construction Rules

- **Weekly SuperTrend anchor:** use only completed weekly bars (1-bar lag, no same-week lookahead).
- **Signal delay:** one-bar delay after signal generation to prevent same-bar execution.
- **Entry confirmation:** require daily RangeFilter bullish (for longs) or bearish (for shorts) confirmation.
- **Regime filter:** block entries when ADX ≤ threshold or Choppiness ≥ 61.8.
- **MTES conflict filter (E8):** block entries when `mtes_conflict == True` or `timeframe_conflict == True`.

---

## Transaction Cost and Slippage Assumptions

| Asset Class | Transaction Cost | Slippage | Total One-Way |
|-------------|-----------------|----------|---------------|
| Futures | 2–3 bps | 2–3 bps | 4–6 bps |
| ETFs | 1–2 bps | 1–2 bps | 2–4 bps |
| Stocks | 2–5 bps | 2–5 bps | 4–10 bps |

Default assumptions for reporting: **5 bps transaction cost + 5 bps slippage = 10 bps one-way (20 bps round-trip)**.

Test across low/base/high assumptions to confirm conclusions are robust to cost changes.

---

## MTES Conflict Metadata Requirements

### Required Evidence

For experiments E8 and any MTES-filtered variants, the validation must report:

1. **Conflict count:** number of bars where `mtes_conflict == True`.
2. **Veto count:** number of entries blocked by MTES conflict filter.
3. **Conflict rate:** `conflict_count / total_bars` as percentage.
4. **Veto rate:** `veto_count / total_signals` as percentage.
5. **Timeframe conflict count:** number of bars where `timeframe_conflict == True`.
6. **MTES direction alignment:** correlation between MTES direction and weekly SuperTrend direction.

### MTES Conflict Frame Contract

The MTES conflict frame must contain columns:
- `mtes_direction`: 1 (bull) or -1 (bear)
- `mtes_regime`: "trending" or "choppy"
- `mtes_conflict`: True when MTES disagrees with weekly ST direction
- `timeframe_conflict`: True when shorter timeframe conflicts with weekly ST

These columns are derived from `MajorTrendEvaluator` output or the MTES metadata pipeline.

---

## Required Metrics

All experiments must report:

### Trading Metrics

| Metric | Description |
|--------|-------------|
| Win rate | Percentage of profitable trades |
| Profit factor | Gross profit / gross loss |
| Max drawdown | Maximum peak-to-trough decline |
| Sharpe ratio | Risk-adjusted return (annualized) |
| Sortino ratio | Downside risk-adjusted return |
| CAGR | Compound annual growth rate |
| Calmar ratio | CAGR / max drawdown |
| Trade count | Total number of trades |
| Avg holding bars | Average bars held per trade |
| Avg holding days | Average calendar days held |
| Exposure | Percentage of bars invested |
| Whipsaw count | Trades reversed within 5 bars with loss ≤ 0 |
| Transaction cost bps | Configured transaction cost |
| Slippage bps | Configured slippage |

### Direction Accuracy Metrics

| Metric | Description |
|--------|-------------|
| Direction accuracy | Percentage of correct trend predictions |
| Mean lag | Average delay in trend detection |
| False signal rate | Signals against actual trend direction |

### Regime Split Metrics

Per-regime breakdown of trading metrics for ADX/Choppiness regime buckets.

---

## Validation Helpers

Reuse existing backtest validation helpers rather than introducing a parallel statistical subsystem:

- `run_validation`: primary validation runner with train/validate/test splits
- `monte_carlo_test`: Monte Carlo simulation for metric distributions
- `bootstrap_sharpe_ci`: bootstrap confidence intervals for Sharpe ratio
- `walk_forward_analysis`: rolling window walk-forward validation

---

## Parameter Sensitivity

Test the following parameter perturbations:

| Parameter | Default | Perturbation Range |
|-----------|---------|-------------------|
| SuperTrend period | 10 | 7–15 |
| SuperTrend multiplier | 3.0 | 2.0–4.0 |
| ADX threshold | 25 | 20–30 |
| Choppiness threshold | 61.8 | 55–68 |
| EMA fast | 20 | 15–25 |
| EMA slow | 50 | 40–60 |

Conclusions must hold across at least 3 parameter sets (low/default/high) within the perturbation ranges.

---

## Robustness Checks

### No-Lookahead Verification

- Verify weekly SuperTrend uses only completed bars (1-bar lag).
- Verify signal generation does not use same-bar price data.
- Report warmup period discarded: `period × 3 + warmup_extra` bars.

### Walk-Forward Validation

- Rolling 12-month evaluation windows with 3-month step.
- Report distribution of metrics across walk-forward windows.
- Compare median and worst-case outcomes across windows.

### Monte Carlo Simulation

- Resample equity curves to estimate metric distributions.
- Report 5th/25th/median/75th/95th percentiles.
- Confirm primary conclusions hold at 75th percentile or better.

### Bootstrap Confidence Intervals

- Bootstrap Sharpe ratio and max drawdown distributions.
- Report 95% confidence intervals.
- Confirm non-overlapping confidence intervals between baseline and best enhanced experiment.

---

## Reporting Artifacts

After running experiments, the following artifacts must be generated:

1. **Bridge baseline report:** `reports/supertrend_bridge_comparison_YYYYMMDD.csv` — legacy vs corrected SuperTrend comparison.
2. **Experiment summary:** `reports/supertrend_enhancement_summary_YYYYMMDD.csv` — all E1–E8 metrics.
3. **Direction accuracy report:** `reports/supertrend_direction_accuracy_YYYYMMDD.csv` — accuracy and lag metrics.
4. **MTES conflict report:** `reports/supertrend_mtes_conflict_YYYYMMDD.csv` — conflict/veto counts per experiment.
5. **Walk-forward report:** `reports/supertrend_walkforward_YYYYMMDD.csv` — rolling window results.
6. **Sensitivity report:** `reports/supertrend_sensitivity_YYYYMMDD.csv` — parameter perturbation results.
7. **Final validation report:** `reports/SUPERTREND_ENHANCEMENT_VALIDATION_REPORT_YYYYMMDD.md` — human-readable summary.

---

## Contract

This document is a **validation contract**. The following cannot be claimed without evidence:

1. ❌ "Enhanced strategy outperforms SuperTrend alone" — without bridge baseline comparison.
2. ❌ "SuperTrend enhancement improves returns" — without trading metrics (win rate, Sharpe, drawdown).
3. ❌ "Weekly SuperTrend is better" — without no-lookahead verification.
4. ❌ "Strategy is robust" — without walk-forward and Monte Carlo evidence.
5. ❌ "MTES filter improves signals" — without conflict/veto count evidence.

The experiment runner (Phase 03-05) must produce all required artifacts before any improvement claim can be made.
