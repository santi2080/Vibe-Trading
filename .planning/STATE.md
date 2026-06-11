---
gsd_state_version: 1.0
milestone: v2.4
milestone_name: exchange-calendar-awareness
status: in_progress
last_updated: "2026-06-11T00:00:00Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 4
  completed_plans: 1
  percent: 25
---

# State

## Current Focus

v2.4 exchange-calendar-awareness: **IN PROGRESS** — Phase 18 completed; Phase 19 holiday calendar integration is next.

## Milestone Summary

v2.3 shipped (2026-06-11): Remote refresh scan loop with `--refresh` flag.

**Goal:** Make data freshness detection aware of exchange trading sessions.

**Target features:**
- Exchange trading session definitions (A-shares, US, HK, futures) — ✅ Phase 18 complete
- Holiday calendar awareness — next
- Session-aware freshness detection (pre-market, regular, after-hours)
- Smart refresh that respects trading hours

## Completed

- Phase 18: Exchange Session Definitions
  - Added `MarketSessionStatus`, `MARKET_TZ`, `get_session_status()`, and `is_session_time()`.
  - Extended `DataFreshnessChecker.is_fresh()` and `get_freshness_status()` with optional `session_context`.
  - Added focused tests for A-share, US, HK, China futures, US futures cross-midnight, and session-aware freshness.

## Next Steps

- Plan/execute Phase 19: Holiday Calendar Integration (CAL-02)
- Keep Phase 20/21 dependent on Phase 19 unless roadmap scope changes

## Deferred (per Scope Guardrails)

- Daily delta against prior scans
- Empirically validated ranking
- Dashboard or web UI
- Notifications or scheduling
- Live/paper trading execution
- Trading advice or buy/sell execution language
