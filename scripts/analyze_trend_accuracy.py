#!/usr/bin/env python3
"""
趋势指标准确性与滞后性分析

分析维度：
1. 趋势判断准确度 - 指标判断 vs 实际趋势
2. 趋势变化滞后性 - 指标变化 vs 价格变化的延迟
3. 趋势持续性 - 指标判断的趋势持续时间

输出：上涨/下跌/震荡 + 强度
"""

import argparse
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from src.analysis.major_trend_evaluator import MajorTrendEvaluator, TrendState


# ──────────────────────────────────────────────────────────────────
# 1. 趋势指标实现
# ──────────────────────────────────────────────────────────────────

class TrendIndicator:
    """趋势指标基类"""
    name: str

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """返回: 1=上涨, -1=下跌, 0=震荡"""
        raise NotImplementedError

    def strength(self, df: pd.DataFrame) -> pd.Series:
        """返回趋势强度 0-100"""
        raise NotImplementedError


class MTESIndicator(TrendIndicator):
    """MTES 趋势指标"""
    name = "MTES"

    def __init__(self, asset_class: str = "futures", warmup: int = 60):
        self.asset_class = asset_class
        self.warmup = warmup
        self.evaluator = MajorTrendEvaluator()

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        directions = []
        warmup = min(self.warmup, len(df) - 10)

        for i in range(len(df)):
            if i < warmup:
                directions.append(0)
            else:
                window = df.iloc[:i+1].copy()
                try:
                    result = self.evaluator.evaluate(
                        window,
                        asset_class=self.asset_class,
                        base_timeframe="1d",
                        higher_timeframe_name="1w",
                    )
                    state = result.trend_state
                    if hasattr(state, 'value'):
                        state = state.value

                    # BULL状态 -> 上涨
                    if state in ['BULL_STRONG', 'BULL_CONFIRMED']:
                        directions.append(1)
                    # BEAR状态 -> 下跌
                    elif state in ['BEAR_STRONG', 'BEAR_CONFIRMED']:
                        directions.append(-1)
                    else:
                        directions.append(0)
                except:
                    directions.append(0)

        return pd.Series(directions, index=df.index)

    def strength(self, df: pd.DataFrame) -> pd.Series:
        scores = []
        warmup = min(self.warmup, len(df) - 10)

        for i in range(len(df)):
            if i < warmup:
                scores.append(np.nan)
            else:
                window = df.iloc[:i+1].copy()
                try:
                    result = self.evaluator.evaluate(
                        window,
                        asset_class=self.asset_class,
                        base_timeframe="1d",
                        higher_timeframe_name="1w",
                    )
                    scores.append(result.trend_score * 100)
                except:
                    scores.append(np.nan)

        return pd.Series(scores, index=df.index)


class SuperTrendIndicator(TrendIndicator):
    """SuperTrend 趋势指标"""
    name = "SuperTrend"

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        # ATR
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr1[0], tr2[0], tr3[0] = 0, 0, 0
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = pd.Series(tr).rolling(window=self.period).mean().values

        # 基础带
        hl_avg = (high + low) / 2
        basic_ub = hl_avg + self.multiplier * atr
        basic_lb = hl_avg - self.multiplier * atr

        final_ub = basic_ub.copy()
        final_lb = basic_lb.copy()
        direction = np.zeros(n)
        direction[self.period] = 1

        for i in range(self.period + 1, n):
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

    def strength(self, df: pd.DataFrame) -> pd.Series:
        # ATR 百分比作为强度指标
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr1[0], tr2[0], tr3[0] = 0, 0, 0
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = pd.Series(tr).rolling(window=self.period).mean()

        return (atr / close * 100).values


class EMAIndicator(TrendIndicator):
    """EMA 趋势指标 - 快线 > 慢线 = 上涨"""
    name = "EMA(50/200)"

    def __init__(self, fast: int = 50, slow: int = 200):
        self.fast = fast
        self.slow = slow

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()

        diff = ema_fast - ema_slow
        signal = np.zeros(len(df))

        # 快线在慢线上方且差距扩大 -> 上涨
        signal[diff > 0] = 1
        # 快线在慢线下方且差距扩大 -> 下跌
        signal[diff < 0] = -1

        return pd.Series(signal, index=df.index)

    def strength(self, df: pd.DataFrame) -> pd.Series:
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()

        # 相对强度：差距/价格
        strength = np.abs(ema_fast - ema_slow) / df["close"] * 100
        return strength.values


