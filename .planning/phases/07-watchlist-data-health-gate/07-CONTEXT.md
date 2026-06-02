# Phase 07: Watchlist Local Data Health Gate - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning
**Source:** REQ-001 from `.planning/REQUIREMENTS.md` plus existing implementation research

<domain>

## Phase Boundary

This phase closes the deferred `REQ-001: Watchlist 本地数据完整性门禁` by productizing the existing watchlist data-health checker and wiring it into user-facing agent/MCP/backtest flows.

It does **not** rebuild the health checker from scratch. The repository already contains a near-complete domain implementation in:

- `agent/src/data/watchlist_data_health.py`
- `scripts/check_watchlist_data.py`
- `agent/tests/test_watchlist_data_health.py`

The phase should focus on integration, guard behavior, registry/MCP exposure, and tests proving the gate blocks downstream analysis/backtests when required local data is unhealthy.

</domain>

<decisions>

## Locked Decisions

### D-01: Reuse existing domain checker
- Use `agent/src/data/watchlist_data_health.py` as the source of truth for watchlist data-health logic.
- Do not create a parallel checker with duplicate path, timeframe, or staleness logic.

### D-02: Standard local data source
- The source of truth for this gate is the standard local parquet layout: `data/{market}/{symbol}/{timeframe}.parquet`.
- Hash/cache directories such as `data/cache/vibe` may be diagnostic only and should not replace the standard source path.

### D-03: Required blocking timeframes
- `1d` and `1h` are blocking timeframes by default.
- Required timeframe failures must block backtesting/analysis when the entry point claims to be gate-protected.

### D-04: Staleness windows and market override
- Default windows remain `1d > 2 days`, `1h > 6 hours`, `4h > 12 hours`.
- Existing `us_futures:1h = 24h` override is accepted because it is already implemented and documented in pending todo notes as a prior decision.
- JSON output must expose overrides through `rules.market_overrides` so consumers can see the difference from the default.

### D-05: Output contracts
- User-facing output must support human-readable table and machine-readable JSON.
- Tool/MCP output should return JSON strings using the existing `BaseTool` convention.
- JSON must include: overall gate status, `can_backtest`, blocking failure count, warning count, and per-symbol/per-timeframe details.

### D-06: Path safety
- Any agent/tool/MCP entry point accepting a watchlist path must reuse the watchlist path safety pattern from `agent/src/tools/watchlist_tool.py` so paths cannot escape the `watchlist/` directory.

### D-07: Integration target
- Add user-facing tool/MCP exposure for data-health checks.
- Add at least one downstream gate integration path where backtest/watchlist analysis refuses to proceed when `report.can_backtest` is false.

### D-08: Testing style
- Follow existing pytest style with deterministic `tmp_path` fixtures and fixed `now` values.
- Extend existing tests instead of replacing them.

</decisions>

<canonical_refs>

## Canonical References

Downstream agents MUST read these before planning or implementing.

### Requirement source
- `.planning/REQUIREMENTS.md` — defines REQ-001 acceptance criteria.
- `.planning/todos/pending/watchlist-local-data-health-check.md` — contains prior implementation notes and the `us_futures:1h = 24h` decision.

### Existing domain implementation
- `agent/src/data/watchlist_data_health.py` — domain checker, data structures, gate rules, JSON/table formatting.
- `scripts/check_watchlist_data.py` — CLI wrapper around the domain checker.
- `agent/tests/test_watchlist_data_health.py` — current domain and CLI tests.

### Watchlist and tool patterns
- `agent/src/data/watchlist.py` — `WatchlistReader` and raw watchlist CSV parsing.
- `agent/src/tools/watchlist_tool.py` — existing watchlist tools and path safety helper.
- `agent/tests/test_strategy_watchlist_tools.py` — registry/tool tests.
- `agent/mcp_server.py` — MCP wrapper pattern for watchlist tools.

### Backtest/analyze patterns
- `agent/src/analysis/watchlist_analyzer.py` — watchlist analysis data loading and batch analysis flow.
- `scripts/backtest_trend_indicators.py` — local data loading for trend-indicator backtests.
- `scripts/backtest_signal_execution.py` — signal execution backtest script.
- `scripts/backtest_mtes_v2v3.py` — MTES v2/v3 backtest script.

</canonical_refs>

<specifics>

## Specific Ideas

- Preferred tool name: `check_watchlist_data` or `check_watchlist_data_health`.
- Preferred location: extend `agent/src/tools/watchlist_tool.py` unless file size becomes a problem; otherwise create `agent/src/tools/watchlist_data_health_tool.py`.
- MCP wrapper should sit near existing `list_watchlist` / `analyze_watchlist` functions in `agent/mcp_server.py`.
- The gate integration may be implemented as a reusable helper (for example, a function that checks and returns a JSON error payload) before wiring it into one or more scripts/tools.
- Avoid exposing arbitrary JSON-output file writing through agent tools unless explicitly needed; keep tools readonly by default.

</specifics>

<deferred>

## Deferred Ideas

- Exchange-calendar-aware staleness logic is deferred; current rule remains fixed-window.
- TqSdk credential setup for CN futures 1h updates is deferred.
- Large refactor to unify all market directory maps is deferred unless required to avoid duplicate gate behavior.
- Broad migration of every historical backtest script to use the gate can be incremental; this phase must prove at least one meaningful guarded path.

</deferred>

---

*Phase: 07-watchlist-data-health-gate*
*Context gathered: 2026-06-01 via REQ-001 planning kickoff*
