# Architecture Research: v2.2 Daily Scan Report Loop

## Summary

v2.2 should add a daily scan orchestration layer on top of existing watchlist, data-health, `TradingSignal`, and composite strategy infrastructure.

Recommended one-way dependency direction:

```text
src.data/*       -> data contracts, watchlist parsing, local health gate
src.strategies/* -> signal generation contracts and strategy logic
src.scan/*       -> daily scan orchestration, run artifacts, report payloads
src.tools/*      -> agent/MCP wrappers around scan pipeline
scripts/cli      -> one-command entrypoint
backtest/*       -> unchanged
```

The new `src.scan` layer can import data and strategy modules. Data, strategies, backtest, tools, and CLI should not import scan internals unless they are wrappers.

## Proposed Components

```text
agent/src/scan/
├── config.py          # DailyScanConfig
├── models.py          # DailyScanRun, SymbolScanResult, manifest models
├── data_loader.py     # local canonical OHLCV loading
├── strategy_factory.py# composite strategy construction
├── pipeline.py        # workflow orchestration
├── artifacts.py       # safe artifact writing
└── markdown.py        # deterministic renderer
```

## Data Flow

```text
CLI / MCP / tool
  -> DailyScanConfig
  -> WatchlistReader
  -> optional data refresh/sync
  -> check_watchlist_data
  -> if FAIL: blocked artifacts/report, exit nonzero
  -> ScanDataLoader per eligible symbol
  -> CompositeTrendStrategy.analyze(df)
  -> TradingSignal.to_dict()
  -> scan.json / data_health.json / manifest.json
  -> report.md
```

## Gate Policy

- `PASS`: run full scan.
- `WARN`: run scan, annotate report prominently; optionally fail in strict mode.
- `FAIL`: stop before strategy execution by default; write health-only blocked artifacts/report.

## Build Order

1. Scan skeleton + data-health artifacts.
2. Local scan data loader + symbol scan contracts.
3. Composite strategy scan integration.
4. Markdown renderer and daily report artifacts.
5. Tool registry, MCP wrapper, and CLI alias.
6. Optional controlled data refresh stage.

## Risks

- Extending legacy `WatchlistAnalyzer` could cause semantic drift from `TradingSignal`.
- Refresh inside analysis could hide data quality/provenance issues.
- Output path handling must match v2.1 safety expectations.
- Report language must avoid implying execution advice.
- Daily scan scope can grow too broad if refresh, report, CLI, MCP, calendar, and history are all bundled in one phase.
