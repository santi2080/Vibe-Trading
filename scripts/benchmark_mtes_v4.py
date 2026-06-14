#!/usr/bin/env python3
"""
MTES v4 vs 经典趋势策略 vs 基线策略 对比脚本（自动发现全品种）

基线(不变): price>EMA200 + EMA斜率↑ + DI+>DI- + ADX>25
对比对象: MTES v4, EMA(50/200)黄金交叉, MACD(12/26/9), SuperTrend(10,3)

自动扫描本地 parquet 数据，按市场分类输出对比结果。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

import argparse
import pandas as pd
import numpy as np
from collections import defaultdict


# ── 1. 数据自动发现 ─────────────────────────────────────────────

MARKET_CFG = [
    # (标签, 路径, 时间周期, 起止日期, warmup, 最小bar)
    ("US_Futures", "us_futures", "1d", "2024-01-01", "2026-06-14", 100, 220),
    ("CN_ETF", "cn_etf", "1d", "2020-01-01", "2026-06-14", 220, 500),
    ("US_Stocks", "us_stocks", "1w", "2020-01-01", "2026-06-14", 50, 150),
    ("US_ETF", "etf", "1w", "2020-01-01", "2026-06-14", 50, 80),
    ("HK_Stocks", "hk_stocks", "1d", "2024-01-01", "2026-06-14", 100, 200),
    ("CN_Futures", "cn_futures", "1d", "2025-01-01", "2026-06-14", 100, 200),
]


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 MultiIndex 列展平为一级列名.  SPY/1w.parquet 有 ('close', 'SPY') 这类列."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
    else:
        df.columns = df.columns.str.lower()
    return df


def discover_symbols(market_dir: str, tf: str, min_bars: int, start: str, end: str):
    """扫描 parquet 数据目录，发现符合条件的品种."""
    data_dir = PROJECT_ROOT / "data" / market_dir
    if not data_dir.exists():
        return []

    symbols = []
    for child in sorted(data_dir.iterdir()):
        if not child.is_dir():
            continue
        path = child / f"{tf}.parquet"
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            df = _flatten_columns(df)
            if "timestamp" in df.columns:
                df = df.set_index("timestamp")
            df = df.sort_index()
            mask = (df.index >= start) & (df.index <= end)
            df = df[mask]
            if len(df) >= min_bars and {"open", "high", "low", "close"}.issubset(set(df.columns)):
                symbols.append((child.name, len(df)))
        except Exception:
            continue

    return sorted(symbols, key=lambda x: -x[1])


# ── 2. 基线策略 ─────────────────────────────────────────────────


class BaselineStrategy:
    """price > EMA200 + EMA斜率↑ + DI+ > DI- + ADX > 25"""

    def analyze_signal(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        n = len(df)
        if n < 220:
            return pd.Series(np.nan, index=df.index)

        ema = close.ewm(span=200, adjust=False).mean()
        ema_slope = (ema - ema.shift(5)) / ema.shift(5)

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


# ── 3. 对比对象 ───────────────────────────────────────────────────


def analyze_mtes_v4(df: pd.DataFrame) -> pd.Series:
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
    close = df["close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    prev = hist.shift(1)
    signal = pd.Series(0, index=df.index)
    signal[(prev <= 0) & (hist > 0)] = 1
    signal[(prev >= 0) & (hist < 0)] = -1
    signal.name = "macd"
    return signal


def analyze_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
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


# ── 4. 对比计算 ──────────────────────────────────────────────────


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
    conflict = ((bl == 1) & (tg == -1)) | ((bl == -1) & (tg == 1))

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

    return {
        "n": n,
        "bl_bull": (bl == 1).sum() / n,
        "bl_bear": (bl == -1).sum() / n,
        "bl_neutral": (bl == 0).sum() / n,
        "tg_bull": (tg == 1).sum() / n,
        "tg_bear": (tg == -1).sum() / n,
        "tg_neutral": (tg == 0).sum() / n,
        "agreement": same / n,
        "conflict": conflict.sum() / n,
        "bl_turnover": (bl.diff() != 0).sum() / n,
        "tg_turnover": (tg.diff() != 0).sum() / n,
        "avg_consecutive": np.mean(run_lengths) if run_lengths else 0.0,
    }


# ── 5. 输出 ──────────────────────────────────────────────────────


def print_section(title: str, results: dict, n_bars: int, total_symbols: int):
    if not results:
        return
    bar = "=" * 115
    print(f"\n{bar}")
    print(f"  {title}  ({total_symbols} 品种, ~{n_bars} bars/品种)")
    print(f"{bar}")
    print(f"{'策略':<12} | {'一致率':>7} | {'冲突率':>7} | {'多(基)':>8} | {'多(对)':>8} | {'空(基)':>8} | {'空(对)':>8} | {'连续一致':>6} | {'换手基':>7} | {'换手对':>7}")
    print(bar)

    averages = defaultdict(list)
    for symbol, data in results.items():
        for name, m in data.items():
            averages[name].append(m)

    for name in list(STRATEGIES.keys()):
        vals = averages.get(name, [])
        if not vals:
            continue
        ag = np.mean([v["agreement"] for v in vals])
        cf = np.mean([v["conflict"] for v in vals])
        bb = np.mean([v["bl_bull"] for v in vals])
        tb = np.mean([v["tg_bull"] for v in vals])
        bd = np.mean([v["bl_bear"] for v in vals])
        td = np.mean([v["tg_bear"] for v in vals])
        ac = np.mean([v["avg_consecutive"] for v in vals])
        bt = np.mean([v["bl_turnover"] for v in vals])
        tt = np.mean([v["tg_turnover"] for v in vals])
        print(f"│ {name:<10} │ {ag*100:>5.1f}% │ {cf*100:>5.1f}% │ {bb*100:>6.1f}% │ {tb*100:>6.1f}% │ {bd*100:>6.1f}% │ {td*100:>6.1f}% │ {ac:>5.1f}d │ {bt*100:>5.2f}% │ {tt*100:>5.2f}% │")

    print(bar)

    # 最佳策略标记
    best_ag = max(averages.keys(), key=lambda n: np.mean([v["agreement"] for v in averages[n]]))
    best_switch = min(averages.keys(), key=lambda n: np.mean([v["tg_turnover"] for v in averages[n]]))
    print(f"  一致率最佳: {best_ag}  |  信号最稳定: {best_switch}")
    print(f"  基线: price>EMA200 + EMA斜率>0.001 + DI+>DI- + ADX>25")


def print_market_report(
    label: str, market_dir: str, tf: str, start: str, end: str, warmup: int, min_bars: int
):
    """发现品种、运行分析、输出一个市场的报告."""
    symbols = discover_symbols(market_dir, tf, min_bars, start, end)
    if not symbols:
        print(f"\n  ⚠ {label}: 无满足最低 bar 数的品种")
        return

    baseline = BaselineStrategy()
    all_results = {}
    max_n_bars = 0

    print(f"\n  发现 {len(symbols)} 个 {tf} 品种，开始分析...", end="", flush=True)

    for sym_name, n_total in symbols:
        path = PROJECT_ROOT / "data" / market_dir / sym_name / f"{tf}.parquet"
        df = pd.read_parquet(path)
        df = _flatten_columns(df)
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        df = df.sort_index()
        mask = (df.index >= start) & (df.index <= end)
        df = df[mask].copy()

        bl = baseline.analyze_signal(df)
        strategies = {}
        for name, func in STRATEGIES.items():
            try:
                tg = func(df)
                m = compute_alignment(bl, tg, warmup=warmup)
                if m:
                    strategies[name] = m
            except Exception:
                continue

        if strategies:
            all_results[sym_name] = strategies
            if len(df) > max_n_bars:
                max_n_bars = len(df)

    print(f" 完成 ({len(all_results)}/{len(symbols)} 有效)")

    if all_results:
        n_bars = max_n_bars - warmup
        print_section(label, all_results, n_bars, len(all_results))
    else:
        print(f"  ⚠ {label}: 所有品种分析失败")


# ── 6. 主函数 ───────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="趋势策略 vs 基线对比（自动发现全品种）")
    parser.add_argument("--markets", default="all", choices=["all", "futures", "etf", "stocks", "hk"])
    parser.add_argument("--list", action="store_true", help="仅列出可用数据")
    args = parser.parse_args()

    if args.list:
        print(f"\n  {'市场':<20} {'品种数':>8} {'周期':>6}")
        print(f"  {'=' * 40}")
        for label, market_dir, tf, start, end, warmup, min_bars in MARKET_CFG:
            syms = discover_symbols(market_dir, tf, min_bars, start, end)
            print(f"  {label:<20} {len(syms):>8} {tf:>6}")
            for name, nb in syms[:3]:
                print(f"    {name:<25} {nb} bars")
            if len(syms) > 3:
                print(f"    ... 还有 {len(syms) - 3} 个")
        return

    print(f"  ========================================")
    print(f"  全市场趋势策略基准对比")
    print(f"  基线: price>EMA200 + EMA斜率↑ + DI+>DI- + ADX>25")
    print(f"  对比: MTES v4 / EMA Cross / MACD / SuperTrend")
    print(f"  ========================================")

    for label, market_dir, tf, start, end, warmup, min_bars in MARKET_CFG:
        if args.markets == "futures" and market_dir not in ("us_futures", "cn_futures"):
            continue
        if args.markets == "etf" and market_dir not in ("cn_etf", "etf"):
            continue
        if args.markets == "stocks" and market_dir != "us_stocks":
            continue
        if args.markets == "hk" and market_dir != "hk_stocks":
            continue

        print(f"\n  ───── {label} ─────")
        try:
            print_market_report(label, market_dir, tf, start, end, warmup, min_bars)
        except Exception as e:
            print(f"  ❌ {label}: {e}")


if __name__ == "__main__":
    main()
