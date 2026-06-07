# Requirements: Vibe-Trading v2.1

**Defined:** 2026-06-06  
**Core Value:** 验证 MTES v3 + SuperTrend 复合策略效果  
**Last audited:** 2026-06-07 after Phase 10 execution (overall_status: blocked)

## v2.1 Requirements

### Backtest Infrastructure

- [x] **BKST-01**: 回测脚本支持 CompositeTrendStrategy 作为策略源  
  **Status:** Verified by Phase 09 infrastructure and UAT.
- [x] **BKST-02**: 回测支持 MTES v3 + SuperTrend 组合配置  
  **Status:** Verified by Phase 09 YAML/config wiring and UAT.
- [x] **BKST-03**: 回测输出包含各策略源的独立信号和组合信号  
  **Status:** Verified by Phase 09 signal artifact hook and UAT.

### Performance Metrics

- [ ] **METR-01**: 计算组合策略 vs 单一策略的收益率对比  
  **Status:** blocked — Phase 09 infrastructure exists, but Phase 10 produced no verified empirical return comparison metrics. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.
- [ ] **METR-02**: 计算胜率、夏普比率、最大回撤等指标  
  **Status:** blocked — Phase 10 produced no verified empirical win rate, Sharpe ratio, or max drawdown metrics. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.
- [ ] **METR-03**: 输出每种策略源的独立表现  
  **Status:** blocked — Phase 10 emitted no verified empirical per-source performance artifacts from a completed run. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.

### Data Coverage

- [ ] **DATA-01**: 使用近 2 年数据 (2024-2026) 进行回测  
  **Status:** blocked — 2024-2026 range was fixed and attempted, but no eligible local data coverage produced verified metrics. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.
- [ ] **DATA-02**: 覆盖 watchlist 中的主要品种（期货/ETF）  
  **Status:** blocked — watchlist coverage was checked, but readiness gates returned `can_backtest=false` and no eligible symbols. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.
- [ ] **DATA-03**: 支持 1D 和 4H 时间周期  
  **Status:** blocked — 1D and 4H were both represented as attempted evidence; both remain blocked by readiness/run-root limitations. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.

### Analysis & Reporting

- [ ] **RPT-01**: 生成组合策略 vs 单一策略对比报告  
  **Status:** blocked — final report contains a blocked-evidence comparison section, not verified empirical metric comparison. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.
- [ ] **RPT-02**: 识别最佳策略组合配置  
  **Status:** blocked — no best configuration can be selected without verified comparable metrics. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.
- [x] **RPT-03**: 记录数据质量和完整性检查  
  **Status:** verified — Phase 10 records data quality/completeness status with readiness artifacts and blocker evidence. Evidence: `10-EMPIRICAL-REPORT.md`, `artifacts/final-evidence-index.json`.

## Traceability

| Requirement | Phase | Status | Evidence |
|-------------|-------|--------|----------|
| BKST-01 | Phase 09 | Verified | `09-SUMMARY-AGGREGATE.md`, `09-UAT.md` |
| BKST-02 | Phase 09 | Verified | `09-03-SUMMARY.md`, `09-UAT.md` |
| BKST-03 | Phase 09 | Verified | `09-03-SUMMARY.md`, `09-UAT.md` |
| METR-01 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Return comparison metrics are missing under blocked status; no values were invented. |
| METR-02 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Win rate, Sharpe ratio, and max drawdown are missing under blocked status; no values were invented. |
| METR-03 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Per-source performance artifacts were not emitted by an empirical run; artifact checks are recorded in evidence JSON. |
| DATA-01 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — 2024-2026 range is fixed and attempted, but no eligible local data coverage produced metrics. |
| DATA-02 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Watchlist coverage was checked, but readiness gates returned can_backtest=false and eligible_symbols is empty. |
| DATA-03 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — 1D and 4H were both represented as attempted evidence; both remain blocked by readiness/run-root limitations. |
| RPT-01 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Final report contains a strategy comparison section, but it is a blocked-evidence comparison without metric values. |
| RPT-02 | Phase 10 | blocked | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Best Configuration section states no best configuration can be selected without metric values; no global rank or heuristic was computed. |
| RPT-03 | Phase 10 | verified | `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/10-EMPIRICAL-REPORT.md`, `.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/final-evidence-index.json` — Data quality and completeness status is explicitly recorded with source readiness gates and blockers. |

**Coverage:**
- v2.1 requirements: 12 total
- Phase 09 verified infrastructure/smoke/UAT/security for BKST and METR/RPT tooling
- Phase 10 executed DATA/RPT/METR empirical closure and produced audit artifacts
- Phase 10 overall_status: blocked; empirical metric evidence is not verified

---
*Requirements defined: 2026-06-06*  
*Last updated: 2026-06-07 after Phase 10 execution (overall_status: blocked)*
