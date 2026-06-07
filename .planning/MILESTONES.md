# Milestones

## v2.1 composite-strategy-backtest (Shipped: 2026-06-07)

**Delivered:** Composite strategy backtest infrastructure with MTES v3 + SuperTrend integration and D-01/D-02 signal semantics. Empirical 2024-2026 backtest evidence blocked by data availability; 8/12 requirements deferred.

**Phases completed:** 09-10 (9 plans, ~35 tasks)

**Key accomplishments:**

- CompositeBacktestSignalEngine with 2×ATR trailing-stop PositionManager
- D-01/D-02 signal semantics: BULL/BEAR+READY → long/short entry; D-02 exits via ATR-based trailing stop
- Three-way comparison orchestrator for composite vs MTES-only vs SuperTrend-only
- Key-node and per-source signal artifact recording
- Composite vs single strategy metrics helpers (return, win-rate, Sharpe, max-drawdown)
- Composite report generation and data quality checks
- Data readiness assessment for US futures (GC=F, SI=F, CL=F) and ETFs
- Empirical evidence closure with blocked status fully documented

**Stats:**
- ~1647 lines of Python (11 files)
- 9 plans (Phase 09: 4, Phase 10: 5)
- ~35 tasks
- 2 phases (09 + 10)
- 1 day (2026-06-06 → 2026-06-07)

**Git range:** `feat(09-01)` → `f380e06`

**Known gaps (deferred):** 8/12 requirements blocked — no verified 2024-2026 1D/4H empirical metrics; best-configuration artifact pending empirical runs; per-source independent performance pending data availability.

**What's next:** v2.2 — Daily Scan Report Loop

---

## v2.0 composite-strategy-signal-layer (Shipped: 2026-06-06)

**Phases completed:** 8 phases, 23 plans, 19 tasks

**Key accomplishments:**

- Reusable MTES core evaluator with Base+Override profiles, six weighted scoring dimensions, independent direction, and lag-safe MTF conflict metadata
- MTES is now available as a registered trend backtest wrapper that emits evaluation-only directional signals and MTES score/state metadata columns.
- Watchlist batch analysis now emits stable MTES contract fields while delegating scoring to the core evaluator with watchlist-driven base/higher timeframes.
- Date
- Date
- Date
- Date
- Date
- Plan:
- Plan:
- Plan:
- Plan:
- Plan:
- Date:

---

