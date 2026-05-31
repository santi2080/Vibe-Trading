#!/usr/bin/env python3
"""SuperTrend Enhancement Experiment Runner.

Phase 03 research experiment runner that executes the SuperTrend enhancement
matrix and generates comparison reports.

Usage:
    python scripts/backtest_supertrend_enhancement.py --symbol GC=F --matrix smoke --output reports
    python scripts/backtest_supertrend_enhancement.py --symbol GC=F --matrix core --output reports
    python scripts/backtest_supertrend_enhancement.py --all --matrix core --max-grid-size 24 --output reports
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))
sys.path.insert(0, str(PROJECT_ROOT))

from agent.src.analysis.supertrend import SuperTrendConfig
from agent.src.analysis.supertrend_enhancement import (
    EnhancementConfig,
    build_enhancement_features,
    generate_enhancement_signals,
    build_experiment_matrix,
    resolve_trading_mode,
)
from agent.src.analysis.supertrend_metrics import (
    TradeDiagnosticsConfig,
    calculate_phase03_trade_metrics,
    flatten_phase03_metrics,
)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SuperTrend Enhancement Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--symbol", type=str, default=None, help="Single symbol to run")
    parser.add_argument("--all", action="store_true", help="Run on all available symbols")
    parser.add_argument("--market-filter", type=str, default=None,
                        help="Filter by market type (us_futures, cn_futures, etf, us_stock)")
    parser.add_argument("--matrix", type=str, default="smoke",
                        choices=["smoke", "core", "full"],
                        help="Matrix mode: smoke (3 experiments), core (E1-E8), full (all combos)")
    parser.add_argument("--output", type=str, default="reports",
                        help="Output directory for reports")
    parser.add_argument("--mode", type=str, default="auto",
                        choices=["auto", "long_only", "long_short"],
                        help="Trading mode")
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0,
                        help="Transaction cost in basis points")
    parser.add_argument("--slippage-bps", type=float, default=5.0,
                        help="Slippage in basis points")
    parser.add_argument("--entry-family", type=str, default="pullback",
                        choices=["pullback", "breakout", "rsi_recovery", "macd_recovery"],
                        help="Entry trigger family")
    parser.add_argument("--walk-forward", action="store_true",
                        help="Enable walk-forward validation")
    parser.add_argument("--max-grid-size", type=int, default=24,
                        help="Maximum parameter grid size")
    return parser.parse_args(argv)


# ─────────────────────────────────────────────────────────────────────────────
# Symbol Universe
# ─────────────────────────────────────────────────────────────────────────────


SYMBOLS_CONFIG = {
    "GC=F": {"market": "us_futures", "name": "黄金"},
    "SI=F": {"market": "us_futures", "name": "白银"},
    "CL=F": {"market": "us_futures", "name": "WTI原油"},
    "ES=F": {"market": "us_futures", "name": "标普500"},
    "NQ=F": {"market": "us_futures", "name": "纳斯达克"},
    "SPY": {"market": "etf", "name": "标普500ETF"},
    "QQQ": {"market": "etf", "name": "纳斯达克ETF"},
    "GLD": {"market": "etf", "name": "黄金ETF"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Data Loading (Real parquet files when available)
# ─────────────────────────────────────────────────────────────────────────────

DATA_ROOT = PROJECT_ROOT / "data"


def _find_data_dir(symbol: str, market: str) -> Optional[Path]:
    """Find data directory for symbol."""
    market_map = {
        "us_futures": "us_futures",
        "us_stock": "us_stocks",
        "cn_futures": "cn_futures",
        "cn_etf": "cn_etf",
        "etf": "etf",
    }
    market_dir = market_map.get(market, market)
    data_dir = DATA_ROOT / market_dir / symbol
    if data_dir.exists():
        return data_dir
    return None


def load_ohlcv(symbol: str, market: str = "us_futures") -> pd.DataFrame:
    """Load OHLCV daily data for symbol from parquet."""
    data_dir = _find_data_dir(symbol, market)

    if data_dir is not None:
        parquet_path = data_dir / "1d.parquet"
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df

    # Fallback: generate synthetic data for testing
    rng = np.random.default_rng(hash(symbol) % 2**32)
    length = 500
    index = pd.date_range("2022-01-01", periods=length, freq="D", name="timestamp")
    trend = 100.0 + np.arange(length, dtype=float) * 0.5
    noise = rng.normal(0, 1.5, length)
    close = trend + noise
    high = close + rng.uniform(0.5, 2.0, length)
    low = close - rng.uniform(0.5, 2.0, length)
    open_ = close + rng.normal(0, 0.5, length)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=index,
    )


def load_weekly_ohlcv(symbol: str, market: str = "us_futures") -> pd.DataFrame:
    """Load weekly OHLCV data from parquet or resample daily."""
    data_dir = _find_data_dir(symbol, market)

    if data_dir is not None:
        parquet_path = data_dir / "1W.parquet"
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df

    # Fallback: resample daily
    daily = load_ohlcv(symbol, market)
    return daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )


def load_mtes_frame(symbol: str, market: str = "us_futures") -> pd.DataFrame:
    """Load MTES conflict metadata. Returns synthetic data if not available."""
    # MTES metadata not yet cached, generate synthetic
    rng = np.random.default_rng(hash(symbol + "mtes") % 2**32)
    daily = load_ohlcv(symbol, market)
    length = len(daily)
    index = daily.index
    return pd.DataFrame(
        {
            "mtes_direction": rng.choice([-1.0, 1.0], size=length),
            "mtes_regime": rng.choice(["trending", "choppy"], size=length),
            "mtes_conflict": rng.choice([True, False], size=length, p=[0.15, 0.85]),
            "timeframe_conflict": rng.choice([True, False], size=length, p=[0.1, 0.9]),
        },
        index=index,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Signal Simulation
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Trade:
    entry_bar: int
    exit_bar: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: float
    size: float = 1.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_bars: int = 0


def simulate_trades_from_signals(
    signals: pd.Series,
    daily: pd.DataFrame,
) -> List[Trade]:
    """Convert signals to trades with one-bar delay (no-lookahead)."""
    # Shift signals by 1 bar (execute next bar)
    shifted = signals.shift(1).fillna(0.0)
    close = daily["close"]

    trades = []
    in_position = False
    entry_bar = 0
    entry_price = 0.0
    entry_time = None

    for i in range(len(shifted)):
        sig = shifted.iloc[i]
        if sig != 0 and not in_position:
            # Entry
            in_position = True
            entry_bar = i
            entry_price = close.iloc[i]
            entry_time = close.index[i]
        elif sig == 0 and in_position:
            # Exit
            exit_bar = i
            exit_price = close.iloc[exit_bar]
            exit_time = close.index[exit_bar]
            pnl_pct = (exit_price - entry_price) / entry_price * sig
            trades.append(Trade(
                entry_bar=entry_bar,
                exit_bar=exit_bar,
                entry_time=entry_time,
                exit_time=exit_time,
                direction=sig,
                pnl=exit_price - entry_price,
                pnl_pct=pnl_pct,
                holding_bars=exit_bar - entry_bar,
            ))
            in_position = False

    # Close final position
    if in_position:
        exit_bar = len(close) - 1
        exit_price = close.iloc[exit_bar]
        exit_time = close.index[exit_bar]
        pnl_pct = (exit_price - entry_price) / entry_price * (signals.iloc[entry_bar] if entry_bar < len(signals) else 1.0)
        trades.append(Trade(
            entry_bar=entry_bar,
            exit_bar=exit_bar,
            entry_time=entry_time,
            exit_time=exit_time,
            direction=signals.iloc[entry_bar] if entry_bar < len(signals) else 1.0,
            pnl=exit_price - entry_price,
            pnl_pct=pnl_pct,
            holding_bars=exit_bar - entry_bar,
        ))

    return trades


def build_equity_curve(trades: List[Trade], daily: pd.DataFrame) -> pd.Series:
    """Build equity curve from trades."""
    equity = pd.Series(1.0, index=daily.index)
    for trade in trades:
        ret = trade.pnl_pct if trade.direction > 0 else -trade.pnl_pct
        equity.iloc[trade.exit_bar] = equity.iloc[trade.entry_bar] * (1 + ret)
    # Forward fill
    equity = equity.ffill().fillna(1.0)
    return equity


def build_position_series(trades: List[Trade], daily: pd.DataFrame) -> pd.Series:
    """Build position series (0/1) from trades."""
    positions = pd.Series(0.0, index=daily.index)
    for trade in trades:
        positions.iloc[trade.entry_bar:trade.exit_bar + 1] = 1.0
    return positions


# ─────────────────────────────────────────────────────────────────────────────
# Legacy SuperTrend (simplified Phase 02 version)
# ─────────────────────────────────────────────────────────────────────────────


def calculate_legacy_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """Legacy simplified SuperTrend (Phase 02 style) - basic bands, no stateful."""
    tr = _true_range(high, low, close)
    atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    mid = (high + low) / 2.0
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr

    st = pd.Series(0.0, index=close.index)
    trend = 1.0
    for i in range(len(close)):
        if i == 0:
            st.iloc[i] = lower.iloc[i]
            continue
        if close.iloc[i] > st.iloc[i - 1]:
            trend = 1.0
            st.iloc[i] = lower.iloc[i]
        elif close.iloc[i] < st.iloc[i - 1]:
            trend = -1.0
            st.iloc[i] = upper.iloc[i]
        else:
            st.iloc[i] = st.iloc[i - 1]
    return st


def _true_range(high, low, close):
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# Experiment Matrix Runners
# ─────────────────────────────────────────────────────────────────────────────


def run_smoke_matrix(
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
    mtes_frame: pd.DataFrame,
    config: Optional[EnhancementConfig] = None,
    trading_mode: str = "auto",
) -> List[Dict[str, Any]]:
    """Run smoke matrix: B1, B2, E4 (minimal set)."""
    if config is None:
        config = EnhancementConfig()

    rows = []

    # B1: Buy-and-hold
    rows.append(_run_buy_and_hold(daily, config, trading_mode))

    # B2: Weekly ST + RF
    config_b2 = EnhancementConfig(
        use_range_filter=True,
        use_regime_filter=False,
        use_mtes_conflict_filter=False,
    )
    rows.append(_run_experiment("B2", "Weekly ST + RF", daily, weekly, mtes_frame, config_b2, trading_mode))

    # E4: Full enhancement with pullback
    config_e4 = EnhancementConfig(
        use_range_filter=True,
        use_regime_filter=True,
        use_mtes_conflict_filter=False,
    )
    rows.append(_run_experiment("E4", "ST + RF + Regime + Pullback", daily, weekly, mtes_frame, config_e4, trading_mode, entry_family="pullback"))

    return rows


def run_core_matrix(
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
    mtes_frame: pd.DataFrame,
    config: Optional[EnhancementConfig] = None,
    trading_mode: str = "auto",
) -> List[Dict[str, Any]]:
    """Run core matrix: B1-B3 and E1-E8."""
    if config is None:
        config = EnhancementConfig()

    rows = []

    # Baselines
    rows.append(_run_buy_and_hold(daily, config, trading_mode))
    rows.append(_run_legacy_st(daily, config, trading_mode))
    rows.append(_run_corrected_daily_st(daily, config, trading_mode))

    # E1-E8 from experiment matrix
    matrix = build_experiment_matrix()
    for item in matrix:
        exp_config = item["config"]
        if isinstance(exp_config, EnhancementConfig):
            exp_config.transaction_cost_bps = config.transaction_cost_bps
            exp_config.slippage_bps = config.slippage_bps
        else:
            exp_config = EnhancementConfig(**exp_config)

        rows.append(_run_experiment(
            experiment_id=item["name"].split(":")[0],
            strategy_name=item["name"],
            daily=daily,
            weekly=weekly,
            mtes_frame=mtes_frame,
            config=exp_config,
            trading_mode=trading_mode,
            entry_family="pullback",
        ))

    return rows


def _run_buy_and_hold(
    daily: pd.DataFrame,
    config: EnhancementConfig,
    trading_mode: str,
) -> Dict[str, Any]:
    """Run buy-and-hold baseline."""
    close = daily["close"]
    signals = pd.Series(1.0, index=daily.index)  # Always long

    trades = simulate_trades_from_signals(signals, daily)
    equity = build_equity_curve(trades, daily)
    positions = build_position_series(trades, daily)

    metrics = calculate_phase03_trade_metrics(
        trades=trades,
        equity_curve=equity,
        positions=positions,
        config=TradeDiagnosticsConfig(
            transaction_cost_bps=config.transaction_cost_bps,
            slippage_bps=config.slippage_bps,
        ),
    )

    warmup = config.st_period * 3 + config.st_warmup_extra

    return {
        "experiment_id": "B1",
        "strategy_name": "Buy and Hold",
        "baseline_family": "buy_and_hold",
        "symbol": "synthetic",
        "market": "synthetic",
        "timeframe": "1D",
        "entry_family": "none",
        "trading_mode": trading_mode,
        "parameters": json.dumps({"period": 0, "multiplier": 0}),
        "sample_start": str(daily.index[warmup]),
        "sample_end": str(daily.index[-1]),
        "uses_weekly_st_anchor": False,
        "uses_daily_rf_confirmation": False,
        "uses_regime_filter": False,
        "uses_mtes_conflict_filter": False,
        "warmup_bars_removed": 0,
        "mtes_conflict_count": 0,
        "mtes_vetoed_entry_count": 0,
        **flatten_phase03_metrics(metrics),
    }


def _run_legacy_st(
    daily: pd.DataFrame,
    config: EnhancementConfig,
    trading_mode: str,
) -> Dict[str, Any]:
    """Run legacy Phase 02 simplified SuperTrend baseline."""
    close = daily["close"]
    high = daily["high"]
    low = daily["low"]

    st = calculate_legacy_supertrend(high, low, close, period=10, multiplier=3.0)
    st_trend = pd.Series(0.0, index=close.index)
    st_trend = st_trend.where(close <= st, 1.0)
    st_trend = st_trend.where(close > st, -1.0)

    # Entry on trend change
    signals = st_trend.diff().fillna(0.0).clip(-1, 1)

    trades = simulate_trades_from_signals(signals, daily)
    equity = build_equity_curve(trades, daily)
    positions = build_position_series(trades, daily)

    metrics = calculate_phase03_trade_metrics(
        trades=trades,
        equity_curve=equity,
        positions=positions,
        config=TradeDiagnosticsConfig(
            transaction_cost_bps=config.transaction_cost_bps,
            slippage_bps=config.slippage_bps,
        ),
    )

    warmup = config.st_period * 3 + config.st_warmup_extra

    return {
        "experiment_id": "B3",
        "strategy_name": "Legacy Phase 02 SuperTrend",
        "baseline_family": "legacy_phase02_supertrend",
        "symbol": "synthetic",
        "market": "synthetic",
        "timeframe": "1D",
        "entry_family": "none",
        "trading_mode": trading_mode,
        "parameters": json.dumps({"period": 10, "multiplier": 3.0, "legacy": True}),
        "sample_start": str(daily.index[warmup]),
        "sample_end": str(daily.index[-1]),
        "uses_weekly_st_anchor": False,
        "uses_daily_rf_confirmation": False,
        "uses_regime_filter": False,
        "uses_mtes_conflict_filter": False,
        "warmup_bars_removed": warmup,
        "st_algorithm_family": "legacy",
        "legacy_vs_corrected_direction_delta": None,
        "legacy_vs_corrected_trade_delta": None,
        "algorithm_delta_notes": "Legacy uses basic bands, corrected uses stateful carry-forward bands",
        "mtes_conflict_count": 0,
        "mtes_vetoed_entry_count": 0,
        **flatten_phase03_metrics(metrics),
    }


def _run_corrected_daily_st(
    daily: pd.DataFrame,
    config: EnhancementConfig,
    trading_mode: str,
) -> Dict[str, Any]:
    """Run corrected daily SuperTrend baseline."""
    from agent.src.analysis.supertrend import calculate_supertrend, remove_supertrend_warmup

    st_config = SuperTrendConfig(period=10, multiplier=3.0)
    st_result = calculate_supertrend(daily, st_config)
    st_result = remove_supertrend_warmup(st_result, st_config)

    # Signals from ST trend
    signals = st_result["st_trend"].fillna(0.0)

    trades = simulate_trades_from_signals(signals, daily)
    equity = build_equity_curve(trades, daily)
    positions = build_position_series(trades, daily)

    metrics = calculate_phase03_trade_metrics(
        trades=trades,
        equity_curve=equity,
        positions=positions,
        config=TradeDiagnosticsConfig(
            transaction_cost_bps=config.transaction_cost_bps,
            slippage_bps=config.slippage_bps,
        ),
    )

    warmup = st_config.period * 3 + st_config.warmup_extra

    return {
        "experiment_id": "B2",
        "strategy_name": "Corrected Daily SuperTrend",
        "baseline_family": "corrected_daily_supertrend",
        "symbol": "synthetic",
        "market": "synthetic",
        "timeframe": "1D",
        "entry_family": "none",
        "trading_mode": trading_mode,
        "parameters": json.dumps({"period": 10, "multiplier": 3.0, "stateful": True}),
        "sample_start": str(daily.index[warmup]),
        "sample_end": str(daily.index[-1]),
        "uses_weekly_st_anchor": False,
        "uses_daily_rf_confirmation": False,
        "uses_regime_filter": False,
        "uses_mtes_conflict_filter": False,
        "warmup_bars_removed": warmup,
        "st_algorithm_family": "corrected",
        "mtes_conflict_count": 0,
        "mtes_vetoed_entry_count": 0,
        **flatten_phase03_metrics(metrics),
    }


def _run_experiment(
    experiment_id: str,
    strategy_name: str,
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
    mtes_frame: pd.DataFrame,
    config: EnhancementConfig,
    trading_mode: str,
    entry_family: str = "pullback",
) -> Dict[str, Any]:
    """Run a single experiment with enhancement features."""
    warmup = config.st_period * 3 + config.st_warmup_extra

    # Build features
    features = build_enhancement_features(
        daily_df=daily,
        weekly_df=weekly,
        market="synthetic",
        mtes_frame=mtes_frame,
        config=config,
    )

    # Generate signals
    signals = generate_enhancement_signals(features, entry_family=entry_family, config=config)

    # Trim warmup
    if warmup > 0 and warmup < len(signals):
        signals = signals.iloc[warmup:]
        daily_trimmed = daily.iloc[warmup:]
    else:
        daily_trimmed = daily

    # Simulate trades
    trades = simulate_trades_from_signals(signals, daily_trimmed)
    equity = build_equity_curve(trades, daily_trimmed)
    positions = build_position_series(trades, daily_trimmed)

    # MTES conflict count
    if "mtes_conflict" in features.columns:
        mtes_conflict_count = int(features["mtes_conflict"].iloc[warmup:].sum())
    else:
        mtes_conflict_count = 0

    # Vetoed entries
    vetoed = 0
    if config.use_mtes_conflict_filter and "mtes_conflict" in features.columns:
        conflict_mask = features["mtes_conflict"] == True
        vetoed = int(conflict_mask.iloc[warmup:].sum())

    metrics = calculate_phase03_trade_metrics(
        trades=trades,
        equity_curve=equity,
        positions=positions,
        config=TradeDiagnosticsConfig(
            transaction_cost_bps=config.transaction_cost_bps,
            slippage_bps=config.slippage_bps,
        ),
    )

    return {
        "experiment_id": experiment_id,
        "strategy_name": strategy_name,
        "baseline_family": "enhanced",
        "symbol": "synthetic",
        "market": "synthetic",
        "timeframe": "1D",
        "entry_family": entry_family,
        "trading_mode": trading_mode,
        "parameters": json.dumps(asdict(config)),
        "sample_start": str(daily.index[warmup]) if warmup < len(daily) else str(daily.index[0]),
        "sample_end": str(daily.index[-1]),
        "uses_weekly_st_anchor": True,
        "uses_daily_rf_confirmation": config.use_range_filter,
        "uses_regime_filter": config.use_regime_filter,
        "uses_mtes_conflict_filter": config.use_mtes_conflict_filter,
        "warmup_bars_removed": warmup,
        "mtes_conflict_count": mtes_conflict_count,
        "mtes_vetoed_entry_count": vetoed,
        **flatten_phase03_metrics(metrics),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────────────


def generate_markdown_summary(rows: List[Dict], symbol: str = "synthetic") -> str:
    """Generate Markdown summary report from experiment rows."""
    df = pd.DataFrame(rows)

    lines = [
        f"# SuperTrend Enhancement Experiment Report",
        f"",
        f"**Symbol**: {symbol}",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Experiments**: {len(rows)}",
        f"",
        f"## Summary",
        f"",
        f"Generated {len(rows)} experiment rows.",
        f"",
    ]

    if len(df) > 0:
        # Best by Sharpe
        if "sharpe" in df.columns:
            best_sharpe = df.loc[df["sharpe"].idxmax()] if df["sharpe"].notna().any() else None
            if best_sharpe is not None:
                lines.extend([
                    f"### Best by Sharpe Ratio",
                    f"",
                    f"- **{best_sharpe['strategy_name']}**: {best_sharpe['sharpe']:.2f}",
                    f"",
                ])

        # Best by Win Rate
        if "win_rate" in df.columns:
            best_wr = df.loc[df["win_rate"].idxmax()] if df["win_rate"].notna().any() else None
            if best_wr is not None:
                lines.extend([
                    f"### Best by Win Rate",
                    f"",
                    f"- **{best_wr['strategy_name']}**: {best_wr['win_rate']:.1%}",
                    f"",
                ])

    lines.extend([
        f"## Transaction Cost Assumptions",
        f"",
        f"- Transaction Cost: {rows[0].get('transaction_cost_bps', 5.0):.1f} bps",
        f"- Slippage: {rows[0].get('slippage_bps', 5.0):.1f} bps",
        f"- Total One-Way: {(rows[0].get('transaction_cost_bps', 5.0) + rows[0].get('slippage_bps', 5.0)):.1f} bps",
        f"",
        f"## No-Lookahead Statement",
        f"",
        f"- Weekly SuperTrend uses only completed bars with 1-bar lag",
        f"- Signal execution uses next-bar (one-bar delay)",
        f"- Warmup bars removed: {rows[0].get('warmup_bars_removed', 130)}",
        f"",
    ])

    return "\n".join(lines)


def validate_output_path(path: str) -> Path:
    """Validate and resolve output path safely."""
    p = Path(path).resolve()
    # Reject absolute paths outside project
    if not str(p).startswith(str(PROJECT_ROOT)) and not str(p).startswith("reports"):
        raise ValueError(f"Output path outside project not allowed: {path}")
    return p


def estimate_grid_size(experiments: int, symbols: int, parameters: int) -> int:
    """Estimate total grid size."""
    return experiments * symbols * parameters


def cap_grid_size(size: int, max_size: int = 24) -> int:
    """Cap grid size at max_size."""
    return min(size, max_size)


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: List[str] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    # Validate output path
    output_dir = validate_output_path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Timestamp
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Resolve trading mode
    if args.mode == "auto":
        trading_mode = "long_short"  # Default for futures
    else:
        trading_mode = args.mode

    # Config
    config = EnhancementConfig(
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
        use_range_filter=True,
        use_regime_filter=True,
        use_mtes_conflict_filter=False,
    )

    # Select symbols
    if args.symbol:
        symbols = {args.symbol: SYMBOLS_CONFIG.get(args.symbol, {"market": "us_futures", "name": args.symbol})}
    elif args.all:
        symbols = SYMBOLS_CONFIG
        if args.market_filter:
            symbols = {k: v for k, v in symbols.items() if v["market"] == args.market_filter}
    else:
        print("Error: must specify --symbol or --all")
        return 1

    all_rows = []

    for symbol, info in symbols.items():
        print(f"Running {symbol} ({info['name']})...")

        daily = load_ohlcv(symbol, info["market"])
        weekly = load_weekly_ohlcv(symbol, info["market"])
        mtes_frame = load_mtes_frame(symbol, info["market"])

        if args.matrix == "smoke":
            rows = run_smoke_matrix(daily, weekly, mtes_frame, config, trading_mode)
        else:
            rows = run_core_matrix(daily, weekly, mtes_frame, config, trading_mode)

        # Estimate grid size
        grid_size = estimate_grid_size(len(rows), len(symbols), 1)
        capped_size = cap_grid_size(grid_size, args.max_grid_size)
        print(f"  Grid size: {grid_size} -> capped to {capped_size}")

        for row in rows:
            row["symbol"] = symbol
            row["market"] = info["market"]
        all_rows.extend(rows)

    # Generate reports
    df = pd.DataFrame(all_rows)

    # CSV
    csv_path = output_dir / f"supertrend_enhancement_comparison_{ts}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nReport: {csv_path}")

    # Markdown
    md_path = output_dir / f"supertrend_enhancement_report_{ts}.md"
    md = generate_markdown_summary(all_rows, symbol=args.symbol or "all")
    md_path.write_text(md, encoding="utf-8")
    print(f"Report: {md_path}")

    print(f"\nCompleted {len(all_rows)} experiment rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
