# Project: Vibe-Trading

**Core Value:** Your Personal Trading Agent — one command to empower your agent with comprehensive trading capabilities

## Current State

**v2.1 shipped (2026-06-07):** Composite strategy backtest infrastructure delivered with empirical evidence blocked. Full milestone details at `.planning/milestones/v2.1-ROADMAP.md` and `.planning/milestones/v2.1-REQUIREMENTS.md`.

**Current focus:** v2.2 planning — Daily Scan Report Loop

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

- [ ] Daily Scan Report Loop (v2.2 candidate)

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
*Last updated: 2026-06-07 after v2.1 milestone close*
