# Roadmap

## Current Milestone: Vibe-Trading Analysis Enhancements

### Phase 1: Major Trend Evaluation System

**Goal:** Build a cross-asset major-trend evaluation system that scores stocks, ETFs, futures, crypto, and FX using direction, strength, structure, momentum, volatility/noise, and multi-timeframe alignment.

**Depends on:** Existing Vibe-Trading data loaders, strategy modules, watchlist analysis, and backtest infrastructure.

**Status:** completed (verified 2026-05-29)

**Plans:**
- SPEC: completed (`.planning/phases/01-major-trend-evaluation-system/01-SPEC.md`)
- Discuss: completed (`.planning/phases/01-major-trend-evaluation-system/01-DISCUSSION-LOG.md`)
- Plan: completed (`.planning/phases/01-major-trend-evaluation-system/01-01-PLAN.md` to `01-04-PLAN.md`)
- Execute: completed (`.planning/phases/01-major-trend-evaluation-system/01-01-SUMMARY.md` to `01-04-SUMMARY.md`)
- Verify: completed (`.planning/phases/01-major-trend-evaluation-system/01-VERIFICATION.md`)

### Phase 2: Trend Indicator Backtest

**Goal:** Build and run a trend-indicator backtest system that compares trend judgment indicators across markets and recommends indicator choices for daily and weekly trend analysis.

**Depends on:** Existing local market data, Phase 01 MTES implementation, and report generation conventions.

**Status:** completed (verified 2026-05-30)

**Plans:**
- Plan: completed (`.planning/phases/02-trend-indicator-backtest/02-01-PLAN.md`)
- Execute: completed (`.planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md`)
- Verify: completed (`.planning/phases/02-trend-indicator-backtest/02-VERIFICATION.md`)

### Phase 3: SuperTrend Enhancement Strategy

**Goal:** Design an executable research and implementation plan for a new securities trend + entry signal strategy combination that uses SuperTrend as a higher-timeframe trend anchor, then improves signal quality with regime filters, daily confirmation, pullback/breakout/momentum entry triggers, MTES conflict filtering, and trading-oriented evaluation metrics.

**Depends on:** Phase 02 trend indicator backtest outputs, `scripts/backtest_trend_indicators.py`, local OHLCV data, existing strategy/backtest patterns, and Phase 01 MTES outputs.

**Status:** completed (verified 2026-05-30)

**Plans:**
- Research: completed (`.planning/phases/03-supertrend-enhancement-strategy/03-RESEARCH.md`)
- Patterns: completed (`.planning/phases/03-supertrend-enhancement-strategy/03-PATTERNS.md`)
- Validation map: completed (`.planning/phases/03-supertrend-enhancement-strategy/03-VALIDATION.md`)
- Plan: completed (`.planning/phases/03-supertrend-enhancement-strategy/03-01-PLAN.md` to `03-05-PLAN.md`)
- Verify: completed (plan-checker passed with 0 blockers / 0 warnings)

### Phase 4: Signal Execution System

**Goal:** Build an executable trading signal system that converts MTES + SuperTrend signals into actionable trade instructions, with integrated risk management, position sizing, order execution simulation, and performance tracking.

**Depends on:** Phase 01 MTES, Phase 03 SuperTrend Enhancement Strategy, existing backtest infrastructure.

**Status:** completed (executed 2026-05-31)

**Plans:**
- SPEC: completed (`.planning/phases/04-signal-execution-system/04-SPEC.md`)
- Plan 01: completed (`.planning/phases/04-signal-execution-system/04-01-PLAN.md`) - Core Data Models
- Plan 02: completed (`.planning/phases/04-signal-execution-system/04-02-PLAN.md`) - Risk Management
- Plan 03: completed (`.planning/phases/04-signal-execution-system/04-03-PLAN.md`) - Execution Simulator
- Plan 04: completed (`.planning/phases/04-signal-execution-system/04-04-PLAN.md`) - Portfolio Tracker
- Plan 05: completed (`.planning/phases/04-signal-execution-system/04-05-PLAN.md`) - Performance Metrics
- Execute: completed (`.planning/phases/04-signal-execution-system/04-01-SUMMARY.md` to `04-05-SUMMARY.md`)

