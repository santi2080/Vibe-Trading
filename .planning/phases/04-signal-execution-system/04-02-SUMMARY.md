# Phase 04 Plan 02: Risk Management Engine

**Plan:** 04-02
**Status:** ✅ completed
**Created:** 2026-05-31
**Executed:** 2026-05-31

## Execution Summary

### Tasks Completed

- [x] Create `agent/src/analysis/risk_manager.py` with:
  - [x] `RiskConfig` dataclass (max_risk_per_trade, max_portfolio_risk, daily_loss_limit, atr_multiplier)
  - [x] `RiskManager` class with stateful risk management
  - [x] `calculate_position_size()` with ATR-based calculation
  - [x] `check_portfolio_risk()` function
  - [x] `apply_circuit_breaker()` function
  - [x] `calculate_risk_reward_ratio()` function
  - [x] `calculate_kelly_criterion()` function

- [x] Create `agent/tests/test_risk_manager.py` with:
  - [x] 42 tests covering all components
  - [x] TestRiskConfig (6 tests)
  - [x] TestRiskManager (7 tests)
  - [x] TestCalculatePositionSize (6 tests)
  - [x] TestCheckPortfolioRisk (4 tests)
  - [x] TestApplyCircuitBreaker (5 tests)
  - [x] TestRiskRewardRatio (5 tests)
  - [x] TestKellyCriterion (5 tests)

### Verification

```
✅ 42 tests passed in 0.26s
```

### Key Design Decisions

1. **RiskConfig.__post_init__** validates all risk parameters
2. **DailyLossRecord** tracks daily losses with circuit breaker
3. **ATR-based position sizing** with configurable multiplier
4. **Asset-class leverage** (stocks=1x, futures=1x, crypto=0.5x)

### Artifacts

- `agent/src/analysis/risk_manager.py` - Risk management engine (367 lines)
- `agent/tests/test_risk_manager.py` - Test suite (423 lines)

### Next

Continue with Phase 04 Plan 03: Execution Simulator
