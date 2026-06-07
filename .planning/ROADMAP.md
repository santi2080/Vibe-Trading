# Roadmap: Vibe-Trading

## Milestones

- ✅ **v2.0** — composite-strategy-signal-layer (shipped 2026-06-06)
- ⚠ **v2.1** — composite-strategy-backtest (implementation complete; empirical evidence blocked, archive requires decision)
- 🌱 **v2.2 candidate** — daily-scan-report-loop (explored 2026-06-07)

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
| 09 | v2.1 | 4/4 | Complete    | 2026-06-06 |
| 10 | v2.1 | 6/5 | Complete   | 2026-06-07 |
| 11 | v2.2 candidate | — | Explored | — |

## Backlog

- Production deployment configuration
- Performance optimization

### Phase 10: Empirical Composite Backtest Evidence Closure

**Goal:** Close the v2.1 evidence gap by running or documenting a reproducible empirical composite backtest using the Phase 09 infrastructure, then update requirement traceability before archiving v2.1.

**Scope:** This is a v2.1 closure/verification phase, not a new feature phase.

**Requirements:** DATA-01, DATA-02, DATA-03, RPT-01, RPT-02, RPT-03, plus final evidence for METR-01/02/03 where empirical report output is required.

**Depends on:** Phase 09

**Plans:** 6/5 plans complete

**Success criteria:**
1. A reproducible composite-vs-single empirical run is available for the intended 2024-2026 period or any unavailable coverage is explicitly documented.
2. The run covers the intended watchlist major instruments where data is available.
3. Composite, MTES-only, and SuperTrend-only variants produce comparable metrics: return, win rate, Sharpe ratio, max drawdown, and trade count.
4. A Markdown empirical report records strategy comparison, best configuration, and data quality/completeness notes.
5. `REQUIREMENTS.md`, `STATE.md`, and v2.1 archive readiness agree on what is verified, partial, or blocked.

**Phase 10 closure status:** Complete with blocked empirical evidence. `final-evidence-index.json` reports `overall_status: blocked`; v2.1 archive requires user acceptance of blocked closure or a follow-up remediation phase.

**Out of scope:**
- New strategy logic
- Daily scan report productization
- Candidate scoring/ranking
- Live or paper trading execution

Plans:
- [x] 10-01: empirical inputs, readiness artifacts, manifest, configs
- [x] 10-02: 1D empirical attempt and blocked evidence inventory
- [x] 10-03: 4H attempted/blocked evidence inventory
- [x] 10-04: final empirical report and evidence index
- [x] 10-05: requirement/state/roadmap/UAT/SUMMARY closure docs

### Phase 11: Daily Scan Report Loop

**Goal:** 一条命令基于 watchlist 生成每日扫描 Markdown 报告，按“全量概览 → 可行动候选 → 观察候选 → 风险/排除”组织，帮助每天快速判断市场与标的状态。

**Product intent:** 将已验证的 MTES v3、Enhanced SuperTrend、CompositeTrendStrategy 和数据健康能力串成可日常使用的产品化闭环，而不是继续堆策略或过早进入实盘执行。

**Proposed requirements:**
- DSR-01: 支持从 watchlist / market / timeframe / strategy config 触发每日扫描
- DSR-02: 扫描前执行数据健康检查，并在报告中汇总覆盖率与排除原因
- DSR-03: 对每个标的运行 MTES、SuperTrend、CompositeTrendStrategy 信号分析
- DSR-04: 输出 watchlist overview，包括多空分布、READY / WAIT / CONFLICT 数量、数据健康摘要
- DSR-05: 输出 `Actionable Candidates` 分组：Composite READY、方向一致、数据健康通过
- DSR-06: 输出 `Watch Candidates` 分组：接近 READY、状态刚变化、单策略强但 composite 未确认
- DSR-07: 输出 `Risk / Excluded` 分组：数据不健康、信号冲突、波动/指标异常
- DSR-08: 生成以人为主的 Markdown 报告；JSON/API/通知暂不纳入 MVP

**Success criteria:**
1. 一个 CLI 命令可以生成每日扫描 Markdown 报告
2. 报告包含 Overview、Actionable Candidates、Watch Candidates、Risk / Excluded 四个核心部分
3. 每个候选标的给出方向、状态、来源信号摘要和进入该分组的理由
4. 数据不健康或信号冲突的标的不会进入 actionable 分组，并能解释排除原因
5. 不引入未验证的强排名或交易执行语义

**Out of scope for MVP:**
- 强排名 / Top 10 score
- 自动交易或半自动下单
- 通知系统
- Web UI
- 参数优化 / 自动调参
- JSON/API 产物链

**Related artifacts:**
- `.planning/notes/daily-scan-report-direction.md`
- `.planning/seeds/scored-candidate-ranking.md`

---

*Last updated: 2026-06-07 after Phase 10 execution (overall_status: blocked)*