### Phase 5: MTES v2 Direction-Primary Scoring

**Goal:** Refactor MTES to use direction-primary scoring where trend_score = -100 ~ +100 (signed), with direction as the primary signal and strength metrics as confirmation.

**Status:** completed (validated 2026-05-31)

**Plans:**
- SPEC: completed (`.planning/phases/05-mtes-refactor/05-SPEC.md`)
- Plan 01: completed (`.planning/phases/05-mtes-refactor/05-01-PLAN.md`) - V2 data structures and scoring functions
- Validation: completed (`.planning/phases/05-mtes-refactor/05-VALIDATION.md`) - 14 tests pass

### Phase 6: MTES v3 - 分层递进趋势系统

**Goal:** 将当前 MTES 6 维度加权评分架构重构为分层递进趋势系统，消除 SMA 滞后问题，引入 SMC 市场结构分析和 Elder 三重滤网。

**Architecture:**
```
Layer 0: 预处理层 (ADX 预过滤, 数据验证)
Layer 1: 大周期趋势锁定 (SMC + Elder 三重滤网 + Ichimoku)
Layer 2: 趋势强度确认 (ADX 门槛 + 动量背离)
Layer 3: 入场时机 (FVG 回踩 + RSI 极值)
```

**Status:** completed (verified 2026-06-01)

**Plans:**
- SPEC: completed (`.planning/phases/06-mtes-v3-layered-system/06-SPEC.md`)
- Discussion: completed (`.planning/phases/06-mtes-v3-layered-system/06-DISCUSSION-LOG.md`)
- Plan 01: completed (`.planning/phases/06-mtes-v3-layered-system/06-01-PLAN.md`) - 核心架构 + Layer 0 + Layer 1 SMC
- Plan 02: completed (`.planning/phases/06-mtes-v3-layered-system/06-02-PLAN.md`) - Elder 三重滤网 + Ichimoku
- Plan 03: completed (`.planning/phases/06-mtes-v3-layered-system/06-03-PLAN.md`) - Layer 2 趋势强度 + Layer 3 入场时机
- Plan 04: completed (`.planning/phases/06-mtes-v3-layered-system/06-04-PLAN.md`) - 整合测试 + MTES v2 适配器
- Execute: completed (`.planning/phases/06-mtes-v3-layered-system/06-01-SUMMARY.md` to `06-04-SUMMARY.md`)
- Verify: completed (`.planning/phases/06-mtes-v3-layered-system/06-VERIFICATION.md`)

### Phase 7: Watchlist Local Data Health Gate

**Goal:** Implement the deferred REQ-001 gate so watchlist-based backtests and analysis can inspect standard local parquet data before running, report per-symbol/per-timeframe health, and block backtests when required local data is missing, empty, invalid, or stale.

**Depends on:** Existing `WatchlistReader`, `watchlist_data_health.py`, watchlist tools/MCP wrappers, local `data/{market}/{symbol}/{timeframe}.parquet` cache conventions, and current watchlist/backtest entry points.

**Requirements:** REQ-001

**Status:** completed (verified 2026-06-02)

**Plans:**
- Context: completed (`.planning/phases/07-watchlist-data-health-gate/07-CONTEXT.md`)
- Research: completed (`.planning/phases/07-watchlist-data-health-gate/07-RESEARCH.md`)
- Plan 01: completed (`.planning/phases/07-watchlist-data-health-gate/07-01-PLAN.md`) - Tool/MCP exposure for watchlist data health gate
- Plan 02: completed (`.planning/phases/07-watchlist-data-health-gate/07-02-PLAN.md`) - Backtest/analyze gate integration and verification
- Execute: completed (`.planning/phases/07-watchlist-data-health-gate/07-01-SUMMARY.md`, `.planning/phases/07-watchlist-data-health-gate/07-02-SUMMARY.md`)
- Verify: completed (`.planning/phases/07-watchlist-data-health-gate/07-VERIFICATION.md`)
