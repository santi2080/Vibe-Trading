"""Tests for risk_manager module.

Covers:
- RiskConfig validation
- RiskManager state management
- Position sizing calculations
- Portfolio risk checks
- Circuit breaker logic
- Risk/reward and Kelly Criterion
"""

from __future__ import annotations

from datetime import datetime

import pytest

from agent.src.analysis.risk_manager import (
    RiskConfig,
    RiskManager,
    apply_circuit_breaker,
    calculate_kelly_criterion,
    calculate_position_size,
    calculate_risk_reward_ratio,
    check_portfolio_risk,
)


class TestRiskConfig:
    """Tests for RiskConfig dataclass."""

    def test_default_values(self):
        config = RiskConfig()
        assert config.max_risk_per_trade == 0.02
        assert config.max_portfolio_risk == 0.06
        assert config.daily_loss_limit == 0.03
        assert config.atr_multiplier == 2.0
        assert config.min_position_size == 0.1
        assert config.max_position_size == 100.0

    def test_custom_values(self):
        config = RiskConfig(
            max_risk_per_trade=0.01,
            max_portfolio_risk=0.05,
            daily_loss_limit=0.02,
            atr_multiplier=1.5,
            min_position_size=0.5,
            max_position_size=50.0,
        )
        assert config.max_risk_per_trade == 0.01
        assert config.max_portfolio_risk == 0.05
        assert config.daily_loss_limit == 0.02
        assert config.atr_multiplier == 1.5
        assert config.min_position_size == 0.5
        assert config.max_position_size == 50.0

    def test_invalid_max_risk_per_trade(self):
        with pytest.raises(ValueError, match="max_risk_per_trade"):
            RiskConfig(max_risk_per_trade=1.5)

    def test_invalid_max_portfolio_risk(self):
        with pytest.raises(ValueError, match="max_portfolio_risk"):
            RiskConfig(max_portfolio_risk=-0.1)

    def test_invalid_daily_loss_limit(self):
        with pytest.raises(ValueError, match="daily_loss_limit"):
            RiskConfig(daily_loss_limit=0)

    def test_invalid_atr_multiplier(self):
        with pytest.raises(ValueError, match="atr_multiplier"):
            RiskConfig(atr_multiplier=0)


