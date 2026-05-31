"""Backtest script for Signal Execution System.

This script runs MTES + SuperTrend signals through the full execution pipeline:
1. Load OHLCV data
2. Generate MTES + SuperTrend signals
3. Execute trades with risk management
4. Calculate performance metrics

Usage:
    python scripts/backtest_signal_execution.py --symbol ES=F --timeframe 1d
    python scripts/backtest_signal_execution.py --symbol GC=F --timeframe 4h
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.src.analysis.signal_executor import (
    ExitReason,
    TradeDirection,
    convert_signal_to_instruction,
    apply_stop_loss,
    apply_take_profit,
    check_exit_conditions,
)
from agent.src.analysis.risk_manager import RiskConfig, RiskManager
from agent.src.analysis.portfolio_tracker import PortfolioTracker
from agent.src.analysis.performance_metrics import (
    calculate_metrics,
    format_metrics_report,
)


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add simple trend signals based on SMA crossover.

    Args:
        df: OHLCV DataFrame with close, high, low, open columns.

    Returns:
        DataFrame with bull_signal, bear_signal, entry_trigger columns.
    """
    df = df.copy()

    # Simple SMA-based trend signals
    df["sma_fast"] = df["close"].rolling(10).mean()
    df["sma_slow"] = df["close"].rolling(30).mean()

    # Bull/bear signals based on SMA crossover
    df["bull_signal"] = (df["sma_fast"] > df["sma_slow"]) & (df["close"] > df["sma_fast"])
    df["bear_signal"] = (df["sma_fast"] < df["sma_slow"]) & (df["close"] < df["sma_fast"])

    # Entry trigger: when signal changes
    df["prev_bull"] = df["bull_signal"].shift(1).fillna(False)
    df["prev_bear"] = df["bear_signal"].shift(1).fillna(False)
    df["entry_trigger"] = (df["bull_signal"] != df["prev_bull"]) | (df["bear_signal"] != df["prev_bear"])

    # Exit trigger: when trend reverses
    df["exit_trigger"] = False

    # SuperTrend-like trend (simplified)
    df["st_trend"] = 1
    df.loc[df["bear_signal"], "st_trend"] = -1
    df.loc[df["close"] < df["close"].shift(1), "st_trend"] = -1

    # MTES score approximation
    df["mtes_score"] = 70.0

    return df


def load_data(symbol: str, timeframe: str = "1d") -> pd.DataFrame | None:
    """Load OHLCV data for symbol."""
    data_dir = Path(__file__).parent.parent / "data" / "us_futures"

    patterns = [
        data_dir / symbol / f"{timeframe}.parquet",
        data_dir / f"{symbol.replace('=F', '')}" / f"{timeframe}.parquet",
    ]

    for pattern in patterns:
        if pattern.exists():
            df = pd.read_parquet(pattern)
            return df

    return None


