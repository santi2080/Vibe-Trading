---
status: complete
phase: 10-close-gap-data-rpt-empirical-composite-backtest-validation
source:
  - 10-EMPIRICAL-REPORT.md
  - artifacts/final-evidence-index.json
started: 2026-06-07T11:57:00Z
updated: 2026-06-07T12:08:00Z
---

## Current Test

[testing complete]

## Tests

### 1. 2024-2026 date range
expected: Phase 10 evidence uses the intended 2024-01-01 to 2026-01-01 range.
result: pass
notes: Fixed range appears in `empirical-run-manifest.json`, `composite-empirical-1d.yaml`, `composite-empirical-4h.yaml`, and `10-EMPIRICAL-REPORT.md`.

### 2. Watchlist coverage
expected: Phase 10 covers intended watchlist major instruments where data is available, or explicitly documents unavailable coverage.
result: blocked
notes: Readiness artifacts report `can_backtest=false` and `eligible_symbols: []`; coverage is documented but not empirically verified.

### 3. 1D evidence
expected: 1D empirical evidence exists for composite, MTES-only, and SuperTrend-only variants, or exact blocker is documented.
result: blocked
notes: `evidence-1d.json` exists and records blocked status due to readiness failure and `safe_run_dir` run-root rejection.

### 4. 4H evidence or block
expected: 4H evidence is attempted and verified, partial, or blocked with source limitations.
result: blocked
notes: `evidence-4h.json` exists and records blocked status from missing local 4H/readiness evidence.

### 5. Composite / MTES-only / SuperTrend-only comparable metrics
expected: Total return, win rate, Sharpe ratio, max drawdown, and trade count are comparable across the three variants.
result: blocked
notes: Variant labels and metric schema are present, but all required metric values are missing under blocked status.

### 6. Strategy Comparison report section
expected: `10-EMPIRICAL-REPORT.md` includes `Strategy Comparison (RPT-01)` and accurately reflects evidence status.
result: pass
notes: Section exists and states the comparison is blocked rather than verified.

### 7. Best Configuration section
expected: `10-EMPIRICAL-REPORT.md` includes `Best Configuration (RPT-02)` without introducing new ranking heuristics.
result: pass
notes: Section states no best configuration can be selected without verified metrics and no global score/rank is computed.

### 8. Per-Source Performance section
expected: `10-EMPIRICAL-REPORT.md` includes `Per-Source Performance (METR-03)` and uses real artifact checks.
result: blocked
notes: Section exists, but empirical per-source artifacts were not produced by a verified run.

### 9. Data Quality section
expected: `10-EMPIRICAL-REPORT.md` includes `Data Quality (RPT-03)` with completeness checks and blocker evidence.
result: pass
notes: Section includes readiness gate status for US futures and ETF, plus blocker details.

### 10. Phase 09 security controls preserved
expected: Closure evidence preserves trusted signal-engine verification, safe run-root validation, safe YAML/JSON loading, variant allowlist, CSV safety, subprocess timeout/redaction, data/artifact row limits, and env-only credential handling.
result: pass
notes: `10-EMPIRICAL-REPORT.md` lists preserved controls; `safe_run_dir` blocked an unauthorized `.planning` run root rather than being bypassed.

## Summary

total: 10
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 5

## Gaps

### G-10-01: Empirical metric evidence remains blocked
status: blocked
requirements: DATA-01, DATA-02, DATA-03, RPT-01, RPT-02, METR-01, METR-02, METR-03
reason: Local readiness gates returned `can_backtest=false`, no eligible symbols were available, and the configured `.planning` run root was rejected by `safe_run_dir` without explicit authorization.
recommended_next_step: Either accept blocked closure before archiving v2.1, or create a follow-up remediation phase that provides local 2024-2026 1D/4H data and an authorized safe run root.
