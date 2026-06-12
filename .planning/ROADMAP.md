# Roadmap: Vibe-Trading

## Milestones

- ✅ **v2.0** — composite-strategy-signal-layer (shipped 2026-06-06)
- ✅ **v2.1** — composite-strategy-backtest (shipped 2026-06-07; empirical evidence blocked)
- ✅ **v2.2** — daily-scan-report-loop (shipped 2026-06-10)
- ✅ **v2.3** — remote-refresh-scan-loop (shipped 2026-06-11)
- ✅ **v2.4** — exchange-calendar-awareness (shipped 2026-06-13)
- 🌱 **v2.5** — dashboard-web-ui (in progress)

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

- [x] Phase 11: Symbol Format Mapping Contract & Data Source Translation Optimization (1/1 plans) — completed 2026-06-08
- [x] Phase 12: Daily Scan Foundation & Run Plan (1/1 plans) — completed 2026-06-09
- [x] Phase 13: Data Health Gated Scan Control (1/1 plans) — completed 2026-06-10
- [x] Phase 14: Composite Signal Scan Buckets (1/1 plans) — completed 2026-06-10
- [x] Phase 15: Deterministic Artifacts & Markdown Report (1/1 plans) — completed 2026-06-10
- [x] Phase 16: Daily Scan Verification Closure (1/1 plans) — completed 2026-06-10

**Goal:** Productize the daily scan workflow with a reliable local-data-first pipeline that can support one-command watchlist scanning and Markdown reporting.

## Phase Details

### Phase 11: Symbol Format Mapping Contract & Data Source Translation Optimization

**Goal:** User and codebase share one Canonical Symbol Format, and every data-source boundary maps that canonical symbol into the vendor-specific format without changing user-facing keys.
**Depends on:** Phase 10 / v2.1 shipped foundations
**Requirements:** SYM-01, SYM-02, SYM-03

**Success Criteria:**
1. Canonical Symbol Format is explicitly defined and tested for A-shares/ETFs, US equities, HK equities, US futures, CN futures, crypto, and forex.
2. `SymbolTranslator` maps canonical symbols into Tushare, AKShare, yfinance, TqSdk, OKX, CCXT, and Databento formats where supported, with unsupported combinations staying explicit rather than silently mangled.
3. Fetch/routing boundaries call vendors with vendor-format symbols but return canonical symbols to callers, preserving fallback and unresolved-symbol behavior.
4. Loader-specific duplicate conversion logic is either delegated to the canonical translator or retained only as tested compatibility shims.
5. Focused tests cover canonical-to-vendor contracts, routing/fallback preservation, and compatibility with the local-data-first daily scan plan.

**Plans:** 1/1 plans complete

### Phase 12: Daily Scan Foundation & Run Plan

**Goal:** User can start a local-data-first daily scan and receive validated run intent before analysis begins.
**Depends on:** Phase 11
**Requirements:** STK-01, CLI-01, CLI-02, WLS-01, WLS-02

**Success Criteria:**
1. User can invoke one daily scan command with explicit watchlist, data directory, output directory, timestamp, and JSON or human output mode.
2. User is told early when the watchlist path is missing or unsafe, required columns are absent, the list is empty, duplicate symbols exist, or market/timeframe values are unsupported.
3. User can inspect a normalized scan plan that lists each symbol, market, required timeframes, cache paths, and intended output paths before strategy results are produced.
4. The scan uses only local data inputs in v2.2; no remote provider fetch is triggered by the default daily scan command.
5. Parquet read/write support is dependable because the project explicitly declares the required Parquet engine dependency.

**Plans:** 1/1 plans complete

### Phase 13: Data Health Gated Scan Control

**Goal:** User can trust that data readiness blocks or caveats the scan before strategy work.
**Depends on:** Phase 12
**Requirements:** GATE-01, GATE-02

**Success Criteria:**
1. Every daily scan run executes the existing data-health gate before any CompositeTrendStrategy analysis.
2. A data-health `FAIL` produces blocked artifacts and a blocked report with no strategy candidates.
3. A data-health `WARN` run can continue, but the report and artifacts clearly expose the caveats.
4. User can distinguish `PASS`, `WARN`, and `FAIL` scan outcomes without reading logs.

**Plans:** 1/1 plans complete

### Phase 14: Composite Signal Scan Buckets

**Goal:** User can see every watchlist symbol classified through CompositeTrendStrategy / TradingSignal semantics.
**Depends on:** Phase 13
**Requirements:** SIG-01, SIG-02

**Success Criteria:**
1. Eligible symbols are scanned through `CompositeTrendStrategy` and serialized via `TradingSignal` semantics, not legacy analyzer semantics.
2. Every input watchlist symbol appears in exactly one final classification: Actionable, Watch, Risk/Excluded, Skipped, or Failed.
3. User can see why any symbol was skipped, failed, or excluded from actionable candidates.
4. Actionable candidates are based on validated signal readiness semantics rather than unverified ranking or historical performance claims.

