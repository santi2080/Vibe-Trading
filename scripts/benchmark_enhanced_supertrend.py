#!/usr/bin/env python3
"""
增强版 SuperTrend 测评

对比原版 vs 增强版：
1. 趋势状态准确率
2. 置信度分布
3. 震荡识别能力
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from collections import defaultdict

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analysis.enhanced_supertrend import EnhancedSuperTrend
from analysis.my_trend_magic import MyTrendMagic


# ──────────────────────────────────────────────────────────────────
# Ground Truth
# ──────────────────────────────────────────────────────────────────

def get_actual_trend(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """计算实际趋势"""
    close = df["close"]
    returns = close.pct_change(lookback)
    returns_smooth = returns.rolling(5).mean()

    signal = np.zeros(len(df))
    signal[returns_smooth > 0.01] = 1   # 上涨
    signal[returns_smooth < -0.01] = -1  # 下跌
    # 0 = 震荡

    return pd.Series(signal, index=df.index)


# ──────────────────────────────────────────────────────────────────
# 原始 SuperTrend（只输出 +1/-1）
# ──────────────────────────────────────────────────────────────────

def calc_basic_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """原版 SuperTrend，只输出方向"""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)

    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr1[0], tr2[0], tr3[0] = 0, 0, 0
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = pd.Series(tr).rolling(window=period).mean().values

    hl_avg = (high + low) / 2
    basic_ub = hl_avg + multiplier * atr
    basic_lb = hl_avg - multiplier * atr

    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()
    direction = np.zeros(n)

    for i in range(1, n):
        if basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i-1]

        if basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i-1]

        if direction[i-1] == 1:
            direction[i] = -1 if close[i] < final_ub[i] else 1
        else:
            direction[i] = 1 if close[i] > final_lb[i] else -1

    return pd.Series(direction, index=df.index)


def calc_my_trend_magic(df: pd.DataFrame, cci_period: int = 20, atr_period: int = 10, atr_mult: float = 1.0) -> pd.Series:
    """MyTrendMagic：只有斜率变化时才改变趋势方向

    核心逻辑：
    - 斜率 UP → 趋势向上
    - 斜率 DOWN → 趋势向下
    - 斜率 FLAT（无变化）→ 保持前一个趋势方向
    - 只有斜率发生变化时，趋势方向才改变
    """
    n = len(df)
    if n < max(cci_period, atr_period, 10):
        return pd.Series(0, index=df.index)

    # ATR
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean()

    # CCI
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(window=cci_period).mean()
    mad = tp.rolling(window=cci_period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad + 1e-10)

    # Magic Line 状态机
    upT = df["low"] - atr * atr_mult
    downT = df["high"] + atr * atr_mult
    magic = pd.Series(np.nan, index=df.index)
    magic.iloc[0] = upT.iloc[0] if cci.iloc[0] >= 0 else downT.iloc[0]
    for i in range(1, n):
        if cci.iloc[i] >= 0:
            magic.iloc[i] = upT.iloc[i] if upT.iloc[i] > magic.iloc[i-1] else magic.iloc[i-1]
        else:
            magic.iloc[i] = downT.iloc[i] if downT.iloc[i] < magic.iloc[i-1] else magic.iloc[i-1]

    # slope_state: 基于 magic line 变化
    magic_change = magic.diff()
    slope_state = pd.Series("FLAT", index=df.index)
    slope_state[magic_change > 0] = "UP"
    slope_state[magic_change < 0] = "DOWN"

    # 趋势方向：只有斜率变化时才改变方向
    direction = np.zeros(n)
    current_dir = 1 if cci.iloc[cci_period] >= 0 else -1
    direction[cci_period] = current_dir

    for i in range(cci_period + 1, n):
        curr_slope = slope_state.iloc[i]
        prev_slope = slope_state.iloc[i - 1]

        # 只有斜率发生变化时，才改变方向
        if curr_slope != prev_slope:
            if curr_slope == "UP":
                current_dir = 1
            elif curr_slope == "DOWN":
                current_dir = -1

        direction[i] = current_dir

    return pd.Series(direction, index=df.index)


# ──────────────────────────────────────────────────────────────────
# 评估指标
# ──────────────────────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    indicator: str
    symbol: str

    # 准确率
    overall_accuracy: float = 0.0
    uptrend_accuracy: float = 0.0
    downtrend_accuracy: float = 0.0
    churn_accuracy: float = 0.0

    # 趋势分布
    uptrend_pct: float = 0.0
    downtrend_pct: float = 0.0
    churn_pct: float = 0.0

    # 置信度（增强版）
    avg_confidence: float = 0.0
    high_confidence_pct: float = 0.0  # confidence >= 0.7

    # 状态分布
    state_0_pct: float = 0.0  # 震荡占比
    state_1_pct: float = 0.0  # 上涨占比
    state_minus1_pct: float = 0.0  # 下跌占比


def evaluate_indicator(
    df: pd.DataFrame,
    actual_trend: pd.Series,
    indicator_name: str,
    symbol: str,
) -> EvaluationResult:
    """评估单个指标"""

    result = EvaluationResult(indicator=indicator_name, symbol=symbol)

    # 计算指标信号
    if indicator_name == "EnhancedSuperTrend":
        indicator = EnhancedSuperTrend()
        calc_result = indicator.calculate(df)
        signal = calc_result["trend_code"]  # 1, -1, 0
        confidence = calc_result["confidence"]
    elif indicator_name == "MyTrendMagic":
        signal = calc_my_trend_magic(df)
        confidence = None
    else:
        signal = calc_basic_supertrend(df)
        confidence = None

    # 过滤有效数据
    valid_mask = signal != 0  # 基本 SuperTrend 没有 0
    valid_idx = valid_mask | (signal == 0)  # 所有数据

    if valid_idx.sum() < 30:
        return result

    total = valid_idx.sum()

    # 1. 准确率
    correct = (
        ((signal == 1) & (actual_trend == 1)).sum() +
        ((signal == -1) & (actual_trend == -1)).sum() +
        ((signal == 0) & (actual_trend == 0)).sum()
    )
    result.overall_accuracy = correct / total * 100 if total > 0 else 0

    # 各状态准确率
    up_mask = (actual_trend == 1) & valid_idx
    down_mask = (actual_trend == -1) & valid_idx
    churn_mask = (actual_trend == 0) & valid_idx

    result.uptrend_accuracy = ((signal[up_mask] == 1).sum() / up_mask.sum() * 100) if up_mask.sum() > 0 else 0
    result.downtrend_accuracy = ((signal[down_mask] == -1).sum() / down_mask.sum() * 100) if down_mask.sum() > 0 else 0
    result.churn_accuracy = ((signal[churn_mask] == 0).sum() / churn_mask.sum() * 100) if churn_mask.sum() > 0 else 0

    # 2. 趋势分布
    result.uptrend_pct = (signal == 1).sum() / len(signal) * 100
    result.downtrend_pct = (signal == -1).sum() / len(signal) * 100
    result.churn_pct = (signal == 0).sum() / len(signal) * 100

    # 3. 置信度（增强版）
    if confidence is not None:
        result.avg_confidence = confidence.mean() * 100
        result.high_confidence_pct = (confidence >= 0.7).sum() / len(confidence) * 100

    # 4. 状态分布
    result.state_0_pct = result.churn_pct
    result.state_1_pct = result.uptrend_pct
    result.state_minus1_pct = result.downtrend_pct

    return result


# ──────────────────────────────────────────────────────────────────
# 数据加载
# ──────────────────────────────────────────────────────────────────

def load_data(symbol: str) -> Optional[pd.DataFrame]:
    """从本地 Parquet 加载数据"""
    sym = symbol.upper()

    candidates = [
        PROJECT_ROOT / "data" / "us_futures" / sym / "1d.parquet",
        PROJECT_ROOT / "data" / "us_futures" / f"{sym}" / "1d.parquet",
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
            df.columns = [c.lower() for c in df.columns]
            return df[[c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]]

    return None


# ──────────────────────────────────────────────────────────────────
# 主程序
# ──────────────────────────────────────────────────────────────────

MARKETS = {
    "贵金属": ["GC=F", "SI=F"],
    "股指期货": ["ES=F", "NQ=F"],
    "原油": ["CL=F"],
}


def main():
    print("=" * 90)
    print("增强版 SuperTrend 趋势状态测评".center(70))
    print("=" * 90)

    all_results = defaultdict(list)

    symbols = ["GC=F", "ES=F", "NQ=F", "CL=F", "SI=F"]

    for symbol in symbols:
        print(f"\n{'─' * 90}")
        print(f"  📊 {symbol}")
        print(f"{'─' * 90}")

        df = load_data(symbol)
        if df is None or len(df) < 100:
            print(f"    ⚠️ 数据不足")
            continue

        print(f"    数据: {len(df)} 根日线 ({df.index[0].date()} ~ {df.index[-1].date()})")

        # 计算实际趋势
        actual_trend = get_actual_trend(df)

        # 评估所有版本
        basic_result = evaluate_indicator(df, actual_trend, "BasicSuperTrend", symbol)
        tm_result = evaluate_indicator(df, actual_trend, "MyTrendMagic", symbol)
        enhanced_result = evaluate_indicator(df, actual_trend, "EnhancedSuperTrend", symbol)

        # 打印对比
        print(f"\n    {'指标':<22} | {'准确率':>10} | {'上涨准确':>10} | {'下跌准确':>10}")
        print(f"    {'─'*22} ──────────── ──────────── ────────────")
        print(f"    {'Basic SuperTrend':<22} | {basic_result.overall_accuracy:>9.1f}% | "
              f"{basic_result.uptrend_accuracy:>9.1f}% | {basic_result.downtrend_accuracy:>9.1f}%")
        print(f"    {'TrendMagic CCI':<22} | {tm_result.overall_accuracy:>9.1f}% | "
              f"{tm_result.uptrend_accuracy:>9.1f}% | {tm_result.downtrend_accuracy:>9.1f}%")
        print(f"    {'Enhanced ST+TM':<22} | {enhanced_result.overall_accuracy:>9.1f}% | "
              f"{enhanced_result.uptrend_accuracy:>9.1f}% | {enhanced_result.downtrend_accuracy:>9.1f}%")

        print(f"\n    {'状态分布':>22} | {'上涨':>10} | {'下跌':>10} | {'震荡':>10}")
        print(f"    {'─'*22} ──────────── ──────────── ────────────")
        print(f"    {'实际趋势':<22} | {(actual_trend == 1).mean()*100:>9.1f}% | "
              f"{(actual_trend == -1).mean()*100:>9.1f}% | {(actual_trend == 0).mean()*100:>9.1f}%")
        print(f"    {'Basic SuperTrend':<22} | {basic_result.uptrend_pct:>9.1f}% | "
              f"{basic_result.downtrend_pct:>9.1f}% | {basic_result.churn_pct:>9.1f}%")
        print(f"    {'TrendMagic CCI':<22} | {tm_result.uptrend_pct:>9.1f}% | "
              f"{tm_result.downtrend_pct:>9.1f}% | {tm_result.churn_pct:>9.1f}%")
        print(f"    {'Enhanced ST+TM':<22} | {enhanced_result.uptrend_pct:>9.1f}% | "
              f"{enhanced_result.downtrend_pct:>9.1f}% | {enhanced_result.churn_pct:>9.1f}%")

        all_results["BasicSuperTrend"].append(basic_result)
        all_results["MyTrendMagic"].append(tm_result)
        all_results["EnhancedSuperTrend"].append(enhanced_result)

    # 汇总
    if all_results:
        print(f"\n{'=' * 90}")
        print("汇总".center(70))
        print(f"{'=' * 90}")

        print(f"\n{'指标':<22} | {'平均准确率':>10} | {'平均上涨准确':>12} | {'平均下跌准确':>12} | {'平均震荡准确':>12}")
        print(f"    {'─'*22} ──────────── ───────────── ───────────── ─────────────")

        for ind_name, results in all_results.items():
            avg_acc = np.mean([r.overall_accuracy for r in results])
            avg_up = np.mean([r.uptrend_accuracy for r in results])
            avg_down = np.mean([r.downtrend_accuracy for r in results])
            avg_churn = np.mean([r.churn_accuracy for r in results])
            print(f"    {ind_name:<22} | {avg_acc:>9.1f}% | {avg_up:>11.1f}% | "
                  f"{avg_down:>11.1f}% | {avg_churn:>11.1f}%")

        # 震荡状态分布对比
        print(f"\n    {'震荡状态输出占比':<22} | {'Basic':>10} | {'Enhanced':>10}")
        print(f"    {'─'*22} ──────────── ────────────")
        basic_churn = np.mean([r.churn_pct for r in all_results["BasicSuperTrend"]])
        enhanced_churn = np.mean([r.churn_pct for r in all_results["EnhancedSuperTrend"]])
        print(f"    {'平均震荡占比':<22} | {basic_churn:>9.1f}% | {enhanced_churn:>9.1f}%")

        # 置信度
        print(f"\n    {'置信度统计（Enhanced）':<22}")
        print(f"    {'─'*50}")
        avg_conf = np.mean([r.avg_confidence for r in all_results["EnhancedSuperTrend"]])
        avg_high = np.mean([r.high_confidence_pct for r in all_results["EnhancedSuperTrend"]])
        print(f"    平均置信度: {avg_conf:.1f}%")
        print(f"    高置信度占比 (>=0.7): {avg_high:.1f}%")


if __name__ == "__main__":
    main()
