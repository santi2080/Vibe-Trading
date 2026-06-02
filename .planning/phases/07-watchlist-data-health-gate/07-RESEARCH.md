# Phase 07: Watchlist Local Data Health Gate - Research

**Researched:** 2026-06-02
**Status:** Ready for planning
**Requirement:** REQ-001

## Research Question

What do we need to know to plan `REQ-001: Watchlist 本地数据完整性门禁` well?

## Key Finding

The core REQ-001 domain logic already exists. This phase should not reimplement the checker. It should productize and integrate the existing checker into agent/MCP/backtest-facing workflows, then prove the gate blocks unsafe downstream work.

Primary existing artifacts:

- `agent/src/data/watchlist_data_health.py`
- `scripts/check_watchlist_data.py`
- `agent/tests/test_watchlist_data_health.py`

## Existing Implementation Coverage

`agent/src/data/watchlist_data_health.py` already provides:

- `WatchlistDataHealthReport`
- `TimeframeDataHealth`
- `check_watchlist_data(...)`
- `check_timeframe_data(...)`
- `format_report_table(...)`
- `resolve_market_dir(...)`
- `resolve_cache_file(...)`
- `normalize_timeframe(...)`
- `required_and_declared_timeframes(...)`
- `validate_ohlcv(...)`
- `calculate_max_gap_hours(...)`

Current behavior already covers most REQ-001 acceptance criteria:

| Acceptance criterion | Current status | Evidence |
|---|---|---|
| Read watchlist CSV and identify symbol/name/market/timeframes | Existing | Uses `WatchlistReader.load_raw()` |
| Check per-symbol/per-timeframe local data | Existing | `check_watchlist_data()` loops symbols/timeframes |
| Report file existence, start/end, rows, recency, max gap | Existing | `TimeframeDataHealth` fields |
| Block `1d` / `1h` failures | Existing | `BLOCKING_TIMEFRAMES = ("1d", "1h")` |
| Staleness windows | Existing with override | `STALE_AFTER`; `MARKET_TIMEFRAME_STALE_AFTER` |
| Human table and JSON | Existing | `format_report_table()` and `to_dict()` |
| JSON gate fields and item details | Existing | `WatchlistDataHealthReport.to_dict()` |

## Important Existing Decision

`us_futures:1h` has a 24-hour staleness override. This differs from the default `1h > 6 hours` acceptance criterion but is documented in `.planning/todos/pending/watchlist-local-data-health-check.md` as a prior follow-up decision because yfinance intraday updates make strict 6h too brittle for US futures pre-market checks.

Planning should preserve this override and ensure it remains visible in JSON via `rules.market_overrides`.

## Closest Code Analogs

### Domain checker and CLI

- `agent/src/data/watchlist_data_health.py` — source of truth for data health logic.
- `scripts/check_watchlist_data.py` — CLI wrapper with `--format table|json|both`, `--json-output`, `--now`, and return code behavior.
- `agent/tests/test_watchlist_data_health.py` — deterministic tests with `tmp_path` and fixed `now`.

### Agent tool pattern

- `agent/src/tools/watchlist_tool.py`
  - `_resolve_watchlist_path(...)` enforces path safety under `watchlist/`.
  - `ListWatchlistTool`, `AnalyzeSecurityTool`, `AnalyzeWatchlistTool` return JSON strings.
- `agent/tests/test_strategy_watchlist_tools.py`
  - verifies registry discovery and JSON output behavior.

### MCP wrapper pattern

- `agent/mcp_server.py`
  - `list_watchlist(...)`
  - `analyze_security(...)`
  - `analyze_watchlist(...)`
  - wrappers call `_get_registry().execute(tool_name, params)`.

### Backtest/analyze data loading patterns

- `agent/src/analysis/watchlist_analyzer.py`
  - batch analysis uses local files first, then `DataClient` fallback.
- `scripts/backtest_trend_indicators.py`
  - loads `data/{market_dir}/{symbol}/{timeframe}.parquet`.
- `scripts/backtest_signal_execution.py`
  - direct local data loading for backtest script.
- `scripts/backtest_mtes_v2v3.py`
  - fixed US futures local data loading.

## Recommended Plan Slices