class TestRiskManager:
    """Tests for RiskManager class."""

    def test_create_risk_manager(self):
        config = RiskConfig()
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        assert rm.initial_capital == 100000.0
        assert rm.current_capital == 100000.0
        assert rm.total_equity == 100000.0
        assert rm.is_circuit_breaker_triggered is False

    def test_can_take_trade(self):
        rm = RiskManager(
            config=RiskConfig(),
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        can_trade, reason = rm.can_take_trade()
        assert can_trade is True
        assert reason == "OK"

    def test_cannot_take_trade_no_capital(self):
        rm = RiskManager(
            config=RiskConfig(),
            initial_capital=100000.0,
            current_capital=0.0,
        )
        can_trade, reason = rm.can_take_trade()
        assert can_trade is False
        assert reason == "No capital available"

    def test_circuit_breaker_blocks_trades(self):
        config = RiskConfig(daily_loss_limit=0.03)
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        rm.update_capital(96900.0)
        can_trade, reason = rm.can_take_trade()
        assert can_trade is False
        assert "Circuit breaker" in reason

    def test_update_capital(self):
        config = RiskConfig()
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        rm.update_capital(99000.0)
        assert rm.current_capital == 99000.0
        assert rm.daily_loss_pct == 0.01

    def test_reset_for_new_day(self):
        config = RiskConfig(daily_loss_limit=0.03)
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        rm.update_capital(96900.0)
        assert rm.is_circuit_breaker_triggered is True

        rm.reset_for_new_day()
        assert rm.is_circuit_breaker_triggered is False
        assert rm.daily_record.starting_equity == 96900.0


class TestCalculatePositionSize:
    """Tests for calculate_position_size function."""

    def test_basic_calculation(self):
        size = calculate_position_size(
            equity=100000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            risk_pct=0.02,
        )
        assert size > 0
        assert isinstance(size, float)

    def test_with_atr(self):
        size = calculate_position_size(
            equity=100000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            risk_pct=0.02,
            atr=2.0,
            atr_multiplier=2.0,
        )
        assert size > 0

    def test_invalid_prices(self):
        size = calculate_position_size(
            equity=100000.0,
            entry_price=0,
            stop_loss_price=98.0,
        )
        assert size == 0.1

    def test_zero_equity(self):
        size = calculate_position_size(
            equity=0,
            entry_price=100.0,
            stop_loss_price=98.0,
        )
        assert size == 0.1

    def test_size_bounded_by_min_max(self):
        size = calculate_position_size(
            equity=1000.0,
            entry_price=100.0,
            stop_loss_price=99.99,
            risk_pct=0.02,
        )
        assert size >= 0.1
        assert size <= 100.0

    def test_risk_amount_calculation(self):
        equity = 100000.0
        risk_pct = 0.02
        risk_amount = equity * risk_pct
        assert risk_amount == 2000.0


class TestRiskManagerPositionSizing:
    """Tests for RiskManager.calculate_position_size method."""

    def test_calculate_position_size_stock(self):
        config = RiskConfig()
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        size = rm.calculate_position_size(
            entry_price=100.0,
            stop_loss_price=98.0,
            asset_class="stock",
        )
        assert size > 0

    def test_calculate_position_size_futures(self):
        config = RiskConfig()
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        size = rm.calculate_position_size(
            entry_price=5000.0,
            stop_loss_price=4950.0,
            atr=25.0,
            asset_class="futures",
        )
        assert size > 0

    def test_calculate_position_size_with_atr(self):
        config = RiskConfig(atr_multiplier=2.0)
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        size = rm.calculate_position_size(
            entry_price=5000.0,
            stop_loss_price=4950.0,
            atr=25.0,
        )
        assert size > 0

    def test_leverage_for_crypto(self):
        config = RiskConfig()
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        leverage = rm._get_leverage("crypto")
        assert leverage == 0.5

    def test_leverage_for_stock(self):
        config = RiskConfig()
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )
        leverage = rm._get_leverage("stock")
        assert leverage == 1.0


class TestCheckPortfolioRisk:
    """Tests for check_portfolio_risk function."""

    def test_no_positions_within_limits(self):
        within, risk_pct = check_portfolio_risk(
            open_positions=[],
            current_equity=100000.0,
        )
        assert within is True
        assert risk_pct == 0.0

    def test_within_limits(self):
        within, risk_pct = check_portfolio_risk(
            open_positions=[
                {"risk_amount": 1000.0},
                {"risk_amount": 2000.0},
            ],
            current_equity=100000.0,
        )
        assert within is True
        assert risk_pct == 0.03

    def test_exceeds_limits(self):
        within, risk_pct = check_portfolio_risk(
            open_positions=[
                {"risk_amount": 5000.0},
                {"risk_amount": 2000.0},
            ],
            current_equity=100000.0,
        )
        assert within is False
        assert risk_pct == 0.07

    def test_zero_equity(self):
        within, risk_pct = check_portfolio_risk(
            open_positions=[{"risk_amount": 1000.0}],
            current_equity=0,
        )
        assert within is False
        assert risk_pct == 1.0


class TestApplyCircuitBreaker:
    """Tests for apply_circuit_breaker function."""

    def test_no_loss(self):
        triggered, reason = apply_circuit_breaker(
            daily_loss_pct=0.0,
            daily_loss_limit=0.03,
        )
        assert triggered is False
        assert reason == "No loss"

    def test_within_limits(self):
        triggered, reason = apply_circuit_breaker(
            daily_loss_pct=0.02,
            daily_loss_limit=0.03,
        )
        assert triggered is False
        assert reason == "OK"

    def test_at_limit(self):
        triggered, reason = apply_circuit_breaker(
            daily_loss_pct=0.03,
            daily_loss_limit=0.03,
        )
        assert triggered is True

    def test_exceeds_limit(self):
        triggered, reason = apply_circuit_breaker(
            daily_loss_pct=0.05,
            daily_loss_limit=0.03,
        )
        assert triggered is True
        assert "exceeds limit" in reason

    def test_negative_loss(self):
        triggered, reason = apply_circuit_breaker(
            daily_loss_pct=-0.01,
            daily_loss_limit=0.03,
        )
        assert triggered is False


