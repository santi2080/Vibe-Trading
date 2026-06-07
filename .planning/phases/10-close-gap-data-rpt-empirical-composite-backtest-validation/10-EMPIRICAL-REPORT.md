# Phase 10 Empirical Composite Backtest Evidence

**Status:** blocked  
**Date range:** `2024-01-01` to `2026-01-01`  
**Intervals attempted:** `1D, 4H`  
**Source:** `yfinance` / `daily`

This report closes the v2.1 evidence gap truthfully: Phase 09 verified infrastructure, but Phase 10 empirical execution did **not** produce verified 2024-2026 composite-vs-single metrics because the available data/readiness and run-root controls blocked empirical runs. Metrics below are populated only from `evidence-1d.json` and `evidence-4h.json`; no metrics were inferred, recalculated from unavailable data, or invented.

## Scope and Fixed Configuration

- Phase: `10-close-gap-data-rpt-empirical-composite-backtest-validation`
- Fixed date range: `2024-01-01` to `2026-01-01`
- Attempted symbols: `GC=F, SI=F, CL=F`
- Eligible symbols: `none`
- Watchlist sources:
  - `watchlist/us_futures_watchlist.csv`
  - `watchlist/etf_watchlist.csv`
- Fixed configs:
  - `artifacts/configs/composite-empirical-1d.yaml`
  - `artifacts/configs/composite-empirical-4h.yaml`
- Strategy variants:
  - `MTES+SuperTrend`
  - `MTESv3-only`
  - `SuperTrend-only`
- Controls preserved:
  - `compare_single: true`
  - `atr_multiplier: 2.0`
  - Phase 09 MTES v3 and Enhanced SuperTrend parameters

## Strategy Comparison (RPT-01)

### 1D Evidence

| Variant | Status | Total Return | Win Rate | Sharpe Ratio | Max Drawdown | Trade Count | Missing Metrics |
|---------|--------|--------------|----------|--------------|--------------|-------------|-----------------|
| MTES+SuperTrend | blocked | missing | missing | missing | missing | missing | total_return, win_rate, sharpe_ratio, max_drawdown, trade_count |
| MTESv3-only | blocked | missing | missing | missing | missing | missing | total_return, win_rate, sharpe_ratio, max_drawdown, trade_count |
| SuperTrend-only | blocked | missing | missing | missing | missing | missing | total_return, win_rate, sharpe_ratio, max_drawdown, trade_count |

### 4H Evidence

| Variant | Status | Total Return | Win Rate | Sharpe Ratio | Max Drawdown | Trade Count | Missing Metrics |
|---------|--------|--------------|----------|--------------|--------------|-------------|-----------------|
| MTES+SuperTrend | blocked | missing | missing | missing | missing | missing | total_return, win_rate, sharpe_ratio, max_drawdown, trade_count |
| MTESv3-only | blocked | missing | missing | missing | missing | missing | total_return, win_rate, sharpe_ratio, max_drawdown, trade_count |
| SuperTrend-only | blocked | missing | missing | missing | missing | missing | total_return, win_rate, sharpe_ratio, max_drawdown, trade_count |

**RPT-01 conclusion:** blocked. A comparison report with verified empirical metrics was not produced. The closure evidence is the blocked status and diagnostics in:

- `artifacts/evidence-1d.json`
- `artifacts/evidence-4h.json`
- `artifacts/runs/1d/run-status.json`
- `artifacts/runs/4h/run-status.json`

## Best Configuration (RPT-02)

No best configuration can be identified from empirical performance because no variant produced verified comparable metrics.

- **Best by Sharpe:** blocked — no verified Sharpe values.
- **Best by total return:** blocked — no verified total return values.
- **Best by win rate:** blocked — no verified win rate values.

No global score/rank is computed. No Sharpe-first tie-break policy, candidate ranking, parameter tuning, or new strategy selection heuristic is introduced.

## Per-Source Performance (METR-03)

Per-source performance output remains blocked for empirical reporting. Phase 09 verified the infrastructure for per-source statistics and signal artifacts, but Phase 10 did not produce empirical run cards or signal artifacts under the intended 2024-2026 data coverage.

| Timeframe | Evidence Status | Signal Key Nodes | Per-Source Signals | Notes |
|-----------|-----------------|------------------|--------------------|-------|
| 1D | blocked | False | False | Metrics missing; see `evidence-1d.json`. |
| 4H | blocked | False | False | Metrics missing; see `evidence-4h.json`. |

## Data Quality (RPT-03)

