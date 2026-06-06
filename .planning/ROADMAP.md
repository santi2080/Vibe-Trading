# Roadmap: Vibe-Trading

## Milestones

- ✅ **v2.0** — composite-strategy-signal-layer (shipped 2026-06-06)
- 🚧 **v2.1** — composite-strategy-backtest (in progress)

## Current Milestone: v2.1

### Phase 1: 回测基础设施

**Goal:** 确保 CompositeTrendStrategy 与回测系统集成，支持 MTES v3 + SuperTrend 组合配置

**Requirements:** BKST-01, BKST-02, BKST-03

**Success criteria:**
1. 回测脚本支持 CompositeTrendStrategy 作为策略源
2. 回测支持 MTES v3 + SuperTrend 组合配置
3. 回测输出包含各策略源的独立信号和组合信号

### Phase 2: 性能指标计算

**Goal:** 计算组合策略 vs 单一策略的收益率、胜率、夏普比率等指标

**Requirements:** METR-01, METR-02, METR-03

**Success criteria:**
1. 计算组合策略 vs 单一策略的收益率对比
2. 计算胜率、夏普比率、最大回撤等指标
3. 输出每种策略源的独立表现

### Phase 3: 数据覆盖与报告

**Goal:** 使用近 2 年数据完成回测，生成对比报告

**Requirements:** DATA-01, DATA-02, DATA-03, RPT-01, RPT-02, RPT-03

**Success criteria:**
1. 使用近 2 年数据 (2024-2026) 完成回测
2. 覆盖 watchlist 中的主要品种
3. 生成组合策略 vs 单一策略对比报告
4. 识别最佳策略组合配置

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|----------|
| 01-08 | v2.0 | 23/23 | Complete | 2026-06-06 |
| 09 | v2.1 | — | Not started | — |
| 10 | v2.1 | — | Not started | — |
| 11 | v2.1 | — | Not started | — |

## Backlog

- Production deployment configuration
- Performance optimization

---
*Last updated: 2026-06-06*