class TestRiskRewardRatio:
    """Tests for calculate_risk_reward_ratio function."""

    def test_basic_calculation(self):
        ratio = calculate_risk_reward_ratio(
            entry_price=100.0,
            stop_loss_price=98.0,
            take_profit_price=106.0,
        )
        assert ratio == 3.0

    def test_short_trade(self):
        ratio = calculate_risk_reward_ratio(
            entry_price=100.0,
            stop_loss_price=102.0,
            take_profit_price=94.0,
        )
        assert ratio == 3.0

    def test_invalid_prices(self):
        ratio = calculate_risk_reward_ratio(
            entry_price=0,
            stop_loss_price=98.0,
            take_profit_price=106.0,
        )
        assert ratio == 0.0

    def test_zero_stop_distance(self):
        ratio = calculate_risk_reward_ratio(
            entry_price=100.0,
            stop_loss_price=100.0,
            take_profit_price=106.0,
        )
        assert ratio == 0.0

    def test_1_to_1_ratio(self):
        ratio = calculate_risk_reward_ratio(
            entry_price=100.0,
            stop_loss_price=99.0,
            take_profit_price=101.0,
        )
        assert ratio == 1.0


class TestKellyCriterion:
    """Tests for calculate_kelly_criterion function."""

    def test_basic_calculation(self):
        kelly = calculate_kelly_criterion(
            win_rate=0.6,
            avg_win=100.0,
            avg_loss=50.0,
        )
        assert kelly > 0
        assert kelly <= 1

    def test_perfect_win_rate(self):
        kelly = calculate_kelly_criterion(
            win_rate=1.0,
            avg_win=100.0,
            avg_loss=50.0,
        )
        assert kelly == 1.0

    def test_zero_win_rate(self):
        kelly = calculate_kelly_criterion(
            win_rate=0.0,
            avg_win=100.0,
            avg_loss=50.0,
        )
        assert kelly == 0.0

    def test_negative_expectancy(self):
        kelly = calculate_kelly_criterion(
            win_rate=0.3,
            avg_win=50.0,
            avg_loss=100.0,
        )
        assert kelly == 0.0

    def test_zero_avg_loss(self):
        kelly = calculate_kelly_criterion(
            win_rate=0.6,
            avg_win=100.0,
            avg_loss=0.0,
        )
        assert kelly == 0.0


# ============================================================================
# New tests for enhanced risk management (Phase 21)
# ============================================================================


class TestStopLossResult:
    """Tests for StopLossResult dataclass."""

    def test_stop_loss_result_creation(self):
        from agent.src.analysis.risk_manager import StopLossResult

        result = StopLossResult(
            stop_price=98.0,
            method="atr",
            risk_amount=2.0,
            risk_pct=0.02,
            stop_distance=2.0,
        )
        assert result.stop_price == 98.0
        assert result.method == "atr"
        assert result.risk_amount == 2.0
        assert result.risk_pct == 0.02
        assert result.stop_distance == 2.0

    def test_stop_loss_result_immutable(self):
        from agent.src.analysis.risk_manager import StopLossResult

        result = StopLossResult(
            stop_price=98.0,
            method="atr",
            risk_amount=2.0,
            risk_pct=0.02,
            stop_distance=2.0,
        )
        with pytest.raises(AttributeError):
            result.stop_price = 97.0


