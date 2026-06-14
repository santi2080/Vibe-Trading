#!/usr/bin/env python3
"""
MTES v4 vs EMA200斜率+ADX(14)>25 基准趋势策略对比脚本

对 US Futures 8 个品种逐品种比较趋势方向一致性和冲突率。

基准策略逻辑:
  1. 计算 EMA200 的 5 日斜率
  2. 斜率 > 0.001 且 ADX(14) > 25 → BULL
  3. 斜率 < -0.001 且 ADX(14) > 25 → BEAR
  4. 其余 → NEUTRAL

MTES v4 信号映射:
  STRONG_LONG    → BULL
  CAUTIOUS_LONG  → BULL
  STRONG_SHORT   → BEAR
  CAUTIOUS_SHORT → BEAR
  WAIT           → NEUTRAL
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from collections import Counter


# ── 1. 基准策略 ──────────────────────────────────────────────────


class BaselineTrendStrategy:
    """EMA200 斜率 + ADX(14)>25 基准趋势策略."""

    def __init__(self, ema_span: int = 200, slope_days: int = 5,
                 slope_threshold: float = 0.001, adx_threshold: float = 25.0,
                 adx_period: int = 14):
        self.ema_span = ema_span
        self.slope_days = slope_days
        self.slope_threshold = slope_threshold
        self.adx_threshold = adx_threshold
        self.adx_period = adx_period

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """返回带信号列的 DataFrame."""
        result = df[["close", "high", "low"]].copy()

        # EMA200
        result["ema"] = result["close"].ewm(span=self.ema_span, adjust=False).mean()

        # EMA200 斜率 (5日变化率)
        result["ema_slope"] = (result["ema"] - result["ema"].shift(self.slope_days)) / result["ema"].shift(self.slope_days)

        # ADX(14) + DI+/DI-
        result["adx"], result["plus_di"], result["minus_di"] = self._adx(df, self.adx_period)

        # 信号: 价格>EMA200 AND EMA斜率向上 AND +DI>-DI AND ADX>25 → BULL
        #       价格<EMA200 AND EMA斜率向下 AND -DI>+DI AND ADX>25 → BEAR
        bull = (
            (result["close"] > result["ema"])
            & (result["ema_slope"] > self.slope_threshold)
            & (result["plus_di"] > result["minus_di"])
            & (result["adx"] > self.adx_threshold)
        )
        bear = (
            (result["close"] < result["ema"])
            & (result["ema_slope"] < -self.slope_threshold)
            & (result["minus_di"] > result["plus_di"])
            & (result["adx"] > self.adx_threshold)
        )

        result["signal"] = np.select([bull, bear], [1, -1], default=0)

        return result

    @staticmethod
    def _adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
        """计算 ADX, +DI, -DI 序列."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        # True Range
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        tr[1:] = np.maximum(np.maximum(tr1, tr2), tr3)

        # Directional Movement
        up_move = np.maximum(high[1:] - high[:-1], 0)
        down_move = np.maximum(low[:-1] - low[1:], 0)
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Wilder smoothing
        alpha = 1.0 / period
        smooth_tr = np.full(n, np.nan)
        smooth_plus = np.full(n, np.nan)
        smooth_minus = np.full(n, np.nan)

        if n > period:
            smooth_tr[period] = np.nansum(tr[1:period + 1])
            smooth_plus[period] = np.nansum(plus_dm[:period])
            smooth_minus[period] = np.nansum(minus_dm[:period])

            for i in range(period + 1, n):
                smooth_tr[i] = (1 - alpha) * smooth_tr[i - 1] + alpha * tr[i]
                smooth_plus[i] = (1 - alpha) * smooth_plus[i - 1] + alpha * (high[i] - high[i - 1] if i > 0 else 0)
                smooth_minus[i] = (1 - alpha) * smooth_minus[i - 1] + alpha * (low[i - 1] - low[i] if i > 0 else 0)

        plus_di = 100 * smooth_plus / np.where(smooth_tr > 0, smooth_tr, 1)
        minus_di = 100 * smooth_minus / np.where(smooth_tr > 0, smooth_tr, 1)
        dx = 100 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) > 0, plus_di + minus_di, 1)

        adx = np.full(n, np.nan)
        if n > period * 2:
            adx[period * 2] = np.nanmean(dx[period:period * 2])
            for i in range(period * 2 + 1, n):
                adx[i] = (1 - alpha) * adx[i - 1] + alpha * dx[i]

        return (
            pd.Series(adx, index=df.index),
            pd.Series(plus_di, index=df.index),
            pd.Series(minus_di, index=df.index),
        )


