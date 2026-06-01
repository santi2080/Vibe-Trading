#!/usr/bin/env python3
"""
MTES v2 vs v3 性能对比测试

使用真实市场数据进行对比分析。
"""
import pandas as pd
import numpy as np
import time
from pathlib import Path

# MTES v2
from agent.src.analysis.major_trend_evaluator import MajorTrendEvaluator, MajorTrendConfig

# MTES v3
from agent.src.analysis.mtes_v3 import MTESv3, MTESv3Config


def load_data(symbol: str, timeframe: str = "1d") -> pd.DataFrame:
    """加载市场数据"""
    data_dir = Path("data/us_futures")
    parquet_path = data_dir / symbol / f"{timeframe}.parquet"

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        df.columns = df.columns.str.lower()
        return df

    # 尝试 CSV
    csv_path = data_dir / symbol / f"{timeframe}.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.lower()
        return df

    return None


def benchmark(func, df: pd.DataFrame, iterations: int = 10) -> dict:
    """性能基准测试"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = func(df)
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # ms

    return {
        "mean_ms": np.mean(times),
        "std_ms": np.std(times),
        "min_ms": np.min(times),
        "max_ms": np.max(times),
        "iterations": iterations
    }


def analyze_v2(df: pd.DataFrame) -> dict:
    """MTES v2 分析"""
    config = MajorTrendConfig(asset_class="futures", use_v2_scoring=True)
    evaluator = MajorTrendEvaluator(config)
    result = evaluator.evaluate(df)

    return {
        "direction": result.direction,
        "trend_state": result.trend_state,
        "score": result.trend_score,
        "confidence": result.confidence,
        "regime": result.regime
    }


def analyze_v3(df: pd.DataFrame) -> dict:
    """MTES v3 分析"""
    config = MTESv3Config()
    mtes = MTESv3(config)
    result = mtes.analyze(df)

    return {
        "direction": result.mtf_trend.direction,
        "trend_state": result.strength.rating,
        "score": result.final_score,
        "confidence": result.final_confidence,
        "regime": result.strength.regime
    }


def main():
    print("=" * 60)
    print("MTES v2 vs v3 性能对比测试")
    print("=" * 60)

    # 测试品种
    symbols = ["ES=F", "NQ=F", "GC=F", "SI=F", "CL=F"]

    results = []

    for symbol in symbols:
        print(f"\n📊 测试品种: {symbol}")
        print("-" * 40)

        df = load_data(symbol)
        if df is None:
            print(f"  ⚠️  数据不存在，跳过")
            continue

        print(f"  数据点数: {len(df)}")

        # 性能测试
        v2_bench = benchmark(analyze_v2, df, iterations=10)
        v3_bench = benchmark(analyze_v3, df, iterations=10)

        # 信号对比
        v2_result = analyze_v2(df)
        v3_result = analyze_v3(df)

        print(f"\n  性能对比:")
        print(f"    MTES v2: {v2_bench['mean_ms']:.2f}ms (±{v2_bench['std_ms']:.2f})")
        print(f"    MTES v3: {v3_bench['mean_ms']:.2f}ms (±{v3_bench['std_ms']:.2f})")

        speedup = v2_bench['mean_ms'] / v3_bench['mean_ms'] if v3_bench['mean_ms'] > 0 else 0
        print(f"    速度比: {speedup:.2f}x")

        print(f"\n  信号对比:")
        print(f"    MTES v2: direction={v2_result['direction']}, score={v2_result['score']:.1f}, confidence={v2_result['confidence']:.2f}")
        print(f"    MTES v3: direction={v3_result['direction']}, score={v3_result['score']:.1f}, confidence={v3_result['confidence']:.2f}")

        # 信号一致性
        match = "✅" if v2_result['direction'] == v3_result['direction'] else "❌"
        print(f"    信号一致: {match}")

        results.append({
            "symbol": symbol,
            "data_points": len(df),
            "v2_ms": v2_bench['mean_ms'],
            "v3_ms": v3_bench['mean_ms'],
            "speedup": speedup,
            "v2_direction": v2_result['direction'],
            "v3_direction": v3_result['direction'],
            "direction_match": v2_result['direction'] == v3_result['direction']
        })

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)

    results_df = pd.DataFrame(results)

    avg_speedup = results_df['speedup'].mean()
    match_rate = results_df['direction_match'].sum() / len(results_df) * 100

    print(f"\n平均速度比: {avg_speedup:.2f}x")
    print(f"信号一致率: {match_rate:.0f}%")
    print(f"\n详细数据:")
    print(results_df.to_string(index=False))

    # 保存结果
    results_df.to_csv("reports/mtes_v2v3_comparison.csv", index=False)
    print(f"\n结果已保存到: reports/mtes_v2v3_comparison.csv")


if __name__ == "__main__":
    main()