class TestTakeProfitResult:
    """Tests for TakeProfitResult dataclass."""

    def test_take_profit_result_creation(self):
        from agent.src.analysis.risk_manager import TakeProfitResult

        result = TakeProfitResult(
            tp_price=106.0,
            method="rr",
            reward_amount=6.0,
            reward_pct=0.06,
            reward_risk_ratio=3.0,
            tp_distance=6.0,
        )
        assert result.tp_price == 106.0
        assert result.method == "rr"
        assert result.reward_amount == 6.0
        assert result.reward_pct == 0.06
        assert result.reward_risk_ratio == 3.0
        assert result.tp_distance == 6.0


class TestRiskParams:
    """Tests for RiskParams dataclass."""

    def test_risk_params_creation(self):
        from agent.src.analysis.risk_manager import (
            RiskParams,
            StopLossResult,
            TakeProfitResult,
            TradeDirection,
        )

        params = RiskParams(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            stop_loss=StopLossResult(
                stop_price=98.0,
                method="atr",
                risk_amount=2.0,
                risk_pct=0.02,
                stop_distance=2.0,
            ),
            take_profit=TakeProfitResult(
                tp_price=106.0,
                method="rr",
                reward_amount=6.0,
                reward_pct=0.06,
                reward_risk_ratio=3.0,
                tp_distance=6.0,
            ),
            position_size=1000.0,
            risk_amount=2000.0,
            reward_amount=6000.0,
            risk_reward_ratio=3.0,
            stop_loss_pct=0.02,
            take_profit_pct=0.06,
            atr=2.0,
            method="atr",
        )
        assert params.entry_price == 100.0
        assert params.direction == TradeDirection.LONG
        assert params.position_size == 1000.0
        assert params.risk_reward_ratio == 3.0


class TestTradeDirection:
    """Tests for TradeDirection enum."""

    def test_long_direction(self):
        from agent.src.analysis.risk_manager import TradeDirection

        assert TradeDirection.LONG.value == 1
        assert TradeDirection.LONG.name == "LONG"

    def test_short_direction(self):
        from agent.src.analysis.risk_manager import TradeDirection

        assert TradeDirection.SHORT.value == -1
        assert TradeDirection.SHORT.name == "SHORT"


class TestCalculateStopLoss:
    """Tests for calculate_stop_loss function."""

    def test_atr_stop_loss_long(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_stop_loss,
        )

        config = RiskConfig(atr_multiplier=2.0)
        result = calculate_stop_loss(
            entry_price=100.0,
            atr=2.0,
            direction=TradeDirection.LONG,
            config=config,
        )
        assert result.stop_price == 96.0  # 100 - (2 * 2)
        assert result.method == "atr"
        assert result.stop_distance == 4.0

    def test_atr_stop_loss_short(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_stop_loss,
        )

        config = RiskConfig(atr_multiplier=2.0)
        result = calculate_stop_loss(
            entry_price=100.0,
            atr=2.0,
            direction=TradeDirection.SHORT,
            config=config,
        )
        assert result.stop_price == 104.0  # 100 + (2 * 2)
        assert result.method == "atr"
        assert result.stop_distance == 4.0

    def test_fixed_pct_stop_loss_long(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_stop_loss,
        )

        config = RiskConfig(stop_loss_method="fixed_pct", stop_loss_pct=0.02)
        result = calculate_stop_loss(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            config=config,
        )
        assert result.stop_price == 98.0  # 100 * (1 - 0.02)
        assert result.method == "fixed_pct"
        assert result.risk_pct == 0.02

    def test_fixed_pct_stop_loss_short(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_stop_loss,
        )

        config = RiskConfig(stop_loss_method="fixed_pct", stop_loss_pct=0.02)
        result = calculate_stop_loss(
            entry_price=100.0,
            direction=TradeDirection.SHORT,
            config=config,
        )
        assert result.stop_price == 102.0  # 100 * (1 + 0.02)
        assert result.method == "fixed_pct"

    def test_fallback_to_fixed_pct_without_atr(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_stop_loss,
        )

        config = RiskConfig()
        result = calculate_stop_loss(
            entry_price=100.0,
            atr=None,
            direction=TradeDirection.LONG,
            config=config,
        )
        # Should fall back to fixed_pct when atr is None
        assert result.method == "fixed_pct"

    def test_invalid_entry_price(self):
        from agent.src.analysis.risk_manager import (
            TradeDirection,
            calculate_stop_loss,
        )

        result = calculate_stop_loss(
            entry_price=0,
            direction=TradeDirection.LONG,
        )
        assert result.stop_price == 0.0
        assert result.risk_amount == 0.0


