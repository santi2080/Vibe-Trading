# Project: Vibe-Trading

**Core Value:** Your Personal Trading Agent — one command to empower your agent with comprehensive trading capabilities

## Current Milestone: v2.1 复合策略验证

**Goal:** 验证 MTES v3 + SuperTrend 复合策略在真实市场数据上的效果

**Target features:**
- CompositeTrendStrategy 回测验证
- MTES v3 + SuperTrend 组合效果评估
- 近 2 年数据回测 (2024-2026)
- 组合信号与单一信号对比分析

## What This Is

Vibe-Trading is a multi-agent trading analysis system that combines trend evaluation, signal generation, and backtesting for stocks, ETFs, futures, and crypto.

**Key capabilities:**
- MTES v3 分层趋势系统 (SMC + Elder + Ichimoku)
- TradingSignal 统一信号合约
- Enhanced SuperTrend 策略
- Signal Execution System
- Watchlist Data Health Gate

## Requirements

### Validated

- ✓ MTES v3 分层架构 — v2.0
- ✓ TradingSignal 统一合约 — v2.0
- ✓ SuperTrend 增强策略 — v2.0
- ✓ Signal Execution System — v2.0
- ✓ Watchlist Data Health Gate — v2.0
- ✓ CompositeTrendStrategy 回测验证 — v2.1 / Phase 09
- ✓ MTES v3 + SuperTrend 组合评估 — v2.1 / Phase 09

### Active

- [ ] v2.1 milestone archive and next milestone definition

## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| MTES v3 分层架构 | SMC + Elder + Ichimoku 组合趋势判断 | ✓ Validated |
| TradingSignal 合约 | 方向/状态/就绪分离 | ✓ Validated |
| CompositeTrendStrategy | 多策略组合框架 | ✓ Validated via Phase 09 backtest |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

---
*Last updated: 2026-06-06 after Phase 09 / v2.1 verification*