# ── 2. MTES v4 包装 ─────────────────────────────────────────────


class MTESv4TrendWrapper:
    """LeanMTES 到信号 (-1/0/1) 的适配."""

    def __init__(self):
        from src.analysis.mtes_v4 import LeanMTES
        self.mtes = LeanMTES()

    def analyze(self, df: pd.DataFrame) -> pd.Series:
        """逐 bar 分析，返回信号序列."""
        signals = pd.Series(0, index=df.index)
        # MTES v4 需要最低约 80 bar
        warmup = 90

        for i in range(warmup, len(df)):
            window = df.iloc[:i + 1]
            try:
                res = self.mtes.analyze(window)
                signal = MTESv4TrendWrapper._action_to_signal(res.action_bias)
                signals.iloc[i] = signal
            except Exception:
                signals.iloc[i] = 0

        return signals

    @staticmethod
    def _action_to_signal(action_bias: str) -> int:
        if action_bias in ("STRONG_LONG", "CAUTIOUS_LONG"):
            return 1
        elif action_bias in ("STRONG_SHORT", "CAUTIOUS_SHORT"):
            return -1
        return 0


# ── 3. 对比计算 ──────────────────────────────────────────────────


def compute_alignment(
    df: pd.DataFrame,
    baseline_signal: pd.Series,
    mtes_signal: pd.Series,
    warmup: int = 220,
) -> dict:
    """计算两策略的方向一致性和冲突率."""
    bl = baseline_signal.iloc[warmup:]
    mt = mtes_signal.iloc[warmup:]

    valid = bl.notna() & mt.notna()
    bl, mt = bl[valid], mt[valid]

    n = len(bl)
    if n == 0:
        return {"error": "no valid data"}

    # 方向统计
    bl_bull = (bl == 1).sum()
    bl_bear = (bl == -1).sum()
    bl_neutral = (bl == 0).sum()
    mt_bull = (mt == 1).sum()
    mt_bear = (mt == -1).sum()
    mt_neutral = (mt == 0).sum()

    # 一致率
    same = (bl == mt).sum()
    agreement = same / n

    # 冲突：一方看多一方看空
    conflict = ((bl == 1) & (mt == -1)) | ((bl == -1) & (mt == 1))
    conflict_rate = conflict.sum() / n

    # 其中 MTES 看空但基准看多的比例
    mtes_bear_bl_bull = ((bl == 1) & (mt == -1)).sum()
    mtes_bull_bl_bear = ((bl == -1) & (mt == 1)).sum()

    # 信号切换次数（稳定性）
    bl_switch = (bl.diff() != 0).sum()
    mt_switch = (mt.diff() != 0).sum()
    bl_turnover = bl_switch / n
    mt_turnover = mt_switch / n

    # 平均连续一致天数
    runs = (bl == mt).astype(int)
    run_lengths = []
    current = 0
    for v in runs.values:
        if v:
            current += 1
        else:
            if current > 0:
                run_lengths.append(current)
                current = 0
    if current > 0:
        run_lengths.append(current)
    avg_consecutive = np.mean(run_lengths) if run_lengths else 0.0

    return {
        "n_bars": n,
        "baseline_bull_pct": bl_bull / n,
        "baseline_bear_pct": bl_bear / n,
        "baseline_neutral_pct": bl_neutral / n,
        "mtes_bull_pct": mt_bull / n,
        "mtes_bear_pct": mt_bear / n,
        "mtes_neutral_pct": mt_neutral / n,
        "agreement": agreement,
        "conflict_rate": conflict_rate,
        "mtes_bear_vs_bl_bull": mtes_bear_bl_bull / n,
        "mtes_bull_vs_bl_bear": mtes_bull_bl_bear / n,
        "baseline_turnover": bl_turnover,
        "mtes_turnover": mt_turnover,
        "avg_consecutive_agreement": avg_consecutive,
    }