class TestCalculateTakeProfit:
    """Tests for calculate_take_profit function."""

    def test_rr_take_profit_long(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_take_profit,
        )

        config = RiskConfig(take_profit_method="rr", take_profit_rr=2.0)
        result = calculate_take_profit(
            entry_price=100.0,
            stop_loss_price=98.0,
            direction=TradeDirection.LONG,
            config=config,
        )
        # Stop distance = 2, RR = 2, TP distance = 4
        assert result.tp_price == 104.0  # 100 + 4
        assert result.method == "rr"
        assert result.reward_risk_ratio == 2.0

    def test_rr_take_profit_short(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_take_profit,
        )

        config = RiskConfig(take_profit_method="rr", take_profit_rr=2.0)
        result = calculate_take_profit(
            entry_price=100.0,
            stop_loss_price=102.0,
            direction=TradeDirection.SHORT,
            config=config,
        )
        # Stop distance = 2, RR = 2, TP distance = 4
        assert result.tp_price == 96.0  # 100 - 4
        assert result.method == "rr"
        assert result.reward_risk_ratio == 2.0

    def test_fixed_take_profit_long(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_take_profit,
        )

        config = RiskConfig(take_profit_method="fixed", take_profit_fixed_pct=0.04)
        result = calculate_take_profit(
            entry_price=100.0,
            stop_loss_price=98.0,
            direction=TradeDirection.LONG,
            config=config,
        )
        assert result.tp_price == 104.0  # 100 * (1 + 0.04)
        assert result.method == "fixed"

    def test_fixed_take_profit_short(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_take_profit,
        )

        config = RiskConfig(take_profit_method="fixed", take_profit_fixed_pct=0.04)
        result = calculate_take_profit(
            entry_price=100.0,
            stop_loss_price=102.0,
            direction=TradeDirection.SHORT,
            config=config,
        )
        assert result.tp_price == 96.0  # 100 * (1 - 0.04)
        assert result.method == "fixed"

    def test_atr_mult_take_profit(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_take_profit,
        )

        config = RiskConfig(take_profit_method="atr_mult", atr_multiplier=4.0)
        result = calculate_take_profit(
            entry_price=100.0,
            stop_loss_price=98.0,
            atr=2.0,
            direction=TradeDirection.LONG,
            config=config,
        )
        # ATR mult: tp_distance = atr * atr_multiplier * 2 = 2 * 4 * 2 = 16
        # tp_price = entry + tp_distance = 100 + 16 = 116
        assert result.tp_price == 116.0
        assert result.method == "atr_mult"

    def test_invalid_prices(self):
        from agent.src.analysis.risk_manager import (
            TradeDirection,
            calculate_take_profit,
        )

        result = calculate_take_profit(
            entry_price=0,
            stop_loss_price=98.0,
            direction=TradeDirection.LONG,
        )
        assert result.tp_price == 0.0