### Slice 1: Tool and MCP exposure

Goal: make the existing checker available to agents and MCP clients.

Likely changes:

- Add `CheckWatchlistDataTool` in `agent/src/tools/watchlist_tool.py` or a new `agent/src/tools/watchlist_data_health_tool.py`.
- Reuse `_resolve_watchlist_path(...)` for path safety.
- Call `check_watchlist_data(...)` and return JSON using existing tool conventions.
- Add MCP wrapper `check_watchlist_data(...)` near existing watchlist tools in `agent/mcp_server.py`.
- Extend `agent/tests/test_strategy_watchlist_tools.py` for registry, path safety, and JSON gate fields.

### Slice 2: Gate integration before downstream analysis/backtest

Goal: prove the gate blocks at least one meaningful downstream path when `report.can_backtest` is false.

Possible target paths:

- `AnalyzeWatchlistTool.execute(...)` before `WatchlistAnalyzer.analyze_all(...)`.
- Or `scripts/backtest_trend_indicators.py` before running watchlist/all-symbol backtests if a watchlist path is involved.

Recommended first integration:

- Add optional gate behavior to `AnalyzeWatchlistTool` because it is user-facing, watchlist-scoped, and already uses JSON output.
- Default should be safe for REQ-001: when analyzing a watchlist, run `check_watchlist_data()` first and return a JSON error/gate payload if `can_backtest` is false.
- If existing tests rely on current behavior with unhealthy real local data, use a parameter such as `enforce_data_gate` carefully. However, REQ-001 says the gate should run before allowing strategy backtest, so avoid silently bypassing in the protected path.

### Slice 3: Documentation and verification alignment

Goal: make the behavior discoverable and preserve acceptance evidence.

Likely changes:

- Update or close `.planning/todos/pending/watchlist-local-data-health-check.md` if execution completes later.
- Add verification commands for:
  - `agent/tests/test_watchlist_data_health.py`
  - `agent/tests/test_strategy_watchlist_tools.py`
  - any script/tool integration tests added.

## Risks and Edge Cases

1. Real repository watchlists may fail the gate depending on local data freshness.
   - Tests should use temporary watchlists/data fixtures, not rely solely on real local files.

2. Tool path safety must be preserved.
   - Reuse `_resolve_watchlist_path(...)` and test path escape rejection.

3. Data path conventions are duplicated in several modules.
   - Keep `watchlist_data_health.py` as source of truth for this phase to avoid drift.

4. Backtest scripts do not all accept a watchlist path.
   - Avoid trying to retrofit every script in one phase; choose one meaningful user-facing path first.

5. Current checker returns `WARN` but `can_backtest=True` when only auxiliary timeframes fail.
   - This matches the pending todo and should remain.

6. `us_futures:1h` override could appear to contradict REQ-001.
   - Preserve it but document it in plan acceptance criteria and JSON checks.

## Validation Architecture

A good plan should include these verification dimensions:

1. Domain tests still pass:
   - `agent/tests/test_watchlist_data_health.py`
2. Tool registry tests pass and cover new tool:
   - `agent/tests/test_strategy_watchlist_tools.py`
3. MCP wrapper can be statically verified or covered through registry execution if MCP direct tests are not available.
4. Gate-block behavior has a deterministic test using temporary watchlist/data where required `1h` is missing or stale.
5. CLI behavior remains unchanged:
   - passing gate exits 0
   - blocking gate exits 1
   - missing watchlist exits 2

## Suggested Plan Count

2 plans should be enough:

1. `07-01-PLAN.md` — expose data health checker through agent tool + MCP wrapper.
2. `07-02-PLAN.md` — integrate gate into watchlist analysis/backtest path and verify blocking behavior.

## Planning Guidance

The planner should treat this as an integration phase over existing code, not a greenfield implementation. Acceptance criteria should explicitly include:

- `REQ-001` referenced in plan frontmatter.
- Tool JSON includes `gate.status`, `gate.can_backtest`, `gate.blocking_failures`, `gate.warnings`, and `items`.
- Path escape attempts return JSON `status=error`.
- Required timeframe failure blocks the protected downstream path.
- Auxiliary timeframe warnings do not block.

## RESEARCH COMPLETE
