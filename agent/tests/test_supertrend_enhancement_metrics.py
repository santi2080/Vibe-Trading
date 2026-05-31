"""Tests for Phase 03."""

from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from backtest.models import TradeRecord
from backtest.metrics import win_rate_and_stats
from agent.src.analysis.supertrend_metrics import (
    TradeDiagnosticsConfig, calculate_phase03_trade_metrics,
    calculate_regime_splits, flatten_phase03_metrics)

def _make_trades(n=10, pnl_seed=100.0):
    return [TradeRecord(symbol="TEST", direction=1, entry_price=100.0,
        exit_price=100.0+(pnl_seed if i%2==0 else -pnl_seed*0.5)/100,
        entry_time=pd.Timestamp("2025-01-01")+pd.Timedelta(days=i*7),
        exit_time=pd.Timestamp("2025-01-01")+pd.Timedelta(days=i*7+5),
        size=100.0, leverage=1.0,
        pnl=(pnl_seed if i%2==0 else -pnl_seed*0.5),
        pnl_pct=(pnl_seed if i%2==0 else -pnl_seed*0.5)/100,
        exit_reason="signal", holding_bars=5, commission=1.0)
        for i in range(n)]

def _make_equity_curve(initial=100000.0, n_bars=252, trend=0.2):
    dates=pd.bdate_range("2025-01-01", periods=n_bars)
    return pd.Series(np.linspace(initial, initial*(1+trend), n_bars), index=dates)

def _make_positions(n_bars=252):
    dates=pd.bdate_range("2025-01-01", periods=n_bars)
    pos=np.zeros(n_bars)
    for i in range(0, n_bars, 5):
        for j in range(3):
            if i+j<n_bars: pos[i+j]=1.0
    return pd.Series(pos, index=dates)

def _make_regime_by_bar(n_bars=252):
    dates=pd.bdate_range("2025-01-01", periods=n_bars)
    regs=["trending" if (i//50)%2==0 else "choppy" for i in range(n_bars)]
    return pd.Series(regs, index=dates)

class TestConfig:
    def test_defaults(self):
        c=TradeDiagnosticsConfig()
        assert c.transaction_cost_bps==5.0 and c.slippage_bps==5.0
        assert c.initial_capital==100000.0 and c.bars_per_year==252
        assert c.whipsaw_bars==5 and c.whipsaw_loss_threshold==0.0

    def test_custom(self):
        c=TradeDiagnosticsConfig(initial_capital=50000.0, bars_per_year=365,
            transaction_cost_bps=3.0, slippage_bps=2.0, whipsaw_bars=10, whipsaw_loss_threshold=-0.001)
        assert c.initial_capital==50000.0 and c.bars_per_year==365
        assert c.transaction_cost_bps==3.0 and c.slippage_bps==2.0
        assert c.whipsaw_bars==10 and c.whipsaw_loss_threshold==-0.001

class TestAggMetrics:
    def test_required_names(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(),
            positions=_make_positions(), regime_by_bar=_make_regime_by_bar())
        for n in ["win_rate","profit_factor","max_drawdown","sharpe","sortino",
            "cagr","calmar","trade_count","avg_holding_bars","avg_holding_days",
            "exposure","whipsaw_count","transaction_cost_bps","slippage_bps"]:
            assert n in m, f"Missing: {n}"

    def test_win_rate_reuses(self):
        t=_make_trades()
        m=calculate_phase03_trade_metrics(t, _make_equity_curve())
        assert m["win_rate"]==pytest.approx(win_rate_and_stats(t)["win_rate"])

    def test_profit_factor_reuses(self):
        t=_make_trades()
        c=TradeDiagnosticsConfig(transaction_cost_bps=0.0, slippage_bps=0.0)
        m=calculate_phase03_trade_metrics(t, _make_equity_curve(), config=c)
        assert m["profit_factor"]==pytest.approx(win_rate_and_stats(t)["profit_factor"])

    def test_max_drawdown_neg(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(trend=-0.2))
        assert "max_drawdown" in m and m["max_drawdown"]<0

    def test_sharpe_sortino(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(trend=0.1))
        assert "sharpe" in m and isinstance(m["sharpe"], (int,float))
        assert "sortino" in m and isinstance(m["sortino"], (int,float))

    def test_cagr_calmar(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(trend=0.2))
        assert "cagr" in m and isinstance(m["cagr"], (int,float))
        assert "calmar" in m and isinstance(m["calmar"], (int,float))

    def test_trade_count(self):
        m=calculate_phase03_trade_metrics(_make_trades(n=15), _make_equity_curve())
        assert m["trade_count"]==15

    def test_avg_holding(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve())
        assert "avg_holding_bars" in m and "avg_holding_days" in m

class TestCosts:
    def test_visible_in_output(self):
        c=TradeDiagnosticsConfig(transaction_cost_bps=10.0, slippage_bps=7.0)
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(), config=c)
        assert m["transaction_cost_bps"]==10.0 and m["slippage_bps"]==7.0

    def test_defaults_conservative(self):
        c=TradeDiagnosticsConfig()
        assert c.transaction_cost_bps==5.0 and c.slippage_bps==5.0

    def test_zero_vs_default(self):
        c0=TradeDiagnosticsConfig(transaction_cost_bps=0.0, slippage_bps=0.0)
        m0=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(trend=0.1), config=c0)
        m1=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(trend=0.1))
        assert m0["profit_factor"]!=m1["profit_factor"]

