#!/usr/bin/env python3
"""
MTES vs SuperTrend 趋势判断准确性诊断

测试维度：
1. 方向准确率：信号发出后价格是否按预期移动
2. 信号领先/滞后：信号是否提前于价格反转
3. 信号持续性：信号的持续时间
4. 噪音过滤：假信号比例

用法：
    python scripts/diagnose_mtes_vs_supertrend.py
    python scripts/diagnose_mtes_vs_supertrend.py --market 贵金属
    python scripts/diagnose_mtes_vs_supertrend.py --symbol GC=F
"""

import argparse
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from src.analysis.major_trend_evaluator import MajorTrendEvaluator, TrendState


# ──────────────────────────────────────────────────────────────────
# SuperTrend 实现
# ──────────────────────────────────────────────────────────────────

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """计算 SuperTrend 信号"""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)

    # ATR
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr1[0] = high[0] - low[0]
    tr2[0] = 0
    tr3[0] = 0
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = pd.Series(tr).rolling(window=period).mean().values

    # 基础带
    hl_avg = (high + low) / 2
    basic_ub = hl_avg + multiplier * atr
    basic_lb = hl_avg - multiplier * atr

    # 最终带和方向
    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()
    direction = np.zeros(n)

    # 初始化：假设多头
    direction[period] = 1

    for i in range(period + 1, n):
        # 上轨
        if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i - 1]

        # 下轨
        if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i - 1]

        # 方向
        if direction[i - 1] == 1:  # 多头
            if close[i] < final_ub[i]:
                direction[i] = -1
            else:
                direction[i] = 1
        else:  # 空头
            if close[i] > final_lb[i]:
                direction[i] = 1
            else:
                direction[i] = -1

    return pd.Series(direction, index=df.index)


def calculate_mtes(df: pd.DataFrame, asset_class: str = "futures") -> Tuple[pd.Series, pd.Series]:
    """计算 MTES 信号和状态

    Returns:
        (direction, score) - 方向信号和评分
    """
    evaluator = MajorTrendEvaluator()
    directions = []
    scores = []

    warmup = 200  # MTES 需要足够数据

    for i in range(len(df)):
        if i < warmup:
            directions.append(0)
            scores.append(np.nan)
        else:
            window = df.iloc[:i+1].copy()
            try:
                result = evaluator.evaluate(
                    window,
                    asset_class=asset_class,
                    base_timeframe="1d",
                    higher_timeframe_name="1w",
                )
                # 映射状态到方向
                if result.direction == "BULL" and result.trend_state in ["BULL_STRONG", "BULL_CONFIRMED", "BULL_EARLY"]:
                    directions.append(1)
                elif result.direction == "BEAR" and result.trend_state in ["BEAR_STRONG", "BEAR_CONFIRMED", "BEAR_EARLY"]:
                    directions.append(-1)
                else:
                    directions.append(0)
                scores.append(result.trend_score)
            except:
                directions.append(0)
                scores.append(np.nan)

    return pd.Series(directions, index=df.index), pd.Series(scores, index=df.index)


# ──────────────────────────────────────────────────────────────────
# 诊断指标
# ──────────────────────────────────────────────────────────────────

@dataclass
class DiagnosticMetrics:
    """诊断指标"""
    indicator: str
    symbol: str
    total_signals: int
    correct_direction: int  # 方向正确次数
    direction_accuracy: float  # 方向准确率
    avg_lead_bars: float  # 平均领先/滞后 K 线数
    avg_holding_bars: float  # 平均持仓 K 线数
    false_signal_rate: float  # 假信号率（5根K线内反转）
    avg_return_per_signal: float  # 每信号平均收益


