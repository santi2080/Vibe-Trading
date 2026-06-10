# Feature Research: v2.2 Daily Scan Report Loop

**Focus:** Data-pipeline-first daily watchlist scanning and Markdown reporting.

## Summary

A daily market scan/reporting pipeline should behave like a deterministic batch data product, not an ad-hoc analysis script. Internally it should validate watchlist input, resolve required timeframes/cache paths, verify or refresh data, run a health gate, scan eligible symbols, preserve skip/failure reasons, generate machine-readable artifacts, and render a human-readable Markdown report.

For v2.2, the core product is the data pipeline. Trading conclusions should remain bounded to existing strategy outputs (`TradingSignal`, MTES v3, `CompositeTrendStrategy`) and avoid unverified trade recommendation UX.

## Table Stakes

- One-command daily scan entry point.
- Watchlist validation before execution.
- Market/timeframe/cache-path run plan.
- Mandatory local data-health gate.
- Optional explicit refresh mode or clear no-refresh mode.
- Symbol-level skip/failure semantics.
- Report generation with partial data when policy allows.
- Machine-readable JSON artifacts.
- Markdown report with data provenance.
- Deterministic output paths and run IDs.
- Clear exit codes.
- Configurable failure policy.
- Tests for the pipeline, artifacts, and report sections.

## Differentiators

Useful but secondary:
- Data-readiness score per symbol.
- Daily delta vs previous scan.
- Data provenance fingerprints.
- Refresh attempt summary.
- Agent-tool compatibility.
- Run history index.

## Anti-Features

Explicitly avoid in v2.2:
- Live or paper trading execution.
- Automated order sizing / portfolio allocation.
- Parameter optimization during daily scan.
- Backtest reruns as part of daily scan.
- Real-time streaming scanner.
- LLM-generated narrative as the core output.
- Web dashboard or large watchlist management UI.
- Unverified Top 10 ranking / performance claims.

## Suggested Requirement Categories

1. CLI / Entry Point
2. Watchlist Intake and Validation
3. Data Refresh and Cache Resolution
4. Data Health Gate and Failure Policy
5. Scan Execution
6. Artifacts and Schema
7. Markdown Report
8. Testing and Verification

## Recommended MVP Cut

Prioritize:
- one-command runner
- watchlist validation and run plan
- mandatory data-health gate
- symbol-level skip/failure semantics
- stable JSON artifacts + manifest
- Markdown report with data-health and scan summaries
- local-fixture tests for the full pipeline

Defer:
- exchange calendars
- daily delta
- multi-watchlist index
- provider refresh complexity beyond explicit modes
- final trading decision UX