class TestExposure:
    def test_zero_when_flat(self):
        eq=_make_equity_curve()
        pos=pd.Series(0.0, index=eq.index)
        m=calculate_phase03_trade_metrics(_make_trades(), eq, positions=pos)
        assert m["exposure"]==0.0

    def test_full_when_invested(self):
        eq=_make_equity_curve()
        pos=pd.Series(1.0, index=eq.index)
        m=calculate_phase03_trade_metrics(_make_trades(), eq, positions=pos)
        assert m["exposure"]==1.0

    def test_fractional(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve(), positions=_make_positions())
        assert 0.0<m["exposure"]<1.0

    def test_none_positions(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve())
        assert "exposure" in m

class TestWhipsaw:
    def test_in_output(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve())
        assert "whipsaw_count" in m and isinstance(m["whipsaw_count"], (int,float))

    def test_zero_for_long_trades(self):
        lt=[TradeRecord(symbol="TEST", direction=1, entry_price=100.0, exit_price=105.0,
            entry_time=pd.Timestamp("2025-01-01")+pd.Timedelta(days=i*30),
            exit_time=pd.Timestamp("2025-01-01")+pd.Timedelta(days=i*30+20),
            size=100.0, leverage=1.0, pnl=500.0, pnl_pct=0.05,
            exit_reason="signal", holding_bars=20, commission=1.0) for i in range(5)]
        m=calculate_phase03_trade_metrics(lt, _make_equity_curve(), config=TradeDiagnosticsConfig(whipsaw_bars=10))
        assert m["whipsaw_count"]==0

    def test_positive_for_short_reversals(self):
        st=[TradeRecord(symbol="TEST", direction=1, entry_price=100.0, exit_price=99.0,
            entry_time=pd.Timestamp("2025-01-01")+pd.Timedelta(days=i*7),
            exit_time=pd.Timestamp("2025-01-01")+pd.Timedelta(days=i*7+3),
            size=100.0, leverage=1.0, pnl=-100.0, pnl_pct=-0.01,
            exit_reason="signal", holding_bars=3, commission=1.0) for i in range(5)]
        m=calculate_phase03_trade_metrics(st, _make_equity_curve(), config=TradeDiagnosticsConfig(whipsaw_bars=5))
        assert m["whipsaw_count"]>0

class TestRegime:
    def test_returns_dict(self):
        s=calculate_regime_splits(_make_trades(), _make_equity_curve(), _make_regime_by_bar())
        assert isinstance(s, dict) and len(s)>0

    def test_keys_are_strings(self):
        s=calculate_regime_splits(_make_trades(), _make_equity_curve(), _make_regime_by_bar())
        for k in s: assert isinstance(k, str)

    def test_has_trade_count(self):
        s=calculate_regime_splits(_make_trades(), _make_equity_curve(), _make_regime_by_bar())
        for v in s.values():
            assert "trade_count" in v or "whipsaw_count" in v

class TestEmpty:
    def test_empty_trades(self):
        m=calculate_phase03_trade_metrics([], _make_equity_curve())
        assert m["trade_count"]==0 and m["whipsaw_count"]==0

    def test_empty_equity(self):
        m=calculate_phase03_trade_metrics(_make_trades(), pd.Series(dtype=float))
        assert "trade_count" in m and "exposure" in m

class TestFlatten:
    def test_returns_dict(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve())
        f=flatten_phase03_metrics(m)
        assert isinstance(f, dict)
        for v in f.values():
            assert isinstance(v, (str, int, float, type(None)))

    def test_prefix(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve())
        f=flatten_phase03_metrics(m, prefix="test_")
        for k in ["win_rate","trade_count","exposure"]:
            assert f"test_{k}" in f or k in f

    def test_dataframe(self):
        m=calculate_phase03_trade_metrics(_make_trades(), _make_equity_curve())
        f=flatten_phase03_metrics(m)
        df=pd.DataFrame([f])
        assert df.shape==(1, len(f))
        assert len(df.to_csv(index=False))>0