class TestCalculateRiskParams:
    """Tests for calculate_risk_params function."""

    def test_comprehensive_params_long(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_risk_params,
        )

        config = RiskConfig(
            max_risk_per_trade=0.02,
            atr_multiplier=2.0,
            take_profit_method="rr",
            take_profit_rr=2.0,
        )
        result = calculate_risk_params(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            equity=100000.0,
            atr=2.0,
            config=config,
        )

        # SL: stop_distance = atr * atr_multiplier = 2 * 2 = 4
        # SL price = entry - stop_distance = 100 - 4 = 96
        # TP: tp_distance = stop_distance * rr_ratio = 4 * 2 = 8
        # TP price = entry + tp_distance = 100 + 8 = 108
        assert result.entry_price == 100.0
        assert result.direction == TradeDirection.LONG
        assert result.stop_loss.stop_price == 96.0
        assert result.take_profit.tp_price == 108.0
        assert result.risk_reward_ratio == 2.0
        assert result.position_size > 0
        assert result.atr == 2.0

    def test_comprehensive_params_short(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            TradeDirection,
            calculate_risk_params,
        )

        config = RiskConfig(
            max_risk_per_trade=0.02,
            atr_multiplier=2.0,
            take_profit_method="rr",
            take_profit_rr=2.0,
        )
        result = calculate_risk_params(
            entry_price=100.0,
            direction=TradeDirection.SHORT,
            equity=100000.0,
            atr=2.0,
            config=config,
        )

        # SL: stop_distance = atr * atr_multiplier = 2 * 2 = 4
        # SL price = entry + stop_distance = 100 + 4 = 104
        # TP: tp_distance = stop_distance * rr_ratio = 4 * 2 = 8
        # TP price = entry - tp_distance = 100 - 8 = 92
        assert result.direction == TradeDirection.SHORT
        assert result.stop_loss.stop_price == 104.0
        assert result.take_profit.tp_price == 92.0

    def test_without_config(self):
        from agent.src.analysis.risk_manager import (
            TradeDirection,
            calculate_risk_params,
        )

        result = calculate_risk_params(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            equity=100000.0,
            atr=2.0,
            risk_pct=0.02,
            atr_multiplier=2.0,
            rr_ratio=2.0,
        )

        assert result.entry_price == 100.0
        assert result.position_size > 0


class TestRiskManagerRiskParams:
    """Tests for RiskManager.calculate_risk_params method."""

    def test_calculate_risk_params_method(self):
        from agent.src.analysis.risk_manager import (
            RiskConfig,
            RiskManager,
            TradeDirection,
        )

        config = RiskConfig(
            atr_multiplier=2.0,
            take_profit_method="rr",
            take_profit_rr=2.0,
        )
        rm = RiskManager(
            config=config,
            initial_capital=100000.0,
            current_capital=100000.0,
        )

        result = rm.calculate_risk_params(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            atr=2.0,
        )

        # SL: 100 - (2 * 2) = 96
        # TP: 100 + (4 * 2) = 108
        assert result.entry_price == 100.0
        assert result.stop_loss.stop_price == 96.0
        assert result.take_profit.tp_price == 108.0
        assert result.position_size > 0


class TestRiskConfigValidation:
    """Additional tests for RiskConfig validation."""

    def test_stop_loss_method_validation(self):
        from agent.src.analysis.risk_manager import RiskConfig

        # Valid methods
        config1 = RiskConfig(stop_loss_method="atr")
        assert config1.stop_loss_method == "atr"

        config2 = RiskConfig(stop_loss_method="fixed_pct")
        assert config2.stop_loss_method == "fixed_pct"

        # Invalid method
        with pytest.raises(ValueError, match="stop_loss_method"):
            RiskConfig(stop_loss_method="invalid")

    def test_take_profit_method_validation(self):
        from agent.src.analysis.risk_manager import RiskConfig

        # Valid methods
        config1 = RiskConfig(take_profit_method="rr")
        assert config1.take_profit_method == "rr"

        config2 = RiskConfig(take_profit_method="fixed")
        assert config2.take_profit_method == "fixed"

        config3 = RiskConfig(take_profit_method="atr_mult")
        assert config3.take_profit_method == "atr_mult"

        # Invalid method
        with pytest.raises(ValueError, match="take_profit_method"):
            RiskConfig(take_profit_method="invalid")

    def test_default_config_values(self):
        from agent.src.analysis.risk_manager import RiskConfig

        config = RiskConfig()
        assert config.stop_loss_method == "atr"
        assert config.stop_loss_pct == 0.02
        assert config.take_profit_method == "rr"
        assert config.take_profit_rr == 2.0
        assert config.take_profit_fixed_pct == 0.04
        assert config.trailing_stop is False
        assert config.trailing_pct == 0.01