Data quality is the primary blocker for empirical closure.

| Source | Gate Status | Can Backtest | Blocking Failures | Warnings | Total Checks |
|--------|-------------|--------------|-------------------|----------|--------------|
| us_futures | FAIL | False | 16 | 8 | 24 |
| etf | FAIL | False | 70 | 35 | 105 |

### 1D Blockers

- **data_readiness**: US futures and ETF readiness gates both report can_backtest=false; required local data files are missing.  \n  Evidence: `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data-readiness-us-futures.json, .planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data-readiness-etf.json`
- **safe_run_dir**: safe_run_dir rejected .planning/.../artifacts/runs/1d as outside allowed run roots; VIBE_TRADING_ALLOWED_RUN_ROOTS would be required to authorize this run root.  \n  Evidence: `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/runs/1d/run-status.json`
- Limitation: No 1D empirical metrics were produced because readiness failed and the configured .planning run root was not authorized by safe_run_dir.
- Limitation: Metrics are intentionally recorded as missing rather than recalculated, inferred, or invented.
- Limitation: No credentials were written and no strategy parameters were changed.

### 4H Blockers

- **data_readiness**: Readiness gates report can_backtest=false and no eligible symbols for empirical evidence.  \n  Evidence: `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data-readiness-us-futures.json, .planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data-readiness-etf.json`
- **4h_availability**: Attempted 4H auxiliary files are missing for the attempted US futures symbols; 4H cannot be verified from available local data.  \n  Evidence: `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/runs/4h/run-status.json`
- Limitation: No 4H empirical metrics were produced because the local readiness evidence contains no eligible symbols and missing 4H files.
- Limitation: The timeframe was not silently replaced with 1D or another interval.
- Limitation: Metrics are intentionally recorded as missing rather than recalculated, inferred, or invented.
- Limitation: No credentials were written and no strategy parameters were changed.

## Coverage and Limitations

- `DATA-01`: blocked — the 2024-2026 date range is fixed in config and manifest, but no eligible local data coverage was available for verified empirical metrics.
- `DATA-02`: blocked — watchlist coverage was attempted, but readiness gates reported `can_backtest=false` and no eligible symbols.
- `DATA-03`: blocked — both 1D and 4H were represented as attempted evidence; neither produced verified metrics from available local data.
- `METR-01`: blocked — no verified composite-vs-single return comparison.
- `METR-02`: blocked — no verified win rate, Sharpe, or max drawdown metrics.
- `METR-03`: blocked — no empirical per-source performance artifacts emitted from a verified run.
- `RPT-01`: blocked — this report records blocked evidence instead of a verified comparison report.
- `RPT-02`: blocked — no best configuration can be selected without verified metrics.
- `RPT-03`: verified as a data-quality report artifact, with empirical backtest data quality status blocked.

## Requirement Traceability

| Requirement | Status | Evidence |
|-------------|--------|----------|
| DATA-01 | blocked | `empirical-run-manifest.json`, `evidence-1d.json`, `evidence-4h.json` |
| DATA-02 | blocked | `data-readiness-us-futures.json`, `data-readiness-etf.json`, `empirical-run-manifest.json` |
| DATA-03 | blocked | `composite-empirical-1d.yaml`, `composite-empirical-4h.yaml`, `evidence-1d.json`, `evidence-4h.json` |
| RPT-01 | blocked | `10-EMPIRICAL-REPORT.md`, `evidence-1d.json`, `evidence-4h.json` |
| RPT-02 | blocked | `10-EMPIRICAL-REPORT.md` Best Configuration section |
| RPT-03 | verified | `10-EMPIRICAL-REPORT.md`, readiness artifacts, evidence JSON blockers |
| METR-01 | blocked | Metrics tables in this report show missing metrics under blocked status |
| METR-02 | blocked | Metrics tables in this report show missing win rate/Sharpe/max drawdown |
| METR-03 | blocked | Per-Source Performance section and artifact checks |

## Security Controls Preserved

Phase 10 did not weaken Phase 09 security controls. The following controls remain preserved or explicitly respected:

- Trusted signal-engine verification.
- Safe run-root validation (`safe_run_dir` blocked `.planning/.../artifacts/runs/1d` rather than being bypassed).
- Safe YAML/JSON loading.
- Fixed strategy variant allowlist.
- CSV safety controls.
- Subprocess timeout and output redaction/truncation.
- Data/artifact row limits.
- Env-only credential handling; no API keys, tokens, bearer credentials, or secrets are written into Phase 10 evidence artifacts.

