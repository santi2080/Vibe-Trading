# Stack Research: v2.2 Daily Scan Report Loop

**Scope:** Brownfield stack additions for a watchlist-driven daily scan data pipeline, freshness/health/fallback handling, and structured artifacts that can feed Markdown reporting.

## Summary

The existing Python stack is sufficient for v2.2. The milestone should add a deterministic scan orchestration layer rather than new workflow infrastructure.

Strong existing foundations:
- `agent/src/data/watchlist.py` — CSV watchlist parsing and metadata
- `agent/src/data/watchlist_data_health.py` — local Parquet freshness/health gate
- `agent/src/tools/watchlist_tool.py` — path-safe JSON-oriented watchlist tools
- `agent/src/strategies/composite/base.py` — `TradingSignal` contract
- `agent/src/strategies/composite/trend_composite.py` — `CompositeTrendStrategy`
- Markdown helpers in `agent/src/analysis/report_generator.py` and `agent/backtest/reporting/composite_report.py`

## Recommended Additions

### Explicit Parquet engine

Add `pyarrow>=15.0.0` explicitly if not already declared. Existing code relies on `pandas.read_parquet()` / `DataFrame.to_parquet()`, but the Parquet engine should be a declared dependency for daily-scan reliability.

### New scan package

Create a focused orchestration package such as:

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

## Integration Points

- CLI/script entry point should call `DailyScanPipeline`, not embed logic.
- MCP/tool wrappers should be thin and JSON-first.
- Markdown rendering should consume structured scan artifacts, not live runtime objects.
- Strategy scan should consume `TradingSignal` / `CompositeTrendStrategy` semantics rather than expanding legacy EMA/ADX/RSI analyzer logic.

## What Not To Add

Do not add for v2.2:
- Airflow / Prefect / Dagster
- Celery / Redis / RQ
- New database
- Polars migration
- New market data vendors
- Dashboard/report publishing stack
- Exchange calendar library unless false stale alerts become blocking

## Risks

- Parquet runtime failure if `pyarrow` is missing.
- Cache convention divergence between project-local `data/` and external cache roots.
- Legacy analyzer producing non-canonical signals.
- Data-provider fallback hiding provenance.
- Overbuilding scheduling/dashboard automation before one-command local workflow stabilizes.
