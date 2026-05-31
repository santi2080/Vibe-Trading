"""Phase 03 SuperTrend trading diagnostics and metrics helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backtest.metrics import calc_metrics, win_rate_and_stats
from backtest.models import TradeRecord


@dataclass
class TradeDiagnosticsConfig:
    initial_capital: float = 100_000.0
    bars_per_year: int = 252
    transaction_cost_bps: float = 5.0
    slippage_bps: float = 5.0
    whipsaw_bars: int = 5
    whipsaw_loss_threshold: float = 0.0


def _count_whipsaws(trades, config):
    return sum(
        1 for t in trades
        if t.holding_bars <= config.whipsaw_bars and t.pnl_pct <= config.whipsaw_loss_threshold
    )


def _calc_exposure(positions):
    if positions is None or len(positions) == 0:
        return 0.0
    return float(positions.clip(upper=1.0).sum() / len(positions))


def _apply_costs(trades, config):
    bps = config.transaction_cost_bps + config.slippage_bps
    cost_pct = bps / 10_000.0
    return [
        replace(t, pnl=t.pnl - t.size * cost_pct, pnl_pct=t.pnl_pct - cost_pct)
        for t in trades
    ]


def calculate_phase03_trade_metrics(
    trades,
    equity_curve,
    positions=None,
    regime_by_bar=None,
    config=None,
):
    if config is None:
        config = TradeDiagnosticsConfig()

    adj_trades = _apply_costs(trades, config)
    trade_stats = win_rate_and_stats(adj_trades)

    base = calc_metrics(
        equity_curve=equity_curve,
        trades=adj_trades,
        initial_cash=config.initial_capital,
        bars_per_year=config.bars_per_year,
    )

    return {
        "win_rate": trade_stats["win_rate"],
        "profit_factor": trade_stats["profit_factor"],
        "max_drawdown": base["max_drawdown"],
        "sharpe": base["sharpe"],
        "sortino": base["sortino"],
        "cagr": base["annual_return"],
        "calmar": base["calmar"],
        "trade_count": len(trades),
        "avg_holding_bars": trade_stats["avg_holding_bars"],
        "avg_holding_days": trade_stats["avg_holding_bars"],
        "exposure": _calc_exposure(positions),
        "whipsaw_count": _count_whipsaws(trades, config),
        "transaction_cost_bps": config.transaction_cost_bps,
        "slippage_bps": config.slippage_bps,
    }


def calculate_regime_splits(trades, equity_curve, regime_by_bar, config=None):
    if config is None:
        config = TradeDiagnosticsConfig()

    if regime_by_bar is None or len(trades) == 0:
        return {}

    regime_map = dict(regime_by_bar.items())

    regime_groups: Dict[str, list] = {}
    for t in trades:
        reg = regime_map.get(t.entry_time)
        if reg is not None:
            regime_groups.setdefault(reg, []).append(t)

    result = {}
    for regime, reg_trades in regime_groups.items():
        reg_metrics = calculate_phase03_trade_metrics(
            reg_trades, equity_curve, config=config
        )
        result[regime] = {
            "trade_count": reg_metrics["trade_count"],
            "whipsaw_count": reg_metrics["whipsaw_count"],
            "win_rate": reg_metrics["win_rate"],
            "profit_factor": reg_metrics["profit_factor"],
        }

    return result


def flatten_phase03_metrics(metrics, prefix=""):
    flat = {}
    for key, value in metrics.items():
        prefixed_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"regime_{prefixed_key}_{sub_key}"] = sub_value
        else:
            flat[prefixed_key] = value
    return flat