**Plans:** 1/1 plans complete

### Phase 15: Deterministic Artifacts & Markdown Report

**Goal:** User gets stable machine-readable artifacts and a human-readable Markdown report without unverified claims.
**Depends on:** Phase 14
**Requirements:** ART-01, RPT-01, RPT-02

**Success Criteria:**
1. Each scan run writes `manifest.json`, `data_health.json`, `scan_results.json`, and `report.md` into a safe deterministic run directory.
2. User can open `report.md` and see data health, candidates, watch symbols, risk/excluded symbols, skipped/failed symbols, caveats, and links to artifacts.
3. Markdown report counts and sections are rendered from the JSON artifacts rather than separate ad-hoc report state.
4. The report avoids unverified ranking, performance metrics, "best configuration" claims, and trading execution advice.

**Plans:** 1/1 plans complete

### Phase 16: Daily Scan Verification Closure

**Goal:** User can verify the daily scan loop with tests covering gate, artifacts, report, safety, and CLI behavior.
**Depends on:** Phase 15
**Requirements:** TST-01

**Success Criteria:**
1. User can run focused tests showing data-health `FAIL` blocks strategy analysis and data-health `WARN` continues with visible caveats.
2. User can run focused tests showing each symbol is assigned to one bucket or reason code.
3. User can run focused tests showing artifact schemas and Markdown/JSON counts stay consistent.
4. User can run focused tests showing unsafe paths are rejected and CLI/tool exit semantics are stable for success, warning, blocked, and failure cases.

**Plans:** 1/1 plans complete

### Phase 17: Remote Refresh Scan Loop

**Goal:** User can run `scan --run --refresh` to auto-fetch stale/missing parquet data before the health gate, then proceed with scan.
**Depends on:** Phase 16 (daily scan loop)
**Requirements:** RF-01, RF-02, RF-03, RF-04, RF-05

**Success Criteria:**
1. `scan --run --refresh` fetches stale data, runs health gate, then scan.
2. Data freshness is checked per-symbol before fetch (avoid unnecessary API calls).
3. Provider 429 errors are handled gracefully with retry logic.
4. `--refresh` is optional; scan without it behaves identically to v2.2.
5. Tests cover: refresh triggered, refresh skipped (data fresh), refresh failure handling.

**Plans:** 1/1 plans complete

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|----------|
| 01-08 | v2.0 | 23/23 | Complete | 2026-06-06 |
| 09 | v2.1 | 4/4 | Complete | 2026-06-06 |
| 10 | v2.1 | 5/5 | Complete (blocked evidence) | 2026-06-07 |
| 11 | v2.2 | 1/1 | Complete | 2026-06-08 |
| 12 | v2.2 | 1/1 | Complete | 2026-06-09 |
| 13 | v2.2 | 1/1 | Complete | 2026-06-10 |
| 14 | v2.2 | 1/1 | Complete | 2026-06-10 |
| 15 | v2.2 | 1/1 | Complete | 2026-06-10 |
| 16 | v2.2 | 1/1 | Complete | 2026-06-10 |
| 17 | v2.3 | 1/1 | Complete | 2026-06-10 |
| 19 | v2.4 | 1/1 | Complete | 2026-06-11 |
| 20 | v2.4 | 1/1 | Complete | 2026-06-12 |
| 21 | v2.4 | 1/1 | Complete | 2026-06-12 |

## Coverage

| Requirement | Phase |
|-------------|-------|
| SYM-01 | Phase 11 |
| SYM-02 | Phase 11 |
| SYM-03 | Phase 11 |
| STK-01 | Phase 12 |
| CLI-01 | Phase 12 |
| CLI-02 | Phase 12 |
| WLS-01 | Phase 12 |
| WLS-02 | Phase 12 |
| GATE-01 | Phase 13 |
| GATE-02 | Phase 13 |
| SIG-01 | Phase 14 |
| SIG-02 | Phase 14 |
| ART-01 | Phase 15 |
| RPT-01 | Phase 15 |
| RPT-02 | Phase 15 |
| TST-01 | Phase 16 |
| RF-01 | Phase 17 |
| RF-02 | Phase 17 |
| RF-03 | Phase 17 |
| RF-04 | Phase 17 |
| RF-05 | Phase 17 |
| CAL-01 | Phase 18 |
| CAL-02 | Phase 19 |
| CAL-03 | Phase 20 |
| CAL-04 | Phase 21 |

**Coverage:** 16/16 v2.2 requirements mapped exactly once; 5/5 v2.3 requirements mapped exactly once; 2/4 v2.4 requirements mapped.

## Scope Guardrails

v2.2 remains local-data-first and data-pipeline-first.

