# Roadmap: Vibe-Trading

## Milestones

- ✅ **v2.0** — composite-strategy-signal-layer (shipped 2026-06-06)
- ✅ **v2.1** — composite-strategy-backtest (shipped 2026-06-07; empirical evidence blocked)
- 🌱 **v2.2** — daily-scan-report-loop

## Phases

<details>
<summary>✅ v2.0 (Phases 01-08) — SHIPPED 2026-06-06</summary>

- [x] Phase 01: Major Trend Evaluation System (4/4 plans) — completed 2026-06-01
- [x] Phase 02: Trend Indicator Backtest (1/1 plan) — completed 2026-06-01
- [x] Phase 03: SuperTrend Enhancement Strategy (5/5 plans) — completed 2026-06-02
- [x] Phase 04: Signal Execution System (5/5 plans) — completed 2026-06-03
- [x] Phase 05: MTES Refactor (1/1 plan) — completed 2026-06-03
- [x] Phase 06: MTES v3 Layered System (4/4 plans) — completed 2026-06-04
- [x] Phase 07: Watchlist Data Health Gate (2/2 plans) — completed 2026-06-05
- [x] Phase 08: Composite Strategy Signal Layer (1/1 plan) — completed 2026-06-06

</details>

<details>
<summary>✅ v2.1 (Phases 09-10) — SHIPPED 2026-06-07</summary>

- [x] Phase 09: Composite Strategy Backtest (4/4 plans) — completed 2026-06-06
  - CompositeBacktestSignalEngine, PositionManager, YAML config, metrics & reporting infrastructure
- [x] Phase 10: Empirical Composite Backtest Evidence Closure (5/5 plans) — completed 2026-06-07
  - Data readiness checks, 1D/4H evidence; overall_status: blocked

**Known gaps:** 8/12 requirements blocked (no verified 2024-2026 empirical metrics); 4/12 verified (BKST-01/02/03, RPT-03).  
**See:** `.planning/milestones/v2.1-ROADMAP.md`, `.planning/milestones/v2.1-REQUIREMENTS.md`

</details>

### 🌱 v2.2: Daily Scan Report Loop

- [ ] Phase 11: Daily Scan Foundation & Run Plan (0/0 plans) — not started
- [ ] Phase 12: Data Health Gated Scan Control (0/0 plans) — not started
- [ ] Phase 13: Composite Signal Scan Buckets (0/0 plans) — not started
- [ ] Phase 14: Deterministic Artifacts & Markdown Report (0/0 plans) — not started
- [ ] Phase 15: Daily Scan Verification Closure (0/0 plans) — not started

**Goal:** Productize the daily scan workflow with a reliable local-data-first pipeline that can support one-command watchlist scanning and Markdown reporting.

## Phase Details

### Phase 11: Daily Scan Foundation & Run Plan

**Goal:** User can start a local-data-first daily scan and receive validated run intent before analysis begins.  
**Depends on:** Phase 10 / v2.1 shipped foundations  
**Requirements:** STK-01, CLI-01, CLI-02, WLS-01, WLS-02

**Success Criteria:**
1. User can invoke one daily scan command with explicit watchlist, data directory, output directory, timestamp, and JSON or human output mode.
2. User is told early when the watchlist path is missing or unsafe, required columns are absent, the list is empty, duplicate symbols exist, or market/timeframe values are unsupported.
3. User can inspect a normalized scan plan that lists each symbol, market, required timeframes, cache paths, and intended output paths before strategy results are produced.
4. The scan uses only local data inputs in v2.2; no remote provider fetch is triggered by the default daily scan command.
5. Parquet read/write support is dependable because the project explicitly declares the required Parquet engine dependency.

**Plans:** TBD

### Phase 12: Data Health Gated Scan Control

**Goal:** User can trust that data readiness blocks or caveats the scan before strategy work.  
**Depends on:** Phase 11  
**Requirements:** GATE-01, GATE-02

**Success Criteria:**
1. Every daily scan run executes the existing data-health gate before any CompositeTrendStrategy analysis.
2. A data-health `FAIL` produces blocked artifacts and a blocked report with no strategy candidates.
3. A data-health `WARN` run can continue, but the report and artifacts clearly expose the caveats.
4. User can distinguish `PASS`, `WARN`, and `FAIL` scan outcomes without reading logs.

**Plans:** TBD

