---
gsd_state_version: 1.0
milestone: v2.4
milestone_name: exchange-calendar-awareness
status: planning
last_updated: "2026-06-11T00:00:00Z"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State

## Current Focus

v2.4 exchange-calendar-awareness: **PLANNING** — Defining requirements.

## Milestone Summary

v2.3 shipped (2026-06-11): Remote refresh scan loop with `--refresh` flag.

**Goal:** Make data freshness detection aware of exchange trading sessions.

**Target features:**
- Exchange trading session definitions (A-shares, US, HK, futures)
- Holiday calendar awareness
- Session-aware freshness detection (pre-market, regular, after-hours)
- Smart refresh that respects trading hours

## Requirements

Requirements definition in progress.

## Next Steps

- Define scoped requirements (REQ-IDs)
- Create phased roadmap
- Start Phase 01 planning

## Deferred (per Scope Guardrails)

- Daily delta against prior scans
- Empirically validated ranking
- Dashboard or web UI
- Notifications or scheduling
- Live/paper trading execution
- Trading advice or buy/sell execution language