**v2.3 (Phase 17):** Adds optional remote refresh before scan gate.

**Included:**
- `--refresh` flag for auto-fetch of stale/missing data before health gate
- Incremental refresh: only fetches data older than staleness threshold
- yfinance for US futures/equities, HybridDataFetcher for other markets
- 429 rate-limit handling with exponential backoff
- Non-blocking refresh failures (gate runs with available data)
- Same parquet paths as local-data-first scan

**Included:**
- Canonical Symbol Format contract and tested data-source translation boundary
- local-data-first one-command daily scan
- watchlist validation and normalized run plan
- mandatory data-health gate
- `CompositeTrendStrategy` / `TradingSignal` scan semantics
- bucket/reason-code assignment for every symbol
- deterministic JSON artifacts and Markdown report
- tests for symbol translation, gate behavior, bucket coverage, artifact/report consistency, path safety, and CLI semantics

**Deferred:**
- exchange-calendar/session-aware freshness
- daily delta against prior scans
- empirically validated ranking
- dashboard or web UI
- notifications or scheduling
- live/paper trading execution
- trading advice or buy/sell execution language

### 🌱 v2.4: Exchange Calendar Awareness

- [x] Phase 18: Exchange Session Definitions (1/1 plans) — completed
- [x] Phase 19: Holiday Calendar Integration (1/1 plans) — completed
- [x] Phase 20: Session-Aware Freshness Detection (1/1 plans) — completed
- [x] Phase 21: Risk Management Enhancement (1/1 plans) — completed

**Goal:** Make data freshness detection aware of exchange trading sessions, avoiding unnecessary refreshes outside trading hours.

**Requirements:** CAL-01, CAL-02, CAL-03, CAL-04

## Phase Details

### Phase 18: Exchange Session Definitions

**Goal:** Define trading session rules for each market type.
**Depends on:** Phase 17 / v2.3 shipped
**Requirements:** CAL-01

**Success Criteria:**
1. A-share session (09:30-11:30, 13:00-15:00, Asia/Shanghai) defined and tested.
2. US equity session (09:30-16:00, America/New_York) defined and tested.
3. US futures session (23:00-17:00 CME, America/Chicago) defined and tested.
4. China futures session (09:00-10:15, 10:30-11:30, 13:30-15:00) defined and tested.
5. Timezone conversion support for all markets.

**Plans:** 1/1 plans
- [x] 18-01-PLAN.md - Timezone-aware sessions, MarketSessionStatus enum, session-aware freshness

### Phase 19: Holiday Calendar Integration

**Goal:** Integrate holiday calendars for each market to detect non-trading days.
**Depends on:** Phase 18
**Requirements:** CAL-02

**Success Criteria:**
1. A-share holiday calendar (CNY, National Day, Labor Day) implemented.
2. US market holiday calendar (Thanksgiving, Christmas, etc.) implemented.
3. Holiday lookup function returns whether a date is a trading day.
4. Holiday calendars are extensible for future additions.

**Plans:** 1/1 plans
- [x] 19-01-PLAN.md - Holiday calendar integration with holidays library

### Phase 20: Session-Aware Freshness Detection

**Goal:** Replace simple staleness checks with session-aware freshness detection.
**Depends on:** Phase 19
**Requirements:** CAL-03

**Success Criteria:**
1. Freshness check returns session-aware status (fresh/stale/session-closed).
2. Pre-market/regular-hours/after-hours status distinction works.
3. Non-trading hours data is not marked as stale.
4. Session-aware freshness report available for scan results.

**Plans:** 1/1 plans complete
- [x] 20-01-PLAN.md - Session-aware freshness detection

**Status:** ✅ COMPLETE (2026-06-12) — session-aware stale_after_for(), _updated_on_date(), FreshnessReport, get_session_aware_report()

### Phase 21: Risk Management Enhancement

**Goal:** Enhance backtesting risk calculations with stop loss / take profit support.
**Depends on:** Phase 20 / v2.4 shipped
**Requirements:** CAL-04 (risk config integration)

**Success Criteria:**
1. RiskConfig supports stop loss method ("atr", "fixed_pct") and take profit method ("rr", "fixed", "atr_mult").
2. `calculate_stop_loss()` returns StopLossResult with stop_price, method, risk_amount, risk_pct.
3. `calculate_take_profit()` returns TakeProfitResult with tp_price, method, reward_amount, reward_risk_ratio.
4. `calculate_risk_params()` returns comprehensive RiskParams combining SL, TP, position size.
5. All new functions have unit tests with >80% coverage.

**Plans:** 1/1 plans complete
- [x] 21-01-PLAN.md - Stop loss / take profit calculation enhancements

## Backlog

- Production deployment configuration
- Performance optimization

### Phase 22: holiday calendar integration

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 21
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 22 to break down)

---

*Last updated: 2026-06-11 for Phase 19 execution*
