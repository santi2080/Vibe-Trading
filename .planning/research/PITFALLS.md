# Pitfalls Research: v2.2 Daily Scan Report Loop

## Summary

The main risk is producing a polished Markdown report while bypassing validated project contracts: the data-health gate, `TradingSignal`, `CompositeTrendStrategy`, artifact safety, and v2.1 empirical-evidence constraints.

v2.2 should be conservative: a reliable data pipeline and report artifact loop, not a trade-decision or ranking engine.

## Failure Modes and Prevention

### 1. Bypassing the data-health gate

**Risk:** Candidates emitted despite missing/stale data.

**Prevention:** Data-health gate must be the first scan stage. `FAIL` blocks strategy execution by default. `WARN` is surfaced prominently.

### 2. Reusing legacy analyzer semantics

**Risk:** Report uses old EMA/ADX/RSI `LONG/SHORT` semantics instead of validated `TradingSignal` / Composite contracts.

**Prevention:** Define `DailyScanResult` around `TradingSignal`, source provenance, conflict reasons, and health status.

### 3. Markdown-only output

**Risk:** Human report exists but agents/tests cannot inspect deterministic results.

**Prevention:** Always write `manifest.json`, `data_health.json`, `scan_results.json`, and `report.md`.

### 4. Hiding warnings or over-blocking

**Risk:** Auxiliary timeframe warnings are either invisible or treated as hard failures.

**Prevention:** Preserve `PASS` / `WARN` / `FAIL`; annotate candidates and overview with warnings.

### 5. Calendar/session false positives

**Risk:** Weekend/holiday/session effects make fixed staleness rules noisy.

**Prevention:** In MVP, disclose fixed-window freshness and `calendar_adjusted: false`; defer full exchange calendars unless needed.

### 6. Hard-coded paths / environment coupling

**Risk:** Report works only on developer machine or cross-project data paths.

**Prevention:** Require explicit/repo-relative `--watchlist`, `--data-dir`, `--output-dir`; record resolved paths in manifest.

### 7. Unsafe output paths and overwrites

**Risk:** Report writes outside intended directory or overwrites previous runs.

**Prevention:** Use safe report root, run directories, atomic writes, and collision policy.

### 8. Over-ranking before empirical validation

**Risk:** Unverified Top 10 or numeric scoring implies performance evidence that v2.1 explicitly lacks.

**Prevention:** Use grouped buckets: Actionable, Watch, Risk/Excluded. Avoid expected-return/win-rate/Sharpe claims unless linked to verified artifacts.

### 9. Hiding excluded symbols

**Risk:** User cannot tell whether a symbol was scanned, blocked, or not ready.

**Prevention:** Every input symbol must be assigned to one bucket or counted with a reason code.

### 10. Mixed stdout / poor error semantics

**Risk:** CLI/tool output becomes unparseable.

**Prevention:** JSON mode stdout must be parseable; progress/logs to stderr; documented exit codes.

## Verification Recommendations

Minimum tests:
- data-health failure blocks scan
- warning-only auxiliary gaps still report caveats
- Composite READY maps to Actionable only when data passes
- source conflicts map to Risk/Excluded
- every symbol assigned to a bucket or reason
- Markdown counts match JSON artifact counts
- blocked report is clearly marked
- no unverified performance claims or global ranking
- path traversal rejected
- CLI exit codes and stdout/stderr behavior validated

## Recommended Roadmap Quality Gate

Before closing v2.2, require evidence that:
- data-health gate runs before strategy analysis
- scan uses `TradingSignal` / Composite semantics
- JSON artifacts and Markdown agree
- no unvalidated performance/ranking claims are introduced
- one-command CLI works with local fixtures in a clean environment
