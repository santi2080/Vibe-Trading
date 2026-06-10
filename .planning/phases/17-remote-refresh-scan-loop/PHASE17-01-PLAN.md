# Phase 17: Remote Refresh Scan Loop

## Goal

用户可以用一条命令自动刷新过期数据并运行 scan，无需手动分步执行。

## Scope

### Included
- `--refresh` flag on scan command to auto-fetch missing/stale data before scan
- Data refresh uses HybridDataFetcher with yfinance as primary source
- Incremental refresh: only fetches missing/stale data, not full history
- Integration with existing data_health gate (refresh runs before gate if enabled)
- Rate limiting and retry backoff to avoid provider throttling

### Deferred
- Exchange calendar awareness (Phase future)
- Scheduling/cron (Phase future)
- Delta report (comparing to prior scan)

## Requirements

- **RF-01**: `scan --run --refresh` auto-fetches stale/missing data before health gate
- **RF-02**: Refresh uses appropriate source per market (yfinance for US futures, existing loaders for others)
- **RF-03**: Refresh respects rate limits (429 handling, backoff)
- **RF-04**: Refresh writes to same parquet paths used by scan
- **RF-05**: Refresh failures are non-blocking (gate still runs with available data)

## Success Criteria

1. `scan --run --refresh` fetches stale data, runs health gate, then scan
2. Data freshness is checked per-symbol before fetch (avoid unnecessary API calls)
3. Provider 429 errors are handled gracefully with retry logic
4. `--refresh` is optional; scan without it behaves identically to v2.2
5. Tests cover: refresh triggered, refresh skipped (data fresh), refresh failure handling

## Technical Notes

- HybridDataFetcher already exists and handles source routing
- yfinance has 2-year limit on 1H data, 1-year on 1D
- Need to check existing data age before fetching to avoid unnecessary API calls
- Write new parquet files in-place (same path as scan reads)

## Files to Create/Modify

- `agent/cli/commands/scan.py` — add `--refresh` flag
- `agent/src/data/data_refresh.py` — new module for refresh logic
- `agent/tests/test_data_refresh.py` — tests
