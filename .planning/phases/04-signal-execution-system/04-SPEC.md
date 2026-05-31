# Phase 4: Signal Execution System — Specification

**Created:** 2026-05-31
**Ambiguity score:** 0.15 (gate: ≤ 0.20)
**Requirements:** 8 locked

## Goal

Build an executable trading signal system that converts MTES + SuperTrend signals into actionable trade instructions, with integrated risk management, position sizing, order execution simulation, and performance tracking.

## Background

Vibe-Trading Phases 01–03 delivered:

- **Phase 01**: Major Trend Evaluation System (MTES) — cross-asset trend scoring (0–100), 7-state classification, 6-dimensional weighted scoring for stocks, ETFs, futures, crypto, and FX.
- **Phase 02**: Trend Indicator Backtest — backtest infrastructure comparing trend indicators across markets.
- **Phase 03**: SuperTrend Enhancement Strategy — signal generation combining weekly SuperTrend anchor, daily RangeFilter confirmation, regime filters, and entry triggers (pullback/breakout/momentum).

The missing capability is turning these signals into executable trade instructions with proper risk controls. Currently signals exist as DataFrame columns but are not connected to any execution layer.

## Requirements

### 1. Signal-to-Instruction Converter

Convert boolean signal columns (`bull_signal`, `bear_signal`, `entry_trigger`) into structured `TradeInstruction` objects with:
- Direction: LONG / SHORT / FLAT
- Entry price: current bar close or next-bar open
- Stop loss: calculated from ATR or recent low/high
- Take profit: risk-reward ratio based levels
- Position size: based on risk parameters

**Acceptance:** Signal converter produces valid TradeInstruction for every bull/bear + entry trigger combination.

### 2. Risk Management Engine

Implement a risk management layer with:
- Maximum portfolio risk per trade (default 2% of capital)
- Maximum portfolio risk across all positions (default 6%)
- Per-asset position limits
- Daily/weekly loss limits with circuit breaker
- Correlation-based position reduction

**Acceptance:** Risk engine rejects or scales positions that exceed defined risk parameters.

### 3. Position Sizing Calculator

Calculate optimal position size based on:
- Account equity and risk per trade
- Asset volatility (ATR-based or HV percentile)
- Correlation with existing positions
- Asset-class specific sizing rules (futures multiplier, crypto discount)

**Acceptance:** Position sizing produces fractional shares/contracts that respect risk limits.

### 4. Order Execution Simulator

Simulate order execution with:
- Market orders (next bar open)
- Limit orders (with fill probability model)
- Slippage modeling (configurable bps)
- Partial fill handling
- Order state machine: PENDING → FILLED / PARTIAL / REJECTED / CANCELLED

**Acceptance:** Execution simulator produces realistic fill prices and state transitions.

### 5. Portfolio State Tracker

Maintain portfolio state including:
- Cash balance and total equity
- Open positions with entry price, size, unrealized P&L
- Position history with entry/exit records
- Closed trades with realized P&L and metrics

**Acceptance:** Portfolio tracker correctly computes equity curve, drawdown, and trade-level metrics.

### 6. Performance Metrics Engine

Calculate comprehensive performance metrics:
- Total return, annualized return
- Sharpe ratio, Sortino ratio
- Maximum drawdown and drawdown duration
- Win rate, profit factor, avg win/loss
- Trade-level metrics: holding period, MAE/MFE

**Acceptance:** Metrics match manual calculations on fixture trade history.

### 7. Backtest Integration

Integrate with existing backtest infrastructure:
- Compatible with `backtest/runner.py` signal interface
- Supports multi-asset backtesting
- Produces equity curve DataFrame
- Generates summary statistics

**Acceptance:** Running backtest on MTES+SuperTrend signals produces equity curve and metrics.

### 8. Signal Quality Filter

Filter signals based on quality criteria:
- MTES trend score threshold (default: score ≥ 60 for trend confirmation)
- Regime filter (reject in NEUTRAL_CHOPPY state)
- Volatility filter (reject in extreme volatility)
- Signal age filter (expire stale signals)

**Acceptance:** Quality filter reduces false signals while preserving valid entries.

## Boundaries

**In scope:**
- Signal conversion to trade instructions
- Risk management rules and circuit breakers
- Position sizing algorithms
- Execution simulation (paper trading, not live)
- Portfolio state management
- Performance metrics calculation
- Integration with existing MTES and SuperTrend modules
- Backtest compatibility

**Out of scope:**
- Live broker connectivity or order routing
- Real-time data streaming
- Portfolio optimization (mean-variance, etc.)
- Machine learning for signal generation
- Fundamental analysis integration
- Multi-currency handling
- Options/futures-specific margin modeling

## Constraints

- All signal processing must be deterministic for reproducible backtests.
- Position sizing must respect risk limits without manual override.
- Execution simulator must produce realistic but not over-optimistic fills.