def diagnose_indicator(
    df: pd.DataFrame,
    direction: pd.Series,
    indicator: str,
    symbol: str,
    holding_window: int = 20
) -> DiagnosticMetrics:
    """诊断单个指标的趋势判断准确性"""

    signals = []
    returns = []

    # 找到所有信号切换点
    prev_signal = 0
    for i in range(len(df) - holding_window):
        curr_signal = direction.iloc[i]
        if curr_signal != prev_signal and curr_signal != 0:
            # 信号切换，记录入场点
            entry_price = df["close"].iloc[i]
            entry_idx = i

            # 计算未来 holding_window 根 K 线的收益
            exit_price = df["close"].iloc[min(i + holding_window, len(df) - 1)]
            ret = (exit_price - entry_price) / entry_price * 100 if curr_signal == 1 else (entry_price - exit_price) / entry_price * 100

            # 判断方向是否正确
            correct = ret > 0

            # 检查假信号（5根K线内反转）
            false_signal = False
            if i + 5 < len(df):
                future_signal = direction.iloc[i+5]
                if future_signal == -curr_signal:
                    false_signal = True

            signals.append({
                "entry_idx": entry_idx,
                "direction": curr_signal,
                "entry_price": entry_price,
                "return": ret,
                "correct": correct,
                "false_signal": false_signal,
            })

            prev_signal = curr_signal

        # 如果之前有持仓但信号消失，记录持仓时间
        elif curr_signal == 0 and prev_signal != 0:
            holding_bars = i - entry_idx
            returns.append(holding_bars)
            prev_signal = 0

    # 计算指标
    total_signals = len(signals)
    if total_signals == 0:
        return DiagnosticMetrics(
            indicator=indicator,
            symbol=symbol,
            total_signals=0,
            correct_direction=0,
            direction_accuracy=0.0,
            avg_lead_bars=0.0,
            avg_holding_bars=0.0,
            false_signal_rate=0.0,
            avg_return_per_signal=0.0,
        )

    correct_count = sum(1 for s in signals if s["correct"])
    false_count = sum(1 for s in signals if s["false_signal"])
    avg_return = np.mean([s["return"] for s in signals])

    return DiagnosticMetrics(
        indicator=indicator,
        symbol=symbol,
        total_signals=total_signals,
        correct_direction=correct_count,
        direction_accuracy=correct_count / total_signals * 100,
        avg_lead_bars=0.0,  # 简化版未计算
        avg_holding_bars=np.mean(returns) if returns else 0.0,
        false_signal_rate=false_count / total_signals * 100,
        avg_return_per_signal=avg_return,
    )


# ──────────────────────────────────────────────────────────────────
# 数据加载
# ──────────────────────────────────────────────────────────────────

def load_data(symbol: str) -> pd.DataFrame | None:
    """从本地 Parquet 加载数据"""
    sym = symbol.upper()

    candidates = []
    if "=" in sym:
        base = sym.split("=")[0]
        candidates += [
            PROJECT_ROOT / "data" / "us_futures" / sym / "1d.parquet",
            PROJECT_ROOT / "data" / "us_futures" / f"{base}=F" / "1d.parquet",
        ]
    else:
        candidates += [
            PROJECT_ROOT / "data" / "us_futures" / sym / "1d.parquet",
            PROJECT_ROOT / "data" / "etf" / sym / "1d.parquet",
            PROJECT_ROOT / "data" / "etf" / sym / "1W.parquet",
        ]

    for path in candidates:
        if path.exists():
            df = pd.read_parquet(path)
            if not isinstance(df.index, pd.DatetimeIndex):
                if "timestamp" in df.columns:
                    df = df.set_index("timestamp")
                elif "datetime" in df.columns:
                    df = df.set_index("datetime")
            df = df.sort_index()

            # 确保列名小写
            df.columns = [c.lower() for c in df.columns]

            # 只保留需要的列
            cols = ["open", "high", "low", "close", "volume"]
            df = df[[c for c in cols if c in df.columns]]

            return df

    return None


# ──────────────────────────────────────────────────────────────────
# 市场配置
# ──────────────────────────────────────────────────────────────────

MARKETS = {
    "贵金属": ["GC=F", "SI=F"],
    "股指期货": ["ES=F", "NQ=F", "YM=F"],
    "原油": ["CL=F", "NG=F"],
    "行业ETF": ["XLK", "XLF", "XLE", "XLV"],
}


# ──────────────────────────────────────────────────────────────────
# 主程序
# ──────────────────────────────────────────────────────────────────

def run_diagnostic(symbol: str, holding: int = 20) -> Tuple[DiagnosticMetrics, DiagnosticMetrics]:
    """对单个品种运行诊断"""
    df = load_data(symbol)
    if df is None or len(df) < 250:
        print(f"  ⚠️ 数据不足: {symbol}")
        return None, None

    print(f"  📊 {symbol}: {len(df)} 根日线 ({df.index[0].date()} ~ {df.index[-1].date()})")

    # 计算指标
    st_direction = calculate_supertrend(df)
    mtes_direction, mtes_score = calculate_mtes(df)

    # 诊断
    st_metrics = diagnose_indicator(df, st_direction, "SuperTrend", symbol, holding)
    mtes_metrics = diagnose_indicator(df, mtes_direction, "MTES", symbol, holding)

    return st_metrics, mtes_metrics


def print_result(metrics: DiagnosticMetrics):
    """打印诊断结果"""
    if metrics.total_signals == 0:
        print(f"    {metrics.indicator:<15} 无交易信号")
        return

    icon = "🥇" if metrics.direction_accuracy >= 70 else "🥈" if metrics.direction_accuracy >= 50 else "❌"
    print(f"    {icon} {metrics.indicator:<15} 信号:{metrics.total_signals:>2} 方向准确率:{metrics.direction_accuracy:>5.1f}% "
          f"假信号:{metrics.false_signal_rate:>5.1f}% 均收益:{metrics.avg_return_per_signal:>+6.2f}%")


