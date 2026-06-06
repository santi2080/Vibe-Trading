# Requirements: Vibe-Trading v2.1

**Defined:** 2026-06-06
**Core Value:** 验证 MTES v3 + SuperTrend 复合策略效果

## v2.1 Requirements

### Backtest Infrastructure

- [ ] **BKST-01**: 回测脚本支持 CompositeTrendStrategy 作为策略源
- [ ] **BKST-02**: 回测支持 MTES v3 + SuperTrend 组合配置
- [ ] **BKST-03**: 回测输出包含各策略源的独立信号和组合信号

### Performance Metrics

- [ ] **METR-01**: 计算组合策略 vs 单一策略的收益率对比
- [ ] **METR-02**: 计算胜率、夏普比率、最大回撤等指标
- [ ] **METR-03**: 输出每种策略源的独立表现

### Data Coverage

- [ ] **DATA-01**: 使用近 2 年数据 (2024-2026) 进行回测
- [ ] **DATA-02**: 覆盖 watchlist 中的主要品种（期货/ETF）
- [ ] **DATA-03**: 支持 1D 和 4H 时间周期

### Analysis & Reporting

- [ ] **RPT-01**: 生成组合策略 vs 单一策略对比报告
- [ ] **RPT-02**: 识别最佳策略组合配置
- [ ] **RPT-03**: 记录数据质量和完整性检查

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BKST-01 | Phase 1 | Pending |
| BKST-02 | Phase 1 | Pending |
| BKST-03 | Phase 1 | Pending |
| METR-01 | Phase 2 | Pending |
| METR-02 | Phase 2 | Pending |
| METR-03 | Phase 2 | Pending |
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| RPT-01 | Phase 3 | Pending |
| RPT-02 | Phase 3 | Pending |
| RPT-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-06*
*Last updated: 2026-06-06 after v2.1 initial definition*