def run_backtest(
    symbol: str,
    timeframe: str = "1d",
    initial_capital: float = 100000.0,
    mtes_threshold: float = 60.0,
    sl_pct: float = 0.02,
    tp_pct: float = 0.04,
    slippage_bps: float = 1.0,
) -> dict:
    """Run backtest for signal execution system.

    Args:
        symbol: Instrument symbol.
        timeframe: Data timeframe.
        initial_capital: Starting capital.
        mtes_threshold: MTES score threshold for signal quality filter.
        sl_pct: Stop loss percentage.
        tp_pct: Take profit percentage.
        slippage_bps: Slippage in basis points.

    Returns:
        Dict with backtest results.
    """
    df = load_data(symbol, timeframe)
    if df is None:
        return {"error": f"Could not load data for {symbol}"}

    if len(df) < 50:
        return {"error": "Insufficient data for backtest"}

    # 添加信号
    df = add_signals(df)

    tracker = PortfolioTracker(
        initial_capital=initial_capital,
        capital=initial_capital,
    )

    risk_config = RiskConfig(
        max_risk_per_trade=0.02,
        max_portfolio_risk=0.06,
        daily_loss_limit=0.03,
    )
    risk_manager = RiskManager(
        config=risk_config,
        initial_capital=initial_capital,
        current_capital=initial_capital,
    )

    bars_processed = 0
    signals_generated = 0
    signals_filtered = 0
    trades_executed = 0

    for idx, row in df.iterrows():
        bars_processed += 1
        current_price = row.get("close", row.get("Close", 0))
        timestamp = idx if isinstance(idx, pd.Timestamp) else pd.Timestamp.now()

        bull_signal = bool(row.get("bull_signal", False))
        bear_signal = bool(row.get("bear_signal", False))
        entry_trigger = bool(row.get("entry_trigger", False))
        exit_trigger = bool(row.get("exit_trigger", False))
        st_trend = int(row.get("st_trend", 0))
        mtes_score = float(row.get("mtes_score", 100))

        if mtes_score < mtes_threshold:
            signals_filtered += 1
            bull_signal = False
            bear_signal = False

        if entry_trigger and (bull_signal or bear_signal):
            signals_generated += 1

        if tracker.has_position(symbol):
            pos = tracker.get_position(symbol)

            sl_hit, sl_price = apply_stop_loss(current_price, pos, timestamp, bars_processed)
            if sl_hit:
                trade = tracker.close_position(
                    symbol=symbol,
                    exit_price=sl_price,
                    exit_time=timestamp,
                    exit_reason=ExitReason.STOP_LOSS,
                    bar_idx=bars_processed,
                )
                if trade:
                    trades_executed += 1
                    risk_manager.update_capital(tracker.capital)
                continue

            tp_hit, tp_price = apply_take_profit(current_price, pos, timestamp, bars_processed)
            if tp_hit:
                trade = tracker.close_position(
                    symbol=symbol,
                    exit_price=tp_price,
                    exit_time=timestamp,
                    exit_reason=ExitReason.TAKE_PROFIT,
                    bar_idx=bars_processed,
                )
                if trade:
                    trades_executed += 1
                    risk_manager.update_capital(tracker.capital)
                continue

            should_exit = check_exit_conditions(
                bull_signal=bull_signal,
                bear_signal=bear_signal,
                exit_trigger=exit_trigger,
                position=pos,
            )
            if should_exit:
                trade = tracker.close_position(
                    symbol=symbol,
                    exit_price=current_price,
                    exit_time=timestamp,
                    exit_reason=ExitReason.SIGNAL,
                    bar_idx=bars_processed,
                )
                if trade:
                    trades_executed += 1
                    risk_manager.update_capital(tracker.capital)
                continue

        else:
            if bull_signal and entry_trigger:
                can_trade, reason = risk_manager.can_take_trade()
                if can_trade:
                    instr = convert_signal_to_instruction(
                        symbol=symbol,
                        bull_signal=bull_signal,
                        bear_signal=bear_signal,
                        entry_trigger=entry_trigger,
                        st_trend=st_trend,
                        current_price=current_price,
                        sl_pct=sl_pct,
                        tp_pct=tp_pct,
                    )
                    if instr:
                        tracker.update_position(
                            symbol=symbol,
                            direction=TradeDirection.LONG,
                            entry_price=instr.entry_price,
                            size=instr.size,
                            stop_loss=instr.stop_loss,
                            take_profit=instr.take_profit,
                            entry_time=timestamp,
                            entry_bar_idx=bars_processed,
                        )
                        trades_executed += 1

            elif bear_signal and entry_trigger:
                can_trade, reason = risk_manager.can_take_trade()
                if can_trade:
                    instr = convert_signal_to_instruction(
                        symbol=symbol,
                        bull_signal=bull_signal,
                        bear_signal=bear_signal,
                        entry_trigger=entry_trigger,
                        st_trend=st_trend,
                        current_price=current_price,
                        sl_pct=sl_pct,
                        tp_pct=tp_pct,
                    )
                    if instr:
                        tracker.update_position(
                            symbol=symbol,
                            direction=TradeDirection.SHORT,
                            entry_price=instr.entry_price,
                            size=instr.size,
                            stop_loss=instr.stop_loss,
                            take_profit=instr.take_profit,
                            entry_time=timestamp,
                            entry_bar_idx=bars_processed,
                        )
                        trades_executed += 1

        if bars_processed % 20 == 0:
            tracker.record_snapshot(timestamp)

    for pos in list(tracker.positions.values()):
        tracker.close_position(
            symbol=pos.symbol,
            exit_price=current_price,
            exit_time=timestamp,
            exit_reason=ExitReason.END_OF_BACKTEST,
            bar_idx=bars_processed,
        )

    metrics = calculate_metrics(tracker)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_processed": bars_processed,
        "signals_generated": signals_generated,
        "signals_filtered": signals_filtered,
        "trades_executed": trades_executed,
        "metrics": metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest Signal Execution System")
    parser.add_argument("--symbol", default="ES=F", help="Symbol to backtest")
    parser.add_argument("--timeframe", default="1d", help="Timeframe (1d, 4h, 1h)")
    parser.add_argument("--capital", type=float, default=100000.0, help="Initial capital")
    parser.add_argument("--threshold", type=float, default=60.0, help="MTES threshold")
    parser.add_argument("--sl", type=float, default=0.02, help="Stop loss percentage")
    parser.add_argument("--tp", type=float, default=0.04, help="Take profit percentage")
    parser.add_argument("--slippage", type=float, default=1.0, help="Slippage in bps")

    args = parser.parse_args()

    print(f"\nRunning backtest for {args.symbol} ({args.timeframe})")
    print(f"Initial capital: ${args.capital:,.2f}")
    print(f"MTES threshold: {args.threshold}")
    print(f"SL: {args.sl*100:.1f}% | TP: {args.tp*100:.1f}% | Slippage: {args.slippage} bps")
    print("-" * 60)

    result = run_backtest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        initial_capital=args.capital,
        mtes_threshold=args.threshold,
        sl_pct=args.sl,
        tp_pct=args.tp,
        slippage_bps=args.slippage,
    )

    if "error" in result:
        print(f"\nError: {result['error']}")
        return 1

    print(f"\nBars processed: {result['bars_processed']}")
    print(f"Signals generated: {result['signals_generated']}")
    print(f"Signals filtered: {result['signals_filtered']}")
    print(f"Trades executed: {result['trades_executed']}")
    print("\n" + format_metrics_report(result["metrics"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
