# Phase 03: SuperTrend Enhancement Strategy - Validation Plan

**Created:** 2026-05-30
**Status:** Planning validation gate

## Purpose

This validation artifact maps Phase 03 requirements to automated checks before execution. It closes the Nyquist-style planning gate by ensuring every critical behavior has a planned test or smoke command.

## Requirement → Verification Map

| Req ID | Behavior | Planned Test / Command | Planned In | Gate |
| --- | --- | --- | --- | --- |
| P03-R1 | Corrected/standard SuperTrend final upper/lower bands, trend state, warmup, and no future-bar behavior | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_calculation.py -q` | 03-01 | Must |
| P03-R1 | Legacy Phase 02 simplified SuperTrend is compared against corrected SuperTrend on the same sample | Runner/report contract asserts `legacy_phase02_st` and `corrected_supertrend` baseline rows plus delta columns | 03-05 | Must |
| P03-R2 | Completed weekly SuperTrend anchor aligns to daily bars without same-week leakage | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_calculation.py -q` with weekly/daily leakage fixture | 03-01 | Must |
| P03-R3 | Daily RangeFilter confirmation, ADX/Chop/ATR/trend-efficiency regime filters, entry trigger families, and MTES conflict filtering are deterministic | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_strategy.py -q` | 03-03 | Must |
| P03-R4 | Trade-level metrics include win rate, profit factor, max drawdown, Sharpe/Sortino, CAGR/Calmar, trade count, holding bars/days, exposure, whipsaw count, and regime split | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_metrics.py -q` | 03-02 | Must |
| P03-R5 | Matrix CLI writes CSV/Markdown reports with required identity, feature, baseline, metric, cost/slippage, no-lookahead, and exclusion fields | `.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_runner.py -q` plus single-symbol smoke | 03-05 | Must |
| P03-R6 | Walk-forward mode separates train-selected parameters from out-of-sample metrics and caps grid runtime | `.venv/bin/python3 scripts/backtest_supertrend_enhancement.py --symbol GC=F --matrix core --walk-forward --max-grid-size 12 --output reports` | 03-05 | Must |

## Automated Verification Commands

### Wave 1

```bash
.venv/bin/python3 -m pytest agent/tests/test_supertrend_calculation.py -q
.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_metrics.py -q
```

### Wave 2

```bash
.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_strategy.py -q
```

### Wave 3

```bash
.venv/bin/python3 -m pytest agent/tests/test_supertrend_validation_plan.py -q
```

### Wave 4

```bash
.venv/bin/python3 -m pytest agent/tests/test_supertrend_enhancement_runner.py -q
.venv/bin/python3 scripts/backtest_supertrend_enhancement.py --symbol GC=F --matrix smoke --output reports
.venv/bin/python3 scripts/backtest_supertrend_enhancement.py --symbol GC=F --matrix core --walk-forward --max-grid-size 12 --output reports
```

### Phase Gate

```bash
.venv/bin/python3 -m pytest agent/tests/test_supertrend_calculation.py agent/tests/test_supertrend_enhancement_metrics.py agent/tests/test_supertrend_enhancement_strategy.py agent/tests/test_supertrend_validation_plan.py agent/tests/test_supertrend_enhancement_runner.py -q
.venv/bin/python3 scripts/backtest_supertrend_enhancement.py --all --matrix core --max-grid-size 24 --output reports
```

If the full available-universe phase gate is skipped for runtime reasons, the executor summary must document:

1. why it was skipped,
2. the exact reproduction command,
3. the subset smoke results,
4. and which symbols were excluded due to warmup/data insufficiency.

## Required Report Evidence

Generated Markdown reports must include:

- baseline comparison: buy-and-hold, legacy Phase 02 SuperTrend, corrected daily SuperTrend, completed weekly SuperTrend anchor, daily RangeFilter, enhanced combinations;
- legacy-vs-corrected SuperTrend delta section;
- trading-mode and cost/slippage assumptions;
- no-lookahead statement for weekly-to-daily alignment;
- walk-forward train/test fields when enabled;
- regime split and whipsaw diagnostics;
- insufficient-data exclusions.

## Risks Covered

| Risk | Covered By |
| --- | --- |
| Standard SuperTrend implementation drift | 03-01 tests and legacy-vs-corrected baseline |
| Weekly/daily lookahead | 03-01 no-leakage fixture and report no-lookahead statement |
| Phase 02 score overvaluing low switching | 03-02 trade metrics and whipsaw diagnostics |
| Parameter overfitting | 03-05 bounded walk-forward mode |
| Huge grid runtime | `--max-grid-size` test and CLI guard |
| Ambiguous cost assumptions | configurable 5 bps cost + 5 bps slippage defaults documented in reports |

## Validation Complete

This artifact is ready for plan-checker review.