### Phase 13: Composite Signal Scan Buckets

**Goal:** User can see every watchlist symbol classified through CompositeTrendStrategy / TradingSignal semantics.  
**Depends on:** Phase 12  
**Requirements:** SIG-01, SIG-02

**Success Criteria:**
1. Eligible symbols are scanned through `CompositeTrendStrategy` and serialized via `TradingSignal` semantics, not legacy analyzer semantics.
2. Every input watchlist symbol appears in exactly one final classification: Actionable, Watch, Risk/Excluded, Skipped, or Failed.
3. User can see why any symbol was skipped, failed, or excluded from actionable candidates.
4. Actionable candidates are based on validated signal readiness semantics rather than unverified ranking or historical performance claims.

**Plans:** TBD

### Phase 14: Deterministic Artifacts & Markdown Report

**Goal:** User gets stable machine-readable artifacts and a human-readable Markdown report without unverified claims.  
**Depends on:** Phase 13  
**Requirements:** ART-01, RPT-01, RPT-02

**Success Criteria:**
1. Each scan run writes `manifest.json`, `data_health.json`, `scan_results.json`, and `report.md` into a safe deterministic run directory.
2. User can open `report.md` and see data health, candidates, watch symbols, risk/excluded symbols, skipped/failed symbols, caveats, and links to artifacts.
3. Markdown report counts and sections are rendered from the JSON artifacts rather than separate ad-hoc report state.
4. The report avoids unverified ranking, performance metrics, “best configuration” claims, and trading execution advice.

**Plans:** TBD

### Phase 15: Daily Scan Verification Closure

**Goal:** User can verify the daily scan loop with tests covering gate, artifacts, report, safety, and CLI behavior.  
**Depends on:** Phase 14  
**Requirements:** TST-01

**Success Criteria:**
1. User can run focused tests showing data-health `FAIL` blocks strategy analysis and data-health `WARN` continues with visible caveats.
2. User can run focused tests showing each symbol is assigned to one bucket or reason code.
3. User can run focused tests showing artifact schemas and Markdown/JSON counts stay consistent.
4. User can run focused tests showing unsafe paths are rejected and CLI/tool exit semantics are stable for success, warning, blocked, and failure cases.

**Plans:** TBD

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|----------|
| 01-08 | v2.0 | 23/23 | Complete | 2026-06-06 |
| 09 | v2.1 | 4/4 | Complete | 2026-06-06 |
| 10 | v2.1 | 5/5 | Complete (blocked evidence) | 2026-06-07 |
| 11 | v2.2 | 0/0 | Not started | — |
| 12 | v2.2 | 0/0 | Not started | — |
| 13 | v2.2 | 0/0 | Not started | — |
| 14 | v2.2 | 0/0 | Not started | — |
| 15 | v2.2 | 0/0 | Not started | — |

## Coverage

| Requirement | Phase |
|-------------|-------|
| STK-01 | Phase 11 |
| CLI-01 | Phase 11 |
| CLI-02 | Phase 11 |
| WLS-01 | Phase 11 |
| WLS-02 | Phase 11 |
| GATE-01 | Phase 12 |
| GATE-02 | Phase 12 |
| SIG-01 | Phase 13 |
| SIG-02 | Phase 13 |
| ART-01 | Phase 14 |
| RPT-01 | Phase 14 |
| RPT-02 | Phase 14 |
| TST-01 | Phase 15 |

**Coverage:** 13/13 v2.2 requirements mapped exactly once.

## Scope Guardrails

v2.2 remains local-data-first and data-pipeline-first.

**Included:**
- local-data-first one-command daily scan
- watchlist validation and normalized run plan
- mandatory data-health gate
- `CompositeTrendStrategy` / `TradingSignal` scan semantics
- bucket/reason-code assignment for every symbol
- deterministic JSON artifacts and Markdown report
- tests for gate behavior, bucket coverage, artifact/report consistency, path safety, and CLI semantics

**Deferred:**
- remote refresh modes
- exchange-calendar/session-aware freshness
- daily delta against prior scans
- empirically validated ranking
- dashboard or web UI
- notifications or scheduling
- live/paper trading execution
- trading advice or buy/sell execution language

## Backlog

- Production deployment configuration
- Performance optimization

---

*Last updated: 2026-06-08 for v2.2 daily-scan-report-loop roadmap*