class ADXIndicator(TrendIndicator):
    """ADX 趋势指标"""
    name = "ADX(14)>25"

    def __init__(self, period: int = 14, threshold: float = 25.0):
        self.period = period
        self.threshold = threshold

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()

        # Directional Movement
        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        smooth_plus_dm = plus_dm.rolling(window=self.period).mean()
        smooth_minus_dm = minus_dm.rolling(window=self.period).mean()

        plus_di = 100 * (smooth_plus_dm / atr)
        minus_di = 100 * (smooth_minus_dm / atr)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=self.period).mean()

        signal = np.zeros(len(df))

        # ADX > threshold 且 +DI > -DI -> 上涨
        mask_up = (adx > self.threshold) & (plus_di > minus_di)
        # ADX > threshold 且 -DI > +DI -> 下跌
        mask_down = (adx > self.threshold) & (minus_di > plus_di)

        signal[mask_up] = 1
        signal[mask_down] = -1

        return pd.Series(signal, index=df.index)

    def strength(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        smooth_plus_dm = plus_dm.rolling(window=self.period).mean()
        smooth_minus_dm = minus_dm.rolling(window=self.period).mean()

        plus_di = 100 * (smooth_plus_dm / atr)
        minus_di = 100 * (smooth_minus_dm / atr)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=self.period).mean()

        return adx.fillna(0).values


# ──────────────────────────────────────────────────────────────────
# 2. 实际趋势 Ground Truth
# ──────────────────────────────────────────────────────────────────

