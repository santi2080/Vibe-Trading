# Project: Vibe-Trading

**Core Value:** Your Personal Trading Agent — one command to empower your agent with comprehensive trading capabilities

## Current State

**v2.3 shipped (2026-06-11):** Remote refresh scan loop with `--refresh` flag for auto-fetching stale/missing data. Full milestone details at `.planning/milestones/v2.3-ROADMAP.md`.

**Current focus:** v2.4 — Exchange Calendar Awareness

## Current Milestone: v2.4 exchange-calendar-awareness

**Goal:** Make data freshness detection aware of exchange trading sessions, avoiding unnecessary refreshes outside trading hours.

**Target features:**
- Exchange trading session definitions (A-shares, US, HK, futures)
- Holiday calendar awareness
- Session-aware freshness detection (pre-market, regular, after-hours)
- Smart refresh that respects trading hours

## What This Is

Vibe-Trading is a multi-agent trading analysis system that combines trend evaluation, signal generation, and backtesting for stocks, ETFs, futures, and crypto.

**Key capabilities:**
- MTES v3 分层趋势系统 (SMC + Elder + Ichimoku)
- TradingSignal 统一信号合约
- Enhanced SuperTrend 策略
- CompositeTrendStrategy 多策略组合
- Signal Execution System
- Watchlist Data Health Gate
- Composite BacktestSignalEngine + PositionManager (2×ATR trailing stop)
- Composite vs single strategy comparison infrastructure

## Requirements

### Validated

- ✓ MTES v3 分层架构 — v2.0
- ✓ TradingSignal 统一合约 — v2.0
- ✓ SuperTrend 增强策略 — v2.0
- ✓ Signal Execution System — v2.0
- ✓ Watchlist Data Health Gate — v2.0
- ✓ CompositeTrendStrategy 多策略组合框架 — v2.0
- ✓ CompositeBacktestSignalEngine 回测引擎 — v2.1 / Phase 09
- ✓ D-01/D-02 信号语义 (BULL/BEAR READY → long/short, D-02 trailing stop exit) — v2.1 / Phase 09
- ✓ Composite vs MTES-only vs SuperTrend-only 三路比较编排器 — v2.1 / Phase 09
- ✓ Composite 回测信号记录 (key-node + per-source) — v2.1 / Phase 09
- ✓ 数据质量检查记录 — v2.1 / Phase 09
- ✓ 回测安全门控 (path traversal, config injection, run_dir sandbox) — v2.1 / Phase 09

### Active

- [ ] v2.4 Exchange Calendar Awareness — session-aware freshness detection, holiday calendar, smart refresh respecting trading hours

### Out of Scope

- Live or paper trading execution (pending empirical validation)
- Automated parameter optimization (pending empirical validation)

## Evolution

**After v2.2 → v2.3:**
- v2.2 Daily Scan Report Loop fully shipped (Phases 11-16).
- v2.3 Remote Refresh Scan Loop shipped with `--refresh` flag (Phase 17).
- v2.4 direction: Exchange Calendar Awareness for smarter refresh.

**After v2.1 → v2.2:**
- Daily scan pipeline productized with local-data-first approach.
- Data health gate and Markdown reporting complete.
- Remote refresh capability added in v2.3.

**v2.1 known gaps:**
- No verified 2024-2026 1D/4H empirical return/win-rate/Sharpe/drawdown metrics.
- No reproducible best-configuration artifact.
- No completed composite vs single strategy comparison report.

### Out of Scope

- Live or paper trading execution (pending empirical validation)
- Automated parameter optimization (pending empirical validation)

## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| MTES v3 分层架构 | SMC + Elder + Ichimoku 组合趋势判断 | ✓ Validated |
| TradingSignal 合约 | 方向/状态/就绪分离 | ✓ Validated |
| CompositeTrendStrategy | 多策略组合框架 | ✓ Validated |
| D-01/D-02 语义 | BULL/BEAR READY → 方向; D-02 跟踪止损退出 | ✓ Validated |
| 2×ATR trailing stop | ATR-based position sizing | ✓ Validated |
| Composite backtest runner wiring | signal_engine template with strategy_variant | ✓ Validated |
| Phase 10 empirical closure | separate evidence generation from infrastructure | ✓ Implemented |

## Evolution

**After v2.0 → v2.1:**

- MTES v3, CompositeStrategy, and backtest infrastructure fully validated and shipped.
- Empirical composite backtest metrics remain blocked pending data/run-root resolution.
- v2.2 direction: Daily Scan Report Loop for productized daily Markdown reports.

**v2.1 known gaps:**
- No verified 2024-2026 1D/4H empirical return/win-rate/Sharpe/drawdown metrics.
- No reproducible best-configuration artifact.
- No completed composite vs single strategy comparison report.

---
*Last updated: 2026-06-11 after v2.4 milestone initialization*
