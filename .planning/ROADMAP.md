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

**Status:** planned (2026-05-31)

**Plans:**
- SPEC: completed (`.planning/phases/04-signal-execution-system/04-SPEC.md`)
- Plan 01: completed (`.planning/phases/04-signal-execution-system/04-01-PLAN.md`) - Core Data Models
- Plan 02: completed (`.planning/phases/04-signal-execution-system/04-02-PLAN.md`) - Risk Management
- Plan 03: completed (`.planning/phases/04-signal-execution-system/04-03-PLAN.md`) - Execution Simulator
- Plan 04: completed (`.planning/phases/04-signal-execution-system/04-04-PLAN.md`) - Portfolio Tracker
- Plan 05: completed (`.planning/phases/04-signal-execution-system/04-05-PLAN.md`) - Performance Metrics
