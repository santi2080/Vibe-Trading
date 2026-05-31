#!/usr/bin/env python3
"""
MTES 趋势判断能力测试脚本

测试 MTES 作为趋势方向判断工具的能力：
1. 方向一致性：MTES vs EMA/ADX/MACD 在同一时刻的方向判断是否一致
2. 信号领先/滞后：MTES 先说趋势转换，其他指标多久后才跟上
3. 噪音过滤：MTES 判断 NEUTRAL 时，其他指标切换多频繁
4. 强度相关性：MTES 强度分数与其他指标数值的相关性

用法:
    python scripts/test_mtes_trend_indicator.py
    python scripts/test_mtes_trend_indicator.py --symbols GC=F ES=F --start 2024-01-01 --end 2025-05-01
    python scripts/test_mtes_trend_indicator.py --debug --symbols GC=F
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from src.analysis.major_trend_evaluator import MajorTrendEvaluator, calculate_adx, TrendState


# ──────────────────────────────────────────────────────────────────
# 1. 各指标方向计算
# ──────────────────────────────────────────────────────────────────

def ema_direction(close: np.ndarray, fast: int = 50, slow: int = 200) -> np.ndarray:
    """EMA 双均线方向: 1=多头, -1=空头, 0=不确定."""
    ema_f = pd.Series(close).ewm(span=fast, adjust=False).mean().values
    ema_s = pd.Series(close).ewm(span=slow, adjust=False).mean().values
    diff = ema_f - ema_s
    # 快线在慢线上方为多头，但趋势要明显（差距 > 0.5%）
    signal = np.where(ema_f > ema_s * 1.005, 1,
                 np.where(ema_f < ema_s * 0.995, -1, 0))
    return signal


def adx_direction(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   period: int = 14) -> tuple[np.ndarray, np.ndarray]:
    """ADX 方向: (direction, adx_value). direction: 1=趋势强, -1=趋势弱, 0=震荡."""
    adx_vals, plus_di, minus_di = calculate_adx._calculate_adx_impl(
        pd.DataFrame({"high": high, "low": low, "close": close}), period)
    adx_vals = adx_vals.values
    plus_di = plus_di.values
    minus_di = minus_di.values

    direction = np.where(
        (adx_vals > 25) & (plus_di > minus_di), 1,
        np.where(
            (adx_vals > 25) & (minus_di > plus_di), -1, 0))
    return direction, adx_vals


def macd_direction(close: np.ndarray,
                   fast: int = 12, slow: int = 26, signal: int = 9) -> np.ndarray:
    """MACD 方向: DIF > 0 为多头, < 0 为空头."""
    ema_f = pd.Series(close).ewm(span=fast, adjust=False).mean().values
    ema_s = pd.Series(close).ewm(span=slow, adjust=False).mean().values
    macd_line = ema_f - ema_s
    signal_line = pd.Series(macd_line).ewm(span=signal, adjust=False).mean().values
    direction = np.where(macd_line > 0, 1, np.where(macd_line < 0, -1, 0))
    return direction


def atr_percent(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                period: int = 14) -> np.ndarray:
    """ATR 占价格的百分比."""
    tr = np.maximum(
        high - low,
        np.abs(high - np.roll(close, 1)),
        np.abs(low - np.roll(close, 1)),
    )
    tr[0] = high[0] - low[0]
    atr = pd.Series(tr).rolling(period).mean().values
    return atr / close * 100


def mtes_direction(scores: np.ndarray, states: np.ndarray) -> np.ndarray:
    """MTES 方向: BULL->1, BEAR->-1, NEUTRAL->0."""
    direction = np.zeros(len(scores), dtype=int)
    for i in range(len(scores)):
        s = states[i] if i < len(states) else states[-1] if len(states) > 0 else "UNKNOWN"
        if s in ("BULL_STRONG", "BULL_CONFIRMED", "BULL_EARLY"):
            direction[i] = 1
        elif s in ("BEAR_STRONG", "BEAR_CONFIRMED", "BEAR_EARLY"):
            direction[i] = -1
        else:
            direction[i] = 0
    return direction


# ──────────────────────────────────────────────────────────────────
# 2. 数据加载
# ──────────────────────────────────────────────────────────────────

def load_data(symbol: str, start: str | None, end: str) -> pd.DataFrame | None:
    """从本地 Parquet 加载 OHLCV 数据."""
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
            PROJECT_ROOT / "data" / "us_futures" / f"{sym}=F" / "1d.parquet",
            PROJECT_ROOT / "data" / "etf" / sym / "1d.parquet",
        ]

    for path in candidates:
        if path.exists():
            df = pd.read_parquet(path)
            if isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            elif "timestamp" in df.columns:
                df = df.set_index("timestamp")
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            # 标准化列名
            rename = {c: c.lower() for c in df.columns if c != c.lower()}
            if rename:
                df = df.rename(columns=rename)

            # 过滤日期范围
            mask = df.index <= pd.to_datetime(end)
            if start:
                mask &= df.index >= pd.to_datetime(start)
            return df[mask].copy()
    return None


# ──────────────────────────────────────────────────────────────────
# 3. 核心分析
# ──────────────────────────────────────────────────────────────────

@dataclass
class IndicatorSignals:
    dates: np.ndarray           # 日期
    close: np.ndarray           # 收盘价
    mtes_dir: np.ndarray        # MTES 方向: 1/-1/0
    mtes_score: np.ndarray      # MTES 强度分数
    mtes_state: np.ndarray      # MTES 状态标签
    ema_dir: np.ndarray         # EMA 方向
    adx_dir: np.ndarray         # ADX 方向
    adx_val: np.ndarray         # ADX 数值
    macd_dir: np.ndarray        # MACD 方向
    atr_pct: np.ndarray         # ATR%


def compute_signals(df: pd.DataFrame, mtes_warmup: int = 200) -> IndicatorSignals:
    """对 OHLCV 数据计算所有指标方向信号."""
    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    dates = df.index.values

    n = len(df)
    mtes_dir = np.zeros(n, dtype=int)
    mtes_score = np.full(n, np.nan)
    mtes_state = np.array(["UNKNOWN"] * n, dtype=object)

    evaluator = MajorTrendEvaluator()

    for i in range(mtes_warmup, n):
        window = df.iloc[: i + 1]
        try:
            result = evaluator.evaluate(window, asset_class="futures",
                                     base_timeframe="1d", higher_timeframe_name="1w")
            s = result.trend_state.value if hasattr(result.trend_state, "value") else result.trend_state
            mtes_state[i] = s
            mtes_score[i] = result.trend_score
            if s in ("BULL_STRONG", "BULL_CONFIRMED", "BULL_EARLY"):
                mtes_dir[i] = 1
            elif s in ("BEAR_STRONG", "BEAR_CONFIRMED", "BEAR_EARLY"):
                mtes_dir[i] = -1
        except Exception:
            pass

    return IndicatorSignals(
        dates=dates,
        close=close,
        mtes_dir=mtes_dir,
        mtes_score=mtes_score,
        mtes_state=mtes_state,
        ema_dir=ema_direction(close),
        adx_dir=adx_direction(high, low, close)[0],
        adx_val=adx_direction(high, low, close)[1],
        macd_dir=macd_direction(close),
        atr_pct=atr_percent(high, low, close),
    )


# ──────────────────────────────────────────────────────────────────
# 4. 分析函数
# ──────────────────────────────────────────────────────────────────

def direction_consistency(sig: IndicatorSignals) -> dict:
    """分析方向一致性."""
    n = len(sig.dates)
    warmup = int(mtes_warmup_from_states(sig.mtes_state))

    # 各指标方向数组（转成 1/-1/0 格式）
    others = {
        "EMA(50/200)": sig.ema_dir,
        "ADX(14)>25": sig.adx_dir,
        "MACD(12/26)": sig.macd_dir,
    }

    results = {}
    for name, direction in others.items():
        agree = (sig.mtes_dir == direction) & (sig.mtes_dir != 0)
        total = (sig.mtes_dir != 0).sum()
        consistency = agree.sum() / total if total > 0 else 0.0
        results[name] = {
            "一致率": f"{consistency:.1%}",
            "一致次数": int(agree.sum()),
            "MTES信号数": int(total),
        }

    return results


def signal_lead_lag(sig: IndicatorSignals) -> dict:
    """分析 MTES 信号领先/滞后其他指标多少根 bar."""
    others = {
        "EMA(50/200)": sig.ema_dir,
        "ADX(14)>25": sig.adx_dir,
        "MACD(12/26)": sig.macd_dir,
    }

    results = {}
    for name, direction in others.items():
        lags = []
        # 找 MTES 从 0→1 或 0→-1 的时刻
        for i in range(1, len(sig.mtes_dir)):
            if sig.mtes_dir[i] != 0 and sig.mtes_dir[i - 1] == 0:
                # MTES 在 i 发出信号，向后找其他指标跟上
                for j in range(i, min(i + 60, len(direction))):
                    if direction[j] == sig.mtes_dir[i]:
                        lags.append(j - i)
                        break
        results[name] = {
            "平均滞后(天)": f"{np.mean(lags):.1f}" if lags else "N/A",
            "最大滞后(天)": f"{max(lags)}" if lags else "N/A",
            "领先次数": len([l for l in lags if l == 0]),
            "样本数": len(lags),
        }
    return results


def noise_filter_analysis(sig: IndicatorSignals) -> dict:
    """分析噪音过滤：MTES=NEUTRAL 时，其他指标切换多频繁。"""
    neutral_mask = sig.mtes_dir == 0
    others = {
        "EMA(50/200)": sig.ema_dir,
        "ADX(14)>25": sig.adx_dir,
        "MACD(12/26)": sig.macd_dir,
    }

    results = {}
    for name, direction in others.items():
        # 统计 neutral 区间的方向切换次数
        n_switches = 0
        n_segments = 0
        in_neutral = False
        for i in range(len(sig.dates)):
            if neutral_mask[i]:
                if not in_neutral:
                    in_neutral = True
                    n_segments += 1
                if i > 0 and direction[i] != direction[i - 1]:
                    n_switches += 1
            else:
                in_neutral = False

        # 每月切换次数
        dates_series = pd.to_datetime(sig.dates)
        n_months = max(1, (dates_series[-1] - dates_series[0]).days / 30)
        monthly_switches = n_switches / n_months

        results[name] = {
            "NEUTRAL区间月均切换": f"{monthly_switches:.1f}",
            "NEUTRAL区间总切换": int(n_switches),
            "NEUTRAL区间数": n_segments,
            "月数": f"{n_months:.1f}",
        }
    return results


def intensity_correlation(sig: IndicatorSignals) -> dict:
    """分析 MTES 强度分数与其他指标数值的相关性。"""
    valid = ~np.isnan(sig.mtes_score) & (sig.adx_val > 0)
    if valid.sum() < 30:
        return {}

    score = sig.mtes_score[valid]
    adx = sig.adx_val[valid]

    corr = float(np.corrcoef(score, adx)[0, 1])
    corr = corr if np.isfinite(corr) else 0.0

    # MTES 强度分段统计 ADX 均值
    high_score = sig.mtes_score[sig.mtes_score >= 65]
    mid_score = sig.mtes_score[(sig.mtes_score >= 50) & (sig.mtes_score < 65)]
    low_score = sig.mtes_score[(sig.mtes_score >= 0) & (sig.mtes_score < 50)]
    neutral_score = sig.mtes_score[sig.mtes_score == 0]

    return {
        "MTES强度 vs ADX 相关系数": f"{corr:.2f}",
        "高强度(score≥65)平均ADX": f"{np.mean(sig.adx_val[(~np.isnan(sig.mtes_score)) & (sig.mtes_score >= 65]):.1f}",
        "中强度(50≤score<65)平均ADX": f"{np.mean(sig.adx_val[(~np.isnan(sig.mtes_score)) & (sig.mtes_score >= 50) & (sig.mtes_score < 65)]):.1f}",
        "低强度(score<50)平均ADX": f"{np.mean(sig.adx_val[(~np.isnan(sig.mtes_score)) & (sig.mtes_score < 50)]):.1f}",
    }


def trend_state_summary(sig: IndicatorSignals) -> dict:
    """MTES 七状态分布统计。"""
    from collections import Counter
    valid_states = [s for s in sig.mtes_state if s != "UNKNOWN"]
    dist = Counter(valid_states)
    total = len(valid_states)
    return {
        f"{state}: {count} ({count/total*100:.0f}%)": None
        for state, count in dist.most_common()
    }


def mtes_warmup_from_states(states: np.ndarray) -> int:
    """从状态数组找到第一个非 UNKNOWN 的索引。"""
    for i, s in enumerate(states):
        if s != "UNKNOWN":
            return i
    return len(states)


# ──────────────────────────────────────────────────────────────────
# 5. 打印输出
# ──────────────────────────────────────────────────────────────────

def print_report(symbol: str, sig: IndicatorSignals,
                start: str, end: str,
                consistency: dict, lead_lag: dict,
                noise: dict, intensity: dict):
    """打印完整报告。"""
    print(f"\n{'='*80}")
    print(f"  品种: {symbol}  |  时间: {start} ~ {end}  |  数据: {len(sig.dates)} 天")
    print(f"{'='*80}")

    # MTES 状态分布
    print(f"\n【1. MTES 趋势状态分布】")
    print(f"  {'状态':<18} {'天数':>6} {'占比':>6}")
    print(f"  {'-'*18} {'-'*6} {'-'*6}")
    from collections import Counter
    valid = [(s, c) for s, c in Counter(
        [x for x in sig.mtes_state if x != "UNKNOWN"]).most_common()]
    total = sum(c for _, c in valid)
    for state, count in valid:
        print(f"  {state:<18} {count:>6} {count/total*100:>5.0f}%")
    print(f"  {'有效信号占比':<18} {total:>6} {total/len(sig.mtes_state)*100:>5.0f}%")

    # 方向一致性
    print(f"\n【2. 方向一致性】（MTES 非 NEUTRAL 时，各指标方向一致率）")
    print(f"  {'指标':<18} {'一致率':>8} {'一致次数':>9} {'MTES信号数':>10}")
    print(f"  {'-'*18} {'-'*8} {'-'*9} {'-'*10}")
    for name, stats in consistency.items():
        print(f"  {name:<18} {stats['一致率']:>8} {stats['一致次数']:>9} {stats['MTES信号数']:>10}")

    # 领先/滞后
    print(f"\n【3. 信号领先/滞后】（MTES 发出方向信号后，其他指标跟上的速度）")
    print(f"  {'指标':<18} {'平均滞后':>10} {'最大滞后':>10} {'领先次数':>8} {'样本数':>8}")
    print(f"  {'-'*18} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    for name, stats in lead_lag.items():
        print(f"  {name:<18} {stats['平均滞后(天)']:>10} {stats['最大滞后(天)']:>10} "
              f"{stats['领先次数']:>8} {stats['样本数']:>8}")

    # 噪音过滤
    print(f"\n【4. 噪音过滤】（MTES=NEUTRAL 时，其他指标方向切换频率）")
    print(f"  {'指标':<18} {'月均切换':>10} {'总切换':>8} {'区间数':>8} {'月数':>8}")
    print(f"  {'-'*18} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
    for name, stats in noise.items():
        print(f"  {name:<18} {stats['NEUTRAL区间月均切换']:>10} "
              f"{stats['NEUTRAL区间总切换']:>8} {stats['NEUTRAL区间数']:>8} {stats['月数']:>8}")

    # 强度相关性
    print(f"\n【5. MTES 强度 vs ADX 相关性】")
    for k, v in intensity.items():
        if v:
            print(f"  {k:<35} {v}")


def print_sample_table(sig: IndicatorSignals, n: int = 30):
    """打印最近 n 天的方向判断对比表。"""
    print(f"\n【样本：最近 {n} 天方向判断对比】")
    print(f"  {'日期':<12} {'收盘价':>10} {'MTES状态':<16} {'MTES分':>5} {'MTES方向':>7} "
          f"{'EMA方向':>7} {'ADX方向':>7} {'MACD方向':>7} {'一致':>4}")
    print(f"  {'-'*12} {'-'*10} {'-'*16} {'-'*5} {'-'*7} "
          f"{'-'*7} {'-'*7} {'-'*7} {'-'*4}")

    dirs = {"1": "BULL", "-1": "BEAR", "0": "NEUT"}
    start = max(0, len(sig.dates) - n)
    for i in range(start, len(sig.dates)):
        mtes_s = sig.mtes_state[i]
        mtes_d = sig.mtes_dir[i]
        ema = sig.ema_dir[i]
        adx = sig.adx_dir[i]
        macd = sig.macd_dir[i]
        agree = "✅" if mtes_d in (ema, adx, macd) and mtes_d != 0 else "⚠️"
        score = f"{sig.mtes_score[i]:.0f}" if not np.isnan(sig.mtes_score[i]) else "N/A"
        print(f"  {str(pd.Timestamp(sig.dates[i]).date():<12} "
              f"{sig.close[i]:>10.2f} {str(mtes_s):<16} {score:>5} "
              f"{dirs.get(str(mtes_d), '?'):>7} "
              f"{dirs.get(str(ema), '?'):>7} "
              f"{dirs.get(str(adx), '?'):>7} "
              f"{dirs.get(str(macd), '?'):>7} "
              f"{agree:>4}")


# ──────────────────────────────────────────────────────────────────
# 6. 主程序
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MTES 趋势判断能力测试")
    parser.add_argument("--symbols", nargs="+", default=["GC=F", "ES=F", "CL=F"],
                        help="品种列表，默认: GC=F ES=F CL=F")
    parser.add_argument("--start", default="2024-01-01",
                        help="开始日期，默认: 2024-01-01")
    parser.add_argument("--end", default="2025-05-27",
                        help="结束日期，默认: 2025-05-27")
    parser.add_argument("--mtes-warmup", type=int, default=200,
                        help="MTES warmup bar，默认: 200")
    parser.add_argument("--debug", action="store_true",
                        help="显示样本对比表")
    args = parser.parse_args()

    print("=" * 80)
    print("  MTES 趋势判断能力测试报告".center(70))
    print("=" * 80)
    print(f"\n配置: MTES warmup={args.mtes_warmup} bar, 日期: {args.start} ~ {args.end}")

    for symbol in args.symbols:
        df = load_data(symbol, args.start, args.end)
        if df is None or len(df) < 100:
            print(f"\n⚠️  {symbol}: 数据不足或文件不存在，跳过")
            continue

        print(f"\n📊 {symbol}: 加载 {len(df)} 条数据 ({df.index[0].date()} ~ {df.index[-1].date()})")

        sig = compute_signals(df, mtes_warmup=args.mtes_warmup)

        consistency = direction_consistency(sig)
        lead_lag = signal_lead_lag(sig)
        noise = noise_filter_analysis(sig)
        intensity = intensity_correlation(sig)

        print_report(symbol, sig, str(df.index[0].date()), str(df.index[-1].date()),
                    consistency, lead_lag, noise, intensity)

        if args.debug:
            print_sample_table(sig, n=30)

    print(f"\n{'='*80}")
    print("测试完成")
    print("提示: 一致率越高说明 MTES 与传统指标方向判断越吻合；")
    print("      领先次数越多说明 MTES 提前发出趋势信号；")
    print("      NEUTRAL 区间切换越少说明 MTES 过滤噪音能力越强。")


if __name__ == "__main__":
    main()
