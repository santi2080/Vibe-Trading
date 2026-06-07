# Requirements: Vibe-Trading v2.1

**Defined:** 2026-06-06  
**Core Value:** 验证 MTES v3 + SuperTrend 复合策略效果  
**Last audited:** 2026-06-07 after Phase 10 gap-closure review

## v2.1 Requirements

### Backtest Infrastructure

- [x] **BKST-01**: 回测脚本支持 CompositeTrendStrategy 作为策略源  
  **Status:** Verified by Phase 09 infrastructure and UAT.
- [x] **BKST-02**: 回测支持 MTES v3 + SuperTrend 组合配置  
  **Status:** Verified by Phase 09 YAML/config wiring and UAT.
- [x] **BKST-03**: 回测输出包含各策略源的独立信号和组合信号  
  **Status:** Verified by Phase 09 signal artifact hook and UAT.

### Performance Metrics

- [x] **METR-01**: 计算组合策略 vs 单一策略的收益率对比  
  **Status:** Infrastructure verified by Phase 09 comparison/reporting support; empirical report evidence to be finalized in Phase 10.
- [x] **METR-02**: 计算胜率、夏普比率、最大回撤等指标  
  **Status:** Metrics helpers and regression coverage verified by Phase 09; empirical report evidence to be finalized in Phase 10.
- [x] **METR-03**: 输出每种策略源的独立表现  
  **Status:** Per-source statistics and signal artifacts verified by Phase 09; empirical report evidence to be finalized in Phase 10.

### Data Coverage

- [ ] **DATA-01**: 使用近 2 年数据 (2024-2026) 进行回测  
  **Status:** Needs Phase 10 evidence closure. Phase 09 verified config/infrastructure; final reproducible empirical coverage must be run or explicitly documented as partial/blocked.
- [ ] **DATA-02**: 覆盖 watchlist 中的主要品种（期货/ETF）  
  **Status:** Needs Phase 10 evidence closure. Coverage should list included symbols and unavailable data reasons.
- [ ] **DATA-03**: 支持 1D 和 4H 时间周期  
  **Status:** Needs Phase 10 evidence closure. If 4H is unavailable for selected data source(s), document as partial/blocked with reason.

### Analysis & Reporting

- [ ] **RPT-01**: 生成组合策略 vs 单一策略对比报告  
  **Status:** Reporting infrastructure verified by Phase 09; final empirical report artifact to be produced or linked in Phase 10.
- [ ] **RPT-02**: 识别最佳策略组合配置  
  **Status:** Reporting infrastructure verified by Phase 09; final empirical best-configuration evidence to be produced or linked in Phase 10.
- [ ] **RPT-03**: 记录数据质量和完整性检查  
  **Status:** Data-quality helper verified by Phase 09; final empirical data quality notes to be produced or linked in Phase 10.

## Traceability

| Requirement | Phase | Status | Evidence |
|-------------|-------|--------|----------|
| BKST-01 | Phase 09 | Verified | `09-SUMMARY-AGGREGATE.md`, `09-UAT.md` |
| BKST-02 | Phase 09 | Verified | `09-03-SUMMARY.md`, `09-UAT.md` |
| BKST-03 | Phase 09 | Verified | `09-03-SUMMARY.md`, `09-UAT.md` |
| METR-01 | Phase 09 + 10 | Infrastructure verified; empirical closure pending | `09-04-SUMMARY.md`; Phase 10 to produce empirical report |
| METR-02 | Phase 09 + 10 | Infrastructure verified; empirical closure pending | `09-04-SUMMARY.md`; Phase 10 to produce empirical report |
| METR-03 | Phase 09 + 10 | Infrastructure verified; empirical closure pending | `09-04-SUMMARY.md`; Phase 10 to produce empirical report |
| DATA-01 | Phase 10 | Closure pending | Phase 10 to run/document 2024-2026 coverage |
| DATA-02 | Phase 10 | Closure pending | Phase 10 to run/document watchlist coverage |
| DATA-03 | Phase 10 | Closure pending | Phase 10 to run/document 1D/4H support or blocked status |
| RPT-01 | Phase 10 | Closure pending | Phase 10 to produce/link empirical comparison report |
| RPT-02 | Phase 10 | Closure pending | Phase 10 to produce/link best-configuration evidence |
| RPT-03 | Phase 10 | Closure pending | Phase 10 to produce/link data quality notes |

**Coverage:**
- v2.1 requirements: 12 total
- Phase 09 verified infrastructure/smoke/UAT/security for BKST and METR/RPT tooling
- Phase 10 retained to close DATA/RPT empirical evidence before milestone archive

---
*Requirements defined: 2026-06-06*  
*Last updated: 2026-06-07 after Phase 10 gap-closure review*
