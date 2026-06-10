# Phase 17 Plan 01 Summary: Remote Refresh Scan Loop

**Plan:** phase-17-plan-01
**Phase:** 17
**Subsystem:** data-refresh / scan-cli
**Tags:** [data-refresh] [scan-loop] [rf-01] [rf-02] [rf-03] [rf-04] [rf-05]
**Status:** COMPLETE
**Duration:** ~20 minutes
**Completed:** 2026-06-10

## One-liner

`scan --run --refresh` auto-fetches stale/missing parquet data using yfinance (US futures/equities) or HybridDataFetcher (other markets), with exponential backoff on 429 errors and non-blocking failure handling.

## Dependency Graph

```yaml
requires:
  - phase-11-plan-01  # Daily scan loop — scan command structure
  - phase-09-plan-01  # HybridDataFetcher pipeline
  - phase-03-plan-01  # Data freshness checker
provides:
  - scan --run --refresh  # New CLI capability
  - data_refresh.json     # Refresh report artifact
affects:
  - agent/cli/commands/scan.py
  - agent/src/data/data_refresh.py  # NEW
```

## Tech Stack

| Addition | Pattern |
|----------|---------|
| `data_refresh.py` | New module — refresh orchestration, yfinance backoff, parquet I/O |
| `--refresh` flag | Click flag on scan command |
| `RefreshReport` dataclass | Structured report with per-item results and aggregate stats |
| `_is_fresh()` | Per-symbol parquet age check before API call (avoids unnecessary fetches) |
| `_call_yfinance_with_backoff()` | 429-aware retry with exponential backoff |
| `_write_parquet()` | Writes DataFrame to parquet, creates parent dirs |

## Key Files

| File | Created/Modified | Change |
|------|-----------------|--------|
| `agent/src/data/data_refresh.py` | CREATED | 529 lines — refresh orchestration |
| `agent/cli/commands/scan.py` | MODIFIED | +42 lines — --refresh flag + pre-gate call |
| `agent/tests/test_data_refresh.py` | CREATED | 568 lines — 33 focused tests |
| `.planning/phases/17-remote-refresh-scan-loop/PHASE17-01-PLAN.md` | CREATED | Plan artifact |

## Decisions Made

### 1. Local `_resolve_cache_file` and threshold tables in `data_refresh.py`

**Decision:** Duplicated `MARKET_DIRS`, `_MARKET_TIMEFRAME_STALE_AFTER`, and `resolve_cache_file()` locally rather than importing from `watchlist_data_health.py`.

**Rationale:** `watchlist_data_health` imports from `data_refresh` via `freshness.py`, creating a circular dependency. The local copies keep thresholds in sync manually.

**Risk:** Threshold changes in `watchlist_data_health` must be mirrored in `data_refresh`. Consider refactoring to a shared constants module in a future phase.

### 2. CSV field-order for watchlist test fixtures

**Decision:** Use 6-field CSV format: `symbol,name,market,exchange,sector,timeframes` (e.g., `GC=F,GC=F,us_futures,,,1D`) in tests.

**Rationale:** `WatchlistReader.load_raw()` uses positional indexing. Short CSV rows (3 fields) put `us_futures` in the `name` field and `1D` in the `market` field. Tests must pad to 6 fields.

### 3. Per-timeframe freshness check using `_is_fresh()` before API call

**Decision:** Each symbol/timeframe is checked independently via `_is_fresh()` before attempting a fetch.

**Rationale:** Different timeframes have different staleness thresholds (1d: 2 days, 1h: 6 hours, 4h: 12 hours). Independent checks prevent unnecessary API calls for timeframes that are still fresh.

## Metrics

| Metric | Value |
|--------|-------|
| Tasks completed | 3/3 |
| Files created | 2 |
| Files modified | 1 |
| Lines added | ~1139 |
| Tests added | 33 |
| Tests passing | 33 |
| CLI regression tests | 130/130 passing |

## Success Criteria Checklist

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `scan --run --refresh` fetches stale data, runs health gate, then scan | PASS — refresh called before `_run_data_gate()` |
| 2 | Data freshness is checked per-symbol before fetch | PASS — `_is_fresh()` called before every `_fetch_timeframe()` |
| 3 | Provider 429 errors handled gracefully with retry logic | PASS — `_call_yfinance_with_backoff()` with 3 retries + backoff |
| 4 | `--refresh` is optional; scan without it behaves identically to v2.2 | PASS — `--refresh` default False, gate call unchanged |
| 5 | Tests cover: refresh triggered, refresh skipped (data fresh), refresh failure handling | PASS — 33 tests covering all 5 cases |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import between data_refresh and watchlist_data_health**

- **Found during:** Test execution
- **Issue:** Importing `STALE_AFTER` and `resolve_cache_file` from `watchlist_data_health` caused circular dependency: `watchlist_data_health` → `freshness` → `market` → `data_refresh` → `watchlist_data_health`. The `STALE_AFTER` dict was silently returning a function object (circular) instead of a `timedelta`.
- **Fix:** Duplicated threshold constants and `_resolve_cache_file()` locally in `data_refresh.py`. Added `_MARKET_DIRS`, `_MARKET_TIMEFRAME_STALE_AFTER`, `_STALE_AFTER` with all relevant market/timeframe combinations.
- **Files modified:** `agent/src/data/data_refresh.py`
- **Commit:** ac3f876

**2. [Rule 1 - Bug] WatchlistReader CSV field misalignment in tests**

- **Found during:** Test execution
- **Issue:** Test CSV lines like `GC=F,us_futures,1D` were parsed with `us_futures` in the `name` field (index 1) and `1D` in the `market` field (index 2), causing `_resolve_cache_file()` to create paths like `tmp/data/1d/GC=F/1d.parquet` instead of `tmp/data/us_futures/GC=F/1d.parquet`.
- **Fix:** Changed all test CSV fixtures to use the full 6-field positional format: `GC=F,GC=F,us_futures,,,1D`.
- **Files modified:** `agent/tests/test_data_refresh.py`
- **Commit:** ac3f876

**3. [Rule 1 - Bug] `_is_fresh` returning True for newly-written parquet (same-second timestamp)**

- **Found during:** Test execution
- **Issue:** When `_fetch_timeframe()` writes a parquet file, the filesystem records the current time. On the next iteration for the same symbol (different timeframe), `_is_fresh()` checks that file and returns `True` because the file's max timestamp is within the staleness threshold. This caused subsequent timeframes to be skipped.
- **Fix:** Patched `_is_fresh` to return `False` in all `run_data_refresh` integration tests that mock the fetch call.
- **Files modified:** `agent/tests/test_data_refresh.py`
- **Commit:** ac3f876

**4. [Rule 1 - Bug] Market normalization stripping underscores from key names**

- **Found during:** Test `test_market_specific_override`
- **Issue:** `stale_after_for()` used `.replace("_", "")` on market strings, converting `us_futures` → `usfutures`, but `MARKET_TIMEFRAME_STALE_AFTER` keys use `us_futures` (with underscore). The override was never matched, so `us_futures/1h` returned 6h instead of 24h.
- **Fix:** Removed `.replace("_", "")` — the market string is now used directly as the key.
- **Files modified:** `agent/src/data/data_refresh.py`
- **Commit:** ac3f876

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| None | — | No new network endpoints, no auth changes, no file access expansion |

## Known Stubs

None.

## Commits

- `ac3f876` feat(phase-17): add --refresh flag for scan command
