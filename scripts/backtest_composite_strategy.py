#!/usr/bin/env python3
"""
Composite Strategy 实证测试

验证 CompositeTrendStrategy 与现有趋势适配器 (MTES v2, MTES v3, Enhanced SuperTrend) 的集成。

用法:
    python scripts/backtest_composite_strategy.py
    python scripts/backtest_composite_strategy.py --symbol EEM --timeframe 1d
    python scripts/backtest_composite_strategy.py --compare
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from src.data.watchlist import WatchlistReader
from src.data.watchlist_data_health import check_watchlist_data
from src.strategies.trend.mtes_v2 import MTESv2TrendStrategy, MTESv2TrendStrategyConfig
from src.strategies.trend.mtes_v3 import MTESv3TrendStrategy, MTESv3TrendStrategyConfig, MTESv3Config
from src.strategies.trend.enhanced_supertrend import EnhancedSuperTrendStrategy, EnhancedSuperTrendStrategyConfig
from src.strategies.trend.base import TrendStrategyConfig
from src.strategies.composite.trend_composite import CompositeTrendStrategy, CompositeTrendConfig
from src.strategies.composite.base import TradingSignal


def load_data(symbol: str, timeframe: str = "1d") -> pd.DataFrame | None:
    """Load parquet data for a symbol."""
    # Find data directory
    for market_dir in (PROJECT_ROOT / "data").iterdir():
        if not market_dir.is_dir():
            continue
        symbol_dir = market_dir / symbol
        if symbol_dir.exists():
            parquet_file = symbol_dir / f"{timeframe}.parquet"
            if parquet_file.exists():
                return pd.read_parquet(parquet_file)
    return None


def run_comparison(symbol: str, df: pd.DataFrame, show_all: bool = False) -> None:
    """Run all strategies and compare results."""
    print(f"\n{'='*70}")
    print(f"Composite Strategy 实证测试: {symbol}")
    print(f"数据: {len(df)} bars, {df.index[0]} ~ {df.index[-1]}")
    print(f"{'='*70}\n")

    # Create individual strategies
    mtes_v2 = MTESv2TrendStrategy(
        strategy_config=TrendStrategyConfig()
    )
    mtes_v3 = MTESv3TrendStrategy(
        strategy_config=TrendStrategyConfig()
    )
    supertrend = EnhancedSuperTrendStrategy(
        strategy_config=TrendStrategyConfig()
    )

    # Run individual strategies
    print("📊 单独策略结果:")
    print("-" * 70)

    result_v2 = mtes_v2.analyze(df)
    result_v3 = mtes_v3.analyze(df)
    result_st = supertrend.analyze(df)

    strategies = [
        ("MTES v2", result_v2),
        ("MTES v3", result_v3),
        ("SuperTrend", result_st),
    ]

    for name, result in strategies:
        print(f"  {name:12} | {result.direction:6} | "
              f"score={result.signed_score:6.1f} | "
              f"conf={result.confidence:.2f} | "
              f"status={result.status}")

    # Create composite strategy
    print(f"\n🔗 组合策略结果:")
    print("-" * 70)

    composite = CompositeTrendStrategy(
        sources=[mtes_v2, mtes_v3, supertrend],
        strategy_config=CompositeTrendConfig(name="composite_mtes_supertrend")
    )

    composite_signal = composite.analyze(df)

    print(f"  Composite     | {composite_signal.direction:6} | "
          f"score={composite_signal.signal_score:6.1f} | "
          f"conf={composite_signal.confidence:.2f} | "
          f"status={composite_signal.status}")
    print(f"               | readiness={composite_signal.readiness}")

    # Show details
    if show_all:
        print(f"\n📋 详细信号信息:")
        print("-" * 70)
        print(f"  方向: {composite_signal.direction}")
        print(f"  状态: {composite_signal.status}")
        print(f"  就绪度: {composite_signal.readiness}")
        print(f"  信号强度: {composite_signal.signal_score}")
        print(f"  置信度: {composite_signal.confidence:.4f}")
        print(f"  成分: {composite_signal.components}")
        print(f"  原因: {composite_signal.reasons}")
        print(f"  警告: {composite_signal.warnings}")
        print(f"  来源: {list(composite_signal.source_results.keys())}")

    # Summary
    print(f"\n📈 信号汇总:")
    print("-" * 70)
    print(f"  最终信号: {composite_signal.direction} ({composite_signal.status})")
    print(f"  综合强度: {composite_signal.signal_score:.1f}/100")
    print(f"  置信度: {composite_signal.confidence:.1%}")
    print(f"  可执行: {'✅ 是' if composite_signal.is_valid else '❌ 否'}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Composite Strategy 实证测试")
    parser.add_argument("--symbol", default="EEM", help="品种代码 (default: EEM)")
    parser.add_argument("--timeframe", default="1d", help="时间周期 (default: 1d)")
    parser.add_argument("--compare", action="store_true", help="比较所有品种")
    parser.add_argument("--show-all", action="store_true", help="显示完整详细信息")
    args = parser.parse_args()

    if args.compare:
        # Compare multiple symbols
        symbols = ["EEM", "CIBR", "IWM"]
        for sym in symbols:
            df = load_data(sym, args.timeframe)
            if df is not None:
                run_comparison(sym, df, show_all=args.show_all)
            else:
                print(f"⚠️  未找到 {sym} 数据")
    else:
        # Single symbol
        df = load_data(args.symbol, args.timeframe)
        if df is None:
            print(f"❌ 错误: 未找到 {args.symbol} 的数据")
            print(f"   请先运行数据下载或检查数据路径")
            sys.exit(1)

        run_comparison(args.symbol, df, show_all=args.show_all)


if __name__ == "__main__":
    main()
