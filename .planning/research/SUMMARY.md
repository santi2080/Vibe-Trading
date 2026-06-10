# Research Summary: v2.2 Daily Scan Report Loop

**Milestone:** v2.2 daily-scan-report-loop  
**Focus:** Data-pipeline-first daily watchlist scanning and Markdown reporting  
**Synthesized:** 2026-06-08

## Executive Summary

v2.2 should productize daily scanning as a deterministic batch data pipeline, not as an ad-hoc report script or trading-decision engine. The milestone should deliver a one-command local workflow that validates a watchlist, verifies data readiness, scans eligible symbols using existing validated signal contracts, writes structured artifacts, and renders a Markdown report from those artifacts.

The strongest implementation direction is to add a focused `agent/src/scan/` orchestration package above the existing `src.data` and `src.strategies` layers. Do not redesign MTES v3, `TradingSignal`, `CompositeTrendStrategy`, or backtest infrastructure.

## Stack Additions

- Keep the existing Python / pandas / Parquet / argparse stack.
- Explicitly declare `pyarrow>=15.0.0` if missing, because daily scan reliability depends on `pd.read_parquet()` / `DataFrame.to_parquet()`.
- Add a small `agent/src/scan/` package for orchestration, models, artifacts, and Markdown rendering.
- Do not add Airflow, Prefect, Dagster, Celery, Redis, a new database, Polars, dashboards, or new market data vendors for this milestone.

## Feature Table Stakes

- One-command daily scan entry point.
- Watchlist validation before data/strategy work.
- Run plan with normalized symbols, markets, timeframes, cache paths, and output paths.
- Mandatory data-health gate before strategy execution.
- Symbol-level skip/failure semantics.
- Stable JSON artifacts:
  - `manifest.json`
  - `data_health.json`
  - `scan_results.json`
- Human-readable `report.md` rendered from structured artifacts.
- Deterministic output directory and run ID policy.
- Clear CLI/tool exit semantics.
- Tests for path safety, data-health blocking, symbol bucketing, artifact schemas, and Markdown/report consistency.

## Recommended MVP Scope

Include:
- local-data-first daily scan runner
- watchlist validation and normalized run plan
- mandatory data-health gate
- symbol-level eligibility and reason codes
- composite/`TradingSignal`-based scan results for eligible symbols
- JSON artifacts + Markdown report
- one-command CLI/script surface
- local fixture tests

Defer:
- exchange-calendar-aware freshness
- daily delta vs previous scan
- multi-watchlist index
- complex provider refresh/fallback automation
- dashboard/web UI
- LLM-generated narrative
- Top 10 ranking or performance claims
- live/paper trading execution

## Architecture Guidance

Recommended package:

```text
agent/src/scan/
├── config.py
├── models.py
├── data_loader.py
├── strategy_factory.py
├── pipeline.py
├── artifacts.py
└── markdown.py
```

Recommended dependency direction:

```text
src.data/*       -> data contracts, watchlist parsing, health gate
src.strategies/* -> signal generation contracts and strategy logic
src.scan/*       -> daily scan orchestration, run artifacts, report payloads
src.tools/*      -> thin wrappers around scan pipeline
scripts/cli      -> one-command entrypoint
backtest/*       -> unchanged
```

Recommended data flow:

```text
CLI / Tool / MCP
  -> DailyScanConfig
  -> WatchlistReader
  -> optional explicit refresh stage
  -> check_watchlist_data
  -> if FAIL: blocked artifacts/report, exit nonzero
  -> ScanDataLoader for eligible symbols
  -> CompositeTrendStrategy.analyze(df)
  -> TradingSignal.to_dict()
  -> scan_results.json / data_health.json / manifest.json
  -> report.md
```

## Suggested Build Order

1. Scan contracts, config, safe output root, and health-gated skeleton.
2. Local data loader and symbol eligibility semantics.
3. Composite strategy / `TradingSignal` scan integration.
4. Artifact writer and Markdown renderer.
5. CLI/tool wrapper and verification harness.
6. Optional controlled refresh mode and run-history enhancements.

## Watch-Outs

- Do not bypass the data-health gate.
- Do not use legacy EMA/ADX/RSI analyzer semantics as the canonical v2.2 signal contract.
- Do not make Markdown the only output; write JSON artifacts first.
- Do not hide excluded/blocked symbols.
- Do not silently substitute stale or fallback data.
- Do not write outside the configured output root or overwrite prior runs without policy.
- Do not introduce unverified ranking, Sharpe, win-rate, expected-return, or “best configuration” claims while v2.1 empirical evidence remains blocked.
- Keep report language as research support, not buy/sell execution advice.

## Suggested Requirement Categories

- Daily scan entry point
- Watchlist intake and validation
- Data/run plan and cache resolution
- Data health gate and failure policy
- Scan execution and signal contract integration
- Symbol buckets and reason codes
- Artifact schema and safe writes
- Markdown report rendering
- CLI/tool behavior and exit semantics
- Testing and verification
- Explicit anti-features / out-of-scope constraints

## Confidence

**High** for brownfield architecture direction and MVP scope.  
**Medium** for refresh/fallback details and exchange-calendar semantics; keep those explicit and bounded during planning.