# ── 4. 输出 ──────────────────────────────────────────────────────

HEADER_FMT = "│ {:<6} │ {:>6} │ {:>6} │ {:>6} │ {:>6} │ {:>6} │ {:>18} │ {:>6} │ {:>6} │ {:>6} │"
ROW_FMT = "│ {:<6} │ {:>5.1f}% │ {:>5.1f}% │ {:>5.1f}% │ {:>5.1f}% │ {:>5.1f}% │ {:>18} │ {:>5.1f}d │ {:>5.2f}% │ {:>5.2f}% │"


def print_report(symbol: str, m: dict, start: str, end: str):
    """打印单品种对比."""
    bar = "─" * 98
    print(f"\n{bar}")
    print(f"  {symbol}  对比报告 ({start} ~ {end})  ({m['n_bars']} bars)")
    print(bar)
    print(f"{'':<6} | {'看多':>6} | {'看空':>6} | {'中性':>6} | {'一致':>6} | {'冲突':>6} | {'冲突(多空)':>8} | {'连续一致':>8} | {'换手':>6} | {'换手':>6}")
    print(f"{'':<6} | {'':>6} | {'':>6} | {'':>6} | {'率':>6} | {'率':>6} | {'':>8} | {'(天)':>8} | {'基准':>6} | {'MTES':>6}")
    conflict_label = "-"
    if m["conflict_rate"] > 0.05:
        if m["mtes_bear_vs_bl_bull"] > m["mtes_bull_vs_bl_bear"]:
            conflict_label = "MT看空基看多"
        else:
            conflict_label = "MT看多基看空"

    print(bar)
    print(f"│ {symbol:<6} │ {m['baseline_bull_pct']*100:>5.1f}% │ {m['baseline_bear_pct']*100:>5.1f}% │ {m['baseline_neutral_pct']*100:>5.1f}% │ {m['agreement']*100:>5.1f}% │ {m['conflict_rate']*100:>5.1f}% │ {conflict_label:>18} │ {m['avg_consecutive_agreement']:>5.1f}d │ {m['baseline_turnover']*100:>5.2f}% │ {m['mtes_turnover']*100:>5.2f}% │")


