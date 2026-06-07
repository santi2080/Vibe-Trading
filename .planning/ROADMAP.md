# Roadmap: Vibe-Trading

## Milestones

- ✅ **v2.0** — composite-strategy-signal-layer (shipped 2026-06-06)
- ✅ **v2.1** — composite-strategy-backtest (shipped 2026-06-07; empirical evidence blocked)
- 🌱 **v2.2 candidate** — daily-scan-report-loop (explored 2026-06-07)

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

### 🌱 v2.2 candidate: Daily Scan Report Loop

- [ ] Phase 11: Daily Scan Report Loop (0/0 plans) — not started

**Goal:** 一条命令基于 watchlist 生成每日扫描 Markdown 报告

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|----------|
| 01-08 | v2.0 | 23/23 | Complete | 2026-06-06 |
| 09 | v2.1 | 4/4 | Complete | 2026-06-06 |
| 10 | v2.1 | 5/5 | Complete (blocked evidence) | 2026-06-07 |
| 11 | v2.2 | — | Explored | — |

## Backlog

- Production deployment configuration
- Performance optimization

---

*Last updated: 2026-06-07 after v2.1 milestone close (empirical evidence blocked closure)*
