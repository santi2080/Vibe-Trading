# Requirements: Vibe-Trading v2.2 Daily Scan Report Loop

**Defined:** 2026-06-08  
**Core Value:** Your Personal Trading Agent — one command to empower your agent with comprehensive trading capabilities

## v2.2 Requirements

Requirements for the daily-scan-report-loop milestone. v2.2 is data-pipeline-first: local-data-first scan, mandatory data-health gate, `CompositeTrendStrategy` / `TradingSignal` semantics, structured artifacts, and Markdown reporting.

### Stack

- [ ] **STK-01**: Project declares an explicit Parquet engine dependency (`pyarrow`) if missing so daily scan Parquet I/O is reliable.

### Daily Scan Entry Point

- [ ] **CLI-01**: User can run one daily scan command with watchlist, data dir, output dir, timestamp, and JSON/human output options.
- [ ] **CLI-02**: Daily scan command is local-data-first and does not fetch remote provider data in v2.2.

### Watchlist and Run Plan

- [ ] **WLS-01**: User gets early validation for missing/unsafe watchlist paths, required columns, empty lists, duplicates, and unsupported market/timeframe values.
- [ ] **WLS-02**: Each run produces a normalized scan plan listing symbol, market, required timeframes, cache paths, and output paths.

### Data Gate

- [ ] **GATE-01**: Daily scan always runs the existing data-health gate before any strategy analysis.
- [ ] **GATE-02**: Data-health `FAIL` produces a clearly blocked report/artifacts and no strategy candidates; `WARN` can continue with caveats.

### Signal Scan

- [ ] **SIG-01**: Eligible symbols are scanned through `CompositeTrendStrategy` / `TradingSignal` semantics, not legacy analyzer semantics.
- [ ] **SIG-02**: Every watchlist symbol is assigned to exactly one bucket or reason code: Actionable, Watch, Risk/Excluded, Skipped, or Failed.

### Artifacts and Report

- [ ] **ART-01**: Each run writes `manifest.json`, `data_health.json`, `scan_results.json`, and `report.md` in a safe deterministic run directory.
- [ ] **RPT-01**: Markdown report is rendered from artifacts and includes data health, candidates/watch/risk sections, skipped/failed symbols, caveats, and artifact links.
- [ ] **RPT-02**: Markdown report avoids unverified ranking, performance claims, and trading execution advice.

### Testing

- [ ] **TST-01**: Tests verify gate blocking, warning caveats, signal buckets, path safety, artifact schema, Markdown/JSON consistency, and CLI/tool exit semantics.

## Future Requirements

Deferred to future milestones. These are acknowledged but intentionally excluded from v2.2 to keep the milestone data-pipeline-first.

### Data Refresh and Calendars

- **REF-01**: User can run controlled refresh modes (`refresh-missing`, `refresh-stale`, `refresh-all`) with provider provenance.
- **CAL-01**: Data-health freshness supports exchange-calendar/session-aware stale checks.

### Scan History and Product UX

- **DELTA-01**: User can see changes since the previous daily scan.
- **HIST-01**: User can browse a run-history index across daily scan reports.
- **RANK-01**: User can see empirically validated ranking or prioritization only after verified backtest evidence exists.
- **NOTIF-01**: User can receive notifications or scheduled daily summaries.
- **DASH-01**: User can browse reports in a dashboard or web UI.

## Out of Scope

Explicit exclusions for v2.2.

| Feature | Reason |
|---------|--------|
| Remote data fetching as part of the default scan | v2.2 is local-data-first; refresh/fallback provenance is deferred to avoid provider variability. |
| Exchange-calendar-aware freshness | Valuable, but fixed-window gate disclosure is sufficient for MVP. |
| Daily delta against previous scans | Requires persisted state semantics beyond the first reliable scan loop. |
| Global Top 10 ranking / expected return / Sharpe / win-rate claims | v2.1 empirical evidence remains blocked; avoid false precision. |
| Live or paper trading execution | Project out-of-scope until empirical validation is resolved. |
| Trading advice / buy-sell execution language | v2.2 is research support and reporting, not execution. |
| Dashboard/web UI | Markdown + JSON artifacts are the product surface for this milestone. |
| Notifications/scheduling | One-command local workflow comes first; automation can wrap it later. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STK-01 | TBD | Pending |
| CLI-01 | TBD | Pending |
| CLI-02 | TBD | Pending |
| WLS-01 | TBD | Pending |
| WLS-02 | TBD | Pending |
| GATE-01 | TBD | Pending |
| GATE-02 | TBD | Pending |
| SIG-01 | TBD | Pending |
| SIG-02 | TBD | Pending |
| ART-01 | TBD | Pending |
| RPT-01 | TBD | Pending |
| RPT-02 | TBD | Pending |
| TST-01 | TBD | Pending |

**Coverage:**
- v2.2 requirements: 13 total
- Mapped to phases: 0
- Unmapped: 13 ⚠️

---
*Requirements defined: 2026-06-08*  
*Last updated: 2026-06-08 after v2.2 requirements definition*