def print_summary(results: list[tuple[str, dict]], start: str, end: str):
    """打印全品种汇总."""
    bar = "─" * 110
    print(f"\n\n{bar}")
    print(f"  US Futures 汇总 — MTES v4 vs EMA200斜率+ADX(14)>25  ({start} ~ {end})")
    print(bar)
    print(f"{'品种':<6} | {'一致率':>7} | {'冲突率':>7} | {'多(基)':>7} | {'多(MT)':>7} | {'空(基)':>7} | {'空(MT)':>7} | {'连续一致':>7} | {'换手基':>7} | {'换手MT':>7}")
    print(bar)

    for symbol, m in results:
        print(f"│ {symbol:<6} │ {m['agreement']*100:>5.1f}% │ {m['conflict_rate']*100:>5.1f}% │ {m['baseline_bull_pct']*100:>5.1f}% │ {m['mtes_bull_pct']*100:>5.1f}% │ {m['baseline_bear_pct']*100:>5.1f}% │ {m['mtes_bear_pct']*100:>5.1f}% │ {m['avg_consecutive_agreement']:>6.1f}d │ {m['baseline_turnover']*100:>5.2f}% │ {m['mtes_turnover']*100:>5.2f}% │")

    # 汇总平均
    avg_agreement = np.mean([m["agreement"] for _, m in results])
    avg_conflict = np.mean([m["conflict_rate"] for _, m in results])
    avg_consecutive = np.mean([m["avg_consecutive_agreement"] for _, m in results])

    print(bar)
    print(f"│ 平均    │ {avg_agreement*100:>5.1f}% │ {avg_conflict*100:>5.1f}% │ {np.mean([m['baseline_bull_pct'] for _, m in results])*100:>5.1f}% │ {np.mean([m['mtes_bull_pct'] for _, m in results])*100:>5.1f}% │ {np.mean([m['baseline_bear_pct'] for _, m in results])*100:>5.1f}% │ {np.mean([m['mtes_bear_pct'] for _, m in results])*100:>5.1f}% │ {avg_consecutive:>6.1f}d │ {np.mean([m['baseline_turnover'] for _, m in results])*100:>5.2f}% │ {np.mean([m['mtes_turnover'] for _, m in results])*100:>5.2f}% │")
    print(f"\n  平均一致率: {avg_agreement*100:.1f}%  |  平均冲突率: {avg_conflict*100:.1f}%  |  平均连续一致: {avg_consecutive:.1f}天")


# ── 5. 主函数 ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="MTES v4 vs 基准趋势策略对比")
    parser.add_argument("--symbols", nargs="+", default=[
        "GC=F", "SI=F", "HG=F", "CL=F", "ZC=F", "ZS=F", "ES=F", "NQ=F"
    ], help="品种列表")
    parser.add_argument("--start", default="2024-01-01", help="开始日期")
    parser.add_argument("--end", default="2026-06-14", help="结束日期")
    parser.add_argument("--warmup", type=int, default=100, help="预热 bar 数")
    args = parser.parse_args()

    baseline = BaselineTrendStrategy()
    mtes = MTESv4TrendWrapper()

    results = []
    print(f"\n  加载数据并分析 {len(args.symbols)} 个品种...\n")

    for symbol in args.symbols:
        path = PROJECT_ROOT / "data" / "us_futures" / symbol / "1d.parquet"
        if not path.exists():
            print(f"  ⚠  {symbol}: 数据文件不存在 ({path})")
            continue

        df = pd.read_parquet(path)
        df.columns = df.columns.str.lower()
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        df = df.sort_index()

        # 过滤日期范围
        mask = (df.index >= args.start) & (df.index <= args.end)
        df = df[mask].copy()
        if len(df) < args.warmup:
            print(f"  ⚠  {symbol}: 数据不足 ({len(df)} < {args.warmup})")
            continue

        # 基准策略
        bl_result = baseline.analyze(df)
        bl_signal = bl_result["signal"]

        # MTES v4
        mt_signal = mtes.analyze(df)

        # 对齐到同一比较窗口
        warmup = args.warmup
        bl_v = bl_signal.iloc[warmup:]
        mt_v = mt_signal.iloc[warmup:]

        # 计算比例
        bl_bull_pct = (bl_v == 1).sum() / len(bl_v)
        bl_bear_pct = (bl_v == -1).sum() / len(bl_v)
        mt_bull_pct = (mt_v == 1).sum() / len(mt_v)
        mt_bear_pct = (mt_v == -1).sum() / len(mt_v)

        # 对比
        m = compute_alignment(df, bl_signal, mt_signal, warmup=warmup)
        m["baseline_bull_pct"] = bl_bull_pct
        m["baseline_bear_pct"] = bl_bear_pct
        m["mtes_bull_pct"] = mt_bull_pct
        m["mtes_bear_pct"] = mt_bear_pct

        print_report(symbol, m, args.start, args.end)
        results.append((symbol, m))

    # 汇总
    if results:
        print_summary(results, args.start, args.end)
    else:
        print("  无有效结果。")


if __name__ == "__main__":
    main()
