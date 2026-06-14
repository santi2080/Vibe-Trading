#!/usr/bin/env python3
"""
MTES v4 vs 经典趋势策略 vs 基线策略 三方对比脚本

基线(不变): price>EMA200 + EMA斜率↑ + DI+>DI- + ADX>25
对比对象: MTES v4, EMA(50/200)黄金交叉, MACD(12/26/9), SuperTrend(10,3)

每个对象分别与基线比较方向一致率、冲突率、信号稳定性。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

import argparse
import pandas as pd
import numpy as np


# ── 1. 基线策略 (固定) ───────────────────────────────────────────


class BaselineStrategy:
    """price > EMA200 + EMA斜率↑ + DI+ > DI- + ADX > 25"""

    def __init__(self):
        pass

    def analyze_signal(self, df: pd.DataFrame) -> pd.Series:
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        n = len(df)
        if n < 220:
            return pd.Series(np.nan, index=df.index)

        # EMA200
        ema = close.ewm(span=200, adjust=False).mean()
        ema_slope = (ema - ema.shift(5)) / ema.shift(5)

        # ADX + DI
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        up_move = (high.diff()).clip(lower=0)
        down_move = (-low.diff()).clip(lower=0)
        plus_dm = np.where((up_move.values > down_move.values) & (up_move.values > 0), up_move.values, 0)
        minus_dm = np.where((down_move.values > up_move.values) & (down_move.values > 0), down_move.values, 0)

        alpha = 1 / 14
        smooth_tr = tr.ewm(alpha=alpha, adjust=False).mean()
        smooth_plus = pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
        smooth_minus = pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()

        plus_di = 100 * smooth_plus / smooth_tr.replace(0, 1)
        minus_di = 100 * smooth_minus / smooth_tr.replace(0, 1)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1)
        adx = dx.ewm(alpha=alpha, adjust=False).mean()

        signal = pd.Series(0, index=df.index)
        bull = (close > ema) & (ema_slope > 0.001) & (plus_di > minus_di) & (adx > 25)
        bear = (close < ema) & (ema_slope < -0.001) & (minus_di > plus_di) & (adx > 25)

        signal[bull] = 1
        signal[bear] = -1
        signal.name = "baseline"
        return signal


# ── 2. 对比对象 ───────────────────────────────────────────────────


def analyze_mtes_v4(df: pd.DataFrame) -> pd.Series:
    """LeanMTES action_bias → signal."""
    from src.analysis.mtes_v4 import LeanMTES

    mtes = LeanMTES()
    signal = pd.Series(0, index=df.index)
    warmup = 90
    for i in range(warmup, len(df)):
        try:
            res = mtes.analyze(df.iloc[:i + 1])
            if res.action_bias in ("STRONG_LONG", "CAUTIOUS_LONG"):
                signal.iloc[i] = 1
            elif res.action_bias in ("STRONG_SHORT", "CAUTIOUS_SHORT"):
                signal.iloc[i] = -1
        except Exception:
            signal.iloc[i] = 0
    signal.name = "mtes_v4"
    return signal


def analyze_ema_cross(df: pd.DataFrame) -> pd.Series:
    """EMA(50/200) 黄金交叉."""
    close = df["close"]
    fast = close.ewm(span=50, adjust=False).mean()
    slow = close.ewm(span=200, adjust=False).mean()

    diff = fast - slow
    prev = diff.shift(1)
    signal = pd.Series(0, index=df.index)
    signal[(prev <= 0) & (diff > 0)] = 1
    signal[(prev >= 0) & (diff < 0)] = -1
    signal.name = "ema_cross"
    return signal


def analyze_macd(df: pd.DataFrame) -> pd.Series:
    """MACD(12/26/9) 零轴穿越."""
    close = df["close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal_line

    prev = hist.shift(1)
    signal = pd.Series(0, index=df.index)
    signal[(prev <= 0) & (hist > 0)] = 1
    signal[(prev >= 0) & (hist < 0)] = -1
    signal.name = "macd"
    return signal


def analyze_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """SuperTrend(10,3)."""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)

    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = pd.Series(tr).rolling(period).mean().values

    hl_avg = (high + low) / 2
    basic_ub = hl_avg + multiplier * atr
    basic_lb = hl_avg - multiplier * atr

    final_ub = np.copy(basic_ub)
    final_lb = np.copy(basic_lb)
    direction = np.ones(n)

    for i in range(period, n):
        if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
            final_ub[i] = basic_ub[i]
        if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]:
            final_lb[i] = basic_lb[i]

        if direction[i - 1] == -1 and close[i] > final_lb[i]:
            direction[i] = 1
        elif direction[i - 1] == 1 and close[i] < final_ub[i]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]

    signal = pd.Series(direction, index=df.index)
    signal.name = "supertrend"
    return signal


# ── 3. 对比计算 ────────────────────────────────────────────────────


STRATEGIES = {
    "MTES_v4": analyze_mtes_v4,
    "EMA_Cross": analyze_ema_cross,
    "MACD": analyze_macd,
    "SuperTrend": analyze_supertrend,
}


def compute_alignment(bl: pd.Series, target: pd.Series, warmup: int) -> dict:
    bl = bl.iloc[warmup:]
    tg = target.iloc[warmup:]
    valid = bl.notna() & tg.notna()
    bl, tg = bl[valid], tg[valid]
    n = len(bl)
    if n == 0:
        return {}

    same = (bl == tg).sum()
    agreement = same / n
    conflict = ((bl == 1) & (tg == -1)) | ((bl == -1) & (tg == 1))
    conflict_rate = conflict.sum() / n

    # 切换次数
    bl_switch = (bl.diff() != 0).sum()
    tg_switch = (tg.diff() != 0).sum()

    # 平均连续一致天数
    runs = (bl == tg).astype(int)
    run_lengths = []
    cur = 0
    for v in runs.values:
        if v:
            cur += 1
        else:
            if cur > 0:
                run_lengths.append(cur)
                cur = 0
    if cur > 0:
        run_lengths.append(cur)
    avg_consec = np.mean(run_lengths) if run_lengths else 0.0

    return {
        "n": n,
        "bl_bull": (bl == 1).sum() / n,
        "bl_bear": (bl == -1).sum() / n,
        "bl_neutral": (bl == 0).sum() / n,
        "tg_bull": (tg == 1).sum() / n,
        "tg_bear": (tg == -1).sum() / n,
        "tg_neutral": (tg == 0).sum() / n,
        "agreement": agreement,
        "conflict": conflict_rate,
        "bl_turnover": bl_switch / n,
        "tg_turnover": tg_switch / n,
        "avg_consecutive": avg_consec,
    }


# ── 4. 输出 ────────────────────────────────────────────────────────


def print_all(all_results: dict[str, dict[str, dict]], start: str, end: str, n_bars: int):
    """按品种输出，每种策略一行."""
    for symbol, strategies in all_results.items():
        bar = "─" * 115
        print(f"\n{bar}")
        print(f"  {symbol}  ({start} ~ {end}, {n_bars} bars)")
        print(bar)
        print(f"{'策略':<12} | {'一致率':>7} | {'冲突率':>7} | {'多(基)':>7} | {'多(对)':>7} | {'空(基)':>7} | {'空(对)':>7} | {'连续一致':>6} | {'换手基':>6} | {'换手对':>6}")
        print(bar)

        for strategy_name, m in strategies.items():
            print(f"│ {strategy_name:<10} │ {m['agreement']*100:>5.1f}% │ {m['conflict']*100:>5.1f}% │ {m['bl_bull']*100:>5.1f}% │ {m['tg_bull']*100:>5.1f}% │ {m['bl_bear']*100:>5.1f}% │ {m['tg_bear']*100:>5.1f}% │ {m['avg_consecutive']:>5.1f}d │ {m['bl_turnover']*100:>5.2f}% │ {m['tg_turnover']*100:>5.2f}% │")

    # 全品种汇总
    print(f"\n\n{'=' * 115}")
    print(f"  US Futures 全品种汇总 — 各策略 vs 基线")
    print(f"{'=' * 115}")
    print(f"{'策略':<12} | {'一致率':>7} | {'冲突率':>7} | {'多(基)':>7} | {'多(对)':>7} | {'空(基)':>7} | {'空(对)':>7} | {'连续一致':>6} | {'换手基':>6} | {'换手对':>6}")
    print(f"{'=' * 115}")

    # 按策略汇总
    strategy_avgs = {}
    for symbol, strategies in all_results.items():
        for name, m in strategies.items():
            if name not in strategy_avgs:
                strategy_avgs[name] = []
            strategy_avgs[name].append(m)

    for name in list(STRATEGIES.keys()):
        vals = strategy_avgs.get(name, [])
        if not vals:
            continue
        avg = lambda k: np.mean([v[k] for v in vals])
        print(f"│ {name:<10} │ {avg('agreement')*100:>5.1f}% │ {avg('conflict')*100:>5.1f}% │ {avg('bl_bull')*100:>5.1f}% │ {avg('tg_bull')*100:>5.1f}% │ {avg('bl_bear')*100:>5.1f}% │ {avg('tg_bear')*100:>5.1f}% │ {avg('avg_consecutive'):>5.1f}d │ {avg('bl_turnover')*100:>5.2f}% │ {avg('tg_turnover')*100:>5.2f}% │")

    print(f"{'=' * 115}")
    print(f"  （基线：price>EMA200 + EMA斜率>0.001 + DI+>DI- + ADX>25）")


# ── 5. 主函数 ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="趋势策略 vs 基线对比")
    parser.add_argument("--symbols", nargs="+", default=[
        "GC=F", "SI=F", "HG=F", "CL=F", "ZC=F", "ZS=F", "ES=F", "NQ=F"
    ])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-06-14")
    parser.add_argument("--warmup", type=int, default=100)
    args = parser.parse_args()

    baseline = BaselineStrategy()
    all_results = {}
    n_bars = 0

    print(f"\n  加载并分析 {len(args.symbols)} 个品种 × {len(STRATEGIES)} 种策略...\n")

    for symbol in args.symbols:
        path = PROJECT_ROOT / "data" / "us_futures" / symbol / "1d.parquet"
        if not path.exists():
            print(f"  ⚠  {symbol}: 数据文件不存在")
            continue

        df = pd.read_parquet(path)
        df.columns = df.columns.str.lower()
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        df = df.sort_index()
        mask = (df.index >= args.start) & (df.index <= args.end)
        df = df[mask].copy()
        if len(df) < args.warmup + 50:
            print(f"  ⚠  {symbol}: 数据不足 ({len(df)} bars)")
            continue

        n_bars = len(df) - args.warmup

        # 基线
        bl = baseline.analyze_signal(df)

        # 各策略
        strategies = {}
        for name, func in STRATEGIES.items():
            try:
                tg = func(df)
                m = compute_alignment(bl, tg, warmup=args.warmup)
                if m:
                    strategies[name] = m
            except Exception as e:
                print(f"  ⚠  {symbol}/{name}: {e}")

        if strategies:
            all_results[symbol] = strategies

    if all_results:
        print_all(all_results, args.start, args.end, n_bars)
    else:
        print("  无有效结果。")


if __name__ == "__main__":
    main()