def get_actual_trend(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    计算实际趋势：使用价格变化的移动平均

    返回:
    - 1: 上涨趋势 (价格持续上涨)
    - -1: 下跌趋势 (价格持续下跌)
    - 0: 震荡 (方向不明)
    """
    close = df["close"]

    # 使用 N 日价格变化率
    returns = close.pct_change(lookback)

    # 平滑处理
    returns_smooth = returns.rolling(5).mean()

    signal = np.zeros(len(df))
    signal[returns_smooth > 0.01] = 1  # 上涨超过 1%
    signal[returns_smooth < -0.01] = -1  # 下跌超过 -1%

    return pd.Series(signal, index=df.index)


def get_trend_change_points(trend: pd.Series) -> List[Tuple[int, int]]:
    """找出趋势变化点: (索引, 变化方向)"""
    changes = []
    prev = 0
    for i in range(1, len(trend)):
        if trend.iloc[i] != prev and trend.iloc[i] != 0:
            changes.append((i, int(trend.iloc[i])))
            prev = trend.iloc[i]
    return changes


# ──────────────────────────────────────────────────────────────────
# 3. 准确性与滞后性分析
# ──────────────────────────────────────────────────────────────────

@dataclass
class TrendAnalysisResult:
    indicator: str
    symbol: str

    # 准确性指标
    overall_accuracy: float = 0.0  # 整体准确率
    uptrend_accuracy: float = 0.0  # 上涨趋势准确率
    downtrend_accuracy: float = 0.0  # 下跌趋势准确率
    churn_accuracy: float = 0.0  # 震荡趋势准确率

    # 滞后性指标
    avg_lag_bars: float = 0.0  # 平均滞后 K 线数
    max_lag_bars: int = 0  # 最大滞后
    min_lag_bars: int = 0  # 最小滞后

    # 趋势判断分布
    uptrend_pct: float = 0.0  # 判断为上涨的时间占比
    downtrend_pct: float = 0.0  # 判断为下跌的时间占比
    churn_pct: float = 0.0  # 判断为震荡的时间占比

    # 趋势强度
    avg_strength: float = 0.0  # 平均趋势强度

    def summary(self) -> str:
        return (
            f"{self.indicator:<15} | 准确:{self.overall_accuracy:>5.1f}% | "
            f"滞后:{self.avg_lag_bars:>4.1f}K | "
            f"涨:{self.uptrend_pct:>4.0f}% 跌:{self.downtrend_pct:>4.0f}% 震:{self.churn_pct:>4.0f}% | "
            f"强度:{self.avg_strength:>5.1f}"
        )


def analyze_indicator(
    indicator: TrendIndicator,
    df: pd.DataFrame,
    symbol: str,
    actual_trend: pd.Series,
) -> TrendAnalysisResult:
    """分析单个指标"""

    # 计算指标趋势判断
    ind_trend = indicator.calculate(df)
    ind_strength = indicator.strength(df)

    # 过滤有效数据（去除 warmup 期间的 NaN）
    valid_mask = ind_trend != 0
    valid_idx = valid_mask

    if valid_idx.sum() < 30:
        return TrendAnalysisResult(
            indicator=indicator.name,
            symbol=symbol,
            overall_accuracy=0,
            uptrend_accuracy=0,
            downtrend_accuracy=0,
            churn_accuracy=0,
            avg_lag_bars=0,
            max_lag_bars=0,
            min_lag_bars=0,
            uptrend_pct=0,
            downtrend_pct=0,
            churn_pct=0,
            avg_strength=0,
        )

    # 1. 计算准确性
    # 将指标趋势映射到实际趋势的判断
    total = valid_idx.sum()
    correct = ((ind_trend[valid_idx] == 1) & (actual_trend[valid_idx] == 1)).sum() + \
              ((ind_trend[valid_idx] == -1) & (actual_trend[valid_idx] == -1)).sum() + \
              ((ind_trend[valid_idx] == 0) & (actual_trend[valid_idx] == 0)).sum()

    overall_accuracy = correct / total * 100 if total > 0 else 0

    # 各趋势类型准确率
    up_mask = (actual_trend == 1) & valid_idx
    down_mask = (actual_trend == -1) & valid_idx
    churn_mask = (actual_trend == 0) & valid_idx

    uptrend_accuracy = ((ind_trend[up_mask] == 1).sum() / up_mask.sum() * 100) if up_mask.sum() > 0 else 0
    downtrend_accuracy = ((ind_trend[down_mask] == -1).sum() / down_mask.sum() * 100) if down_mask.sum() > 0 else 0
    churn_accuracy = ((ind_trend[churn_mask] == 0).sum() / churn_mask.sum() * 100) if churn_mask.sum() > 0 else 0

    # 2. 计算滞后性
    ind_changes = get_trend_change_points(ind_trend)
    actual_changes = get_trend_change_points(actual_trend)

    lags = []
    for actual_idx, actual_dir in actual_changes:
        # 找到最近的趋势变化
        for i in range(actual_idx, max(0, actual_idx - 50), -1):
            if ind_trend.iloc[i] == actual_dir:
                lag = actual_idx - i
                if lag >= 0:  # 指标滞后或同步
                    lags.append(lag)
                break

    avg_lag = np.mean(lags) if lags else 0
    max_lag = max(lags) if lags else 0
    min_lag = min(lags) if lags else 0

    # 3. 趋势分布
    uptrend_pct = (ind_trend == 1).sum() / len(ind_trend) * 100
    downtrend_pct = (ind_trend == -1).sum() / len(ind_trend) * 100
    churn_pct = (ind_trend == 0).sum() / len(ind_trend) * 100

    # 4. 平均强度
    valid_strength = ind_strength[~np.isnan(ind_strength)]
    avg_strength = np.mean(valid_strength) if len(valid_strength) > 0 else 0

    return TrendAnalysisResult(
        indicator=indicator.name,
        symbol=symbol,
        overall_accuracy=overall_accuracy,
        uptrend_accuracy=uptrend_accuracy,
        downtrend_accuracy=downtrend_accuracy,
        churn_accuracy=churn_accuracy,
        avg_lag_bars=avg_lag,
        max_lag_bars=max_lag,
        min_lag_bars=min_lag,
        uptrend_pct=uptrend_pct,
        downtrend_pct=downtrend_pct,
        churn_pct=churn_pct,
        avg_strength=avg_strength,
    )


# ──────────────────────────────────────────────────────────────────
# 4. 数据加载
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
# 5. 主程序
# ──────────────────────────────────────────────────────────────────

def infer_asset_class(symbol: str) -> str:
    """推断资产类别"""
    s = symbol.upper()
    if any(p in s for p in ["BTC", "ETH", "USDT"]):
        return "crypto"
    if any(p in s for p in ["GC", "ES", "SI", "CL", "NQ", "HG"]):
        return "futures"
    if any(p in s for p in ["SPY", "QQQ", "GLD", "SLV", "TLT"]):
        return "etf"
    return "stock"


MARKETS = {
    "贵金属": ["GC=F", "SI=F"],
    "股指期货": ["ES=F", "NQ=F"],
    "原油": ["CL=F"],
}


def main():
    parser = argparse.ArgumentParser(description="趋势指标准确性与滞后性分析")
    parser.add_argument("--symbols", nargs="+", default=["GC=F", "ES=F", "NQ=F", "CL=F", "SI=F"])
    parser.add_argument("--lookback", type=int, default=20, help="实际趋势计算回看期")
    args = parser.parse_args()

    print("=" * 100)
    print("趋势指标准确性与滞后性分析".center(80))
    print("=" * 100)
    print(f"实际趋势回看期: {args.lookback} 根日线")
    print()

    all_results = []

    for symbol in args.symbols:
        print(f"\n{'─' * 80}")
        print(f"  📊 {symbol}")
        print(f"{'─' * 80}")

        df = load_data(symbol)
        if df is None or len(df) < 100:
            print(f"    ⚠️ 数据不足")
            continue

        print(f"    数据: {len(df)} 根日线 ({df.index[0].date()} ~ {df.index[-1].date()})")

        # 计算实际趋势
        actual_trend = get_actual_trend(df, lookback=args.lookback)

        # 定义指标
        asset_class = infer_asset_class(symbol)
        indicators = [
            MTESIndicator(asset_class=asset_class, warmup=60),
            SuperTrendIndicator(period=10, multiplier=3.0),
            EMAIndicator(fast=50, slow=200),
            ADXIndicator(period=14, threshold=25.0),
        ]

        print(f"\n    {'指标':<18} | {'准确率':>8} | {'上涨准确':>8} | {'下跌准确':>8} | {'平均滞后':>8} | {'最大滞后':>8} |")
        print(f"    {'─'*18} ──────── ──────── ──────── ──────── ────────")

        for ind in indicators:
            result = analyze_indicator(ind, df, symbol, actual_trend)
            all_results.append(result)
            print(
                f"    {result.indicator:<18} | {result.overall_accuracy:>7.1f}% | "
                f"{result.uptrend_accuracy:>7.1f}% | {result.downtrend_accuracy:>7.1f}% | "
                f"{result.avg_lag_bars:>7.1f}K | {result.max_lag_bars:>7d}K |"
            )

    # 汇总
    if all_results:
        print(f"\n{'=' * 100}")
        print("汇总".center(80))
        print(f"{'=' * 100}")

        # 按指标聚合
        indicator_results = defaultdict(list)
        for r in all_results:
            indicator_results[r.indicator].append(r)

        print(f"\n    {'指标':<18} | {'平均准确率':>10} | {'平均滞后':>8} | {'平均上涨%':>10} | {'平均下跌%':>10} | {'平均强度':>8} |")
        print(f"    {'─'*18} ─────────── ──────── ─────────── ─────────── ─────────")

        for ind_name, results in sorted(indicator_results.items()):
            avg_acc = np.mean([r.overall_accuracy for r in results])
            avg_lag = np.mean([r.avg_lag_bars for r in results])
            avg_up = np.mean([r.uptrend_pct for r in results])
            avg_down = np.mean([r.downtrend_pct for r in results])
            avg_str = np.mean([r.avg_strength for r in results])

            print(
                f"    {ind_name:<18} | {avg_acc:>9.1f}% | {avg_lag:>7.1f}K | "
                f"{avg_up:>9.0f}% | {avg_down:>9.0f}% | {avg_str:>7.1f} |"
            )

        # 最佳指标
        print(f"\n    📌 最佳指标推荐:")
        indicator_avg = []
        for ind_name, results in indicator_results.items():
            avg_acc = np.mean([r.overall_accuracy for r in results])
            avg_lag = np.mean([r.avg_lag_bars for r in results])
            # 综合评分：准确率高 + 滞后低
            score = avg_acc - avg_lag * 0.5
            indicator_avg.append((ind_name, avg_acc, avg_lag, score))

        indicator_avg.sort(key=lambda x: x[3], reverse=True)
        for i, (name, acc, lag, score) in enumerate(indicator_avg, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"    {medal} {i}. {name}: 准确率 {acc:.1f}%, 滞后 {lag:.1f}K")


if __name__ == "__main__":
    main()
