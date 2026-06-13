# Phase 20: Session-Aware Freshness Detection — Summary

**Status:** PLANNED
**Date:** 2026-06-12
**Depends on:** Phase 19 (Holiday Calendar Integration)

## Phase 20 Overview

Replace simple staleness checks in `data_refresh.py` with session-aware freshness detection. When a market is closed (after hours or holiday), data from the last trading session should not be marked stale — because there was no opportunity to update it.

## Success Criteria

1. `stale_after_for()` returns session-adjusted thresholds
2. `get_session_aware_report()` returns enriched status: `fresh` / `stale` / `session_closed` / `holiday`
3. Pre-market / regular-hours / after-hours distinction works
4. Non-trading-hours data not marked stale for fixed-hour markets
5. Continuous markets (US futures) retain original threshold behavior
6. Session-aware freshness report available in scan results

## Task Breakdown

| Task | Description | Files |
|------|-------------|-------|
| 20-01 | Extend `stale_after_for()` with session awareness | `data_refresh.py` |
| 20-02 | Add `_updated_on_date()` helper | `data_refresh.py` |
| 20-03 | Add `FreshnessReport` dataclass + `get_session_aware_report()` | `freshness.py` |
| 20-04 | Focused tests for session-aware freshness | `test_freshness.py` (new) |
| 20-05 | Update `__init__.py` exports | `__init__.py` |
| 20-06 | Update ROADMAP progress | `ROADMAP.md` |

## Key Design Decisions

- **Session-adjusted thresholds**: When market is closed with no update today → threshold × 1.5; when holiday → threshold × 2
- **Continuous markets (US futures)**: No session adjustment — data can always arrive
- **`FreshnessReport` dataclass**: Rich return type with status, age, session_status, threshold, reason
- **Leverages Phase 18-19**: `get_session_status()`, `MarketSessionStatus`, `is_trading_day()`, `MARKET_TZ`

## Verification

```bash
pytest agent/src/data/test_freshness.py -x -q
pytest agent/src/data/test_trading_sessions.py -x -q
pytest agent/src/data/test_holiday_calendar.py -x -q
```

All must pass before Phase 20 closure.