def main():
    parser = argparse.ArgumentParser(description="MTES vs SuperTrend 趋势判断准确性诊断")
    parser.add_argument("--market", choices=list(MARKETS.keys()), help="指定市场")
    parser.add_argument("--symbol", help="指定品种")
    parser.add_argument("--holding", type=int, default=20, help="持仓窗口（默认20根日线）")
    parser.add_argument("--all-markets", action="store_true", help="测试所有市场")
    args = parser.parse_args()

    print("=" * 70)
    print("MTES vs SuperTrend 趋势判断准确性诊断".center(60))
    print("=" * 70)
    print(f"持仓窗口: {args.holding} 根日线")

    all_results = {}

    # 选择要测试的品种
    if args.symbol:
        symbols = [args.symbol]
    elif args.market:
        symbols = MARKETS[args.market]
    elif args.all_markets:
        symbols = [s for symbols in MARKETS.values() for s in symbols]
    else:
        symbols = ["GC=F", "ES=F", "CL=F"]  # 默认测试

    for symbol in symbols:
        print(f"\n{'─' * 50}")
        print(f"  {symbol}")
        print(f"{'─' * 50}")

        st_m, mtes_m = run_diagnostic(symbol, args.holding)

        if st_m and mtes_m:
            print_result(st_m)
            print_result(mtes_m)
            all_results[symbol] = (st_m, mtes_m)

    # 汇总
    if all_results:
        print(f"\n{'=' * 70}")
        print("汇总".center(60))
        print(f"{'=' * 70}")

        print(f"\n{'品种':<10} {'指标':<12} {'信号数':<6} {'方向准确率':<10} {'假信号率':<10} {'均收益':<10}")
        print(f"{'─' * 60}")

        st_avg_acc, mtes_avg_acc = [], []
        st_avg_false, mtes_avg_false = [], []
        st_avg_ret, mtes_avg_ret = [], []

        for symbol, (st_m, mtes_m) in all_results.items():
            if st_m.total_signals > 0:
                st_avg_acc.append(st_m.direction_accuracy)
                st_avg_false.append(st_m.false_signal_rate)
                st_avg_ret.append(st_m.avg_return_per_signal)
            if mtes_m.total_signals > 0:
                mtes_avg_acc.append(mtes_m.direction_accuracy)
                mtes_avg_false.append(mtes_m.false_signal_rate)
                mtes_avg_ret.append(mtes_m.avg_return_per_signal)

            # 标记最佳
            best = "◀BEST"
            if st_m.total_signals > 0 and mtes_m.total_signals > 0:
                if st_m.direction_accuracy >= mtes_m.direction_accuracy:
                    print(f"{symbol:<10} SuperTrend {st_m.total_signals:>4}      {st_m.direction_accuracy:>7.1f}%   "
                          f"{st_m.false_signal_rate:>7.1f}%   {st_m.avg_return_per_signal:>+7.2f}%")
                    print(f"{'':10} MTES        {mtes_m.total_signals:>4}      {mtes_m.direction_accuracy:>7.1f}%   "
                          f"{mtes_m.false_signal_rate:>7.1f}%   {mtes_m.avg_return_per_signal:>+7.2f}% {best}")
                else:
                    print(f"{symbol:<10} SuperTrend {st_m.total_signals:>4}      {st_m.direction_accuracy:>7.1f}%   "
                          f"{st_m.false_signal_rate:>7.1f}%   {st_m.avg_return_per_signal:>+7.2f}% {best}")
                    print(f"{'':10} MTES        {mtes_m.total_signals:>4}      {mtes_m.direction_accuracy:>7.1f}%   "
                          f"{mtes_m.false_signal_rate:>7.1f}%   {mtes_m.avg_return_per_signal:>+7.2f}%")
            elif st_m.total_signals > 0:
                print(f"{symbol:<10} SuperTrend {st_m.total_signals:>4}      {st_m.direction_accuracy:>7.1f}%   "
                      f"{st_m.false_signal_rate:>7.1f}%   {st_m.avg_return_per_signal:>+7.2f}%")
            elif mtes_m.total_signals > 0:
                print(f"{symbol:<10} MTES        {mtes_m.total_signals:>4}      {mtes_m.direction_accuracy:>7.1f}%   "
                      f"{mtes_m.false_signal_rate:>7.1f}%   {mtes_m.avg_return_per_signal:>+7.2f}%")

        # 平均值
        print(f"{'─' * 60}")
        if st_avg_acc:
            print(f"{'平均':<10} SuperTrend {'--':>4}      {np.mean(st_avg_acc):>7.1f}%   "
                  f"{np.mean(st_avg_false):>7.1f}%   {np.mean(st_avg_ret):>+7.2f}%")
        if mtes_avg_acc:
            print(f"{'':10} MTES        {'--':>4}      {np.mean(mtes_avg_acc):>7.1f}%   "
                  f"{np.mean(mtes_avg_false):>7.1f}%   {np.mean(mtes_avg_ret):>+7.2f}%")


if __name__ == "__main__":
    main()
