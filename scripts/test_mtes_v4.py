#!/usr/bin/env python3
"""Test script for MTES V4."""

import sys
from pathlib import Path
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

import pandas as pd
import numpy as np

from src.analysis.mtes_v4 import LeanMTES, LeanMTESConfig


def generate_test_data(
    n_bars: int = 300,
    trend: str = "bull"
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)

    dates = pd.date_range("2024-01-01", periods=n_bars, freq="D")

    if trend == "bull":
        # Upward trend with noise
        base = 100
        returns = np.random.randn(n_bars) * 1.5 + 0.05
    elif trend == "bear":
        # Downward trend with noise
        base = 100
        returns = np.random.randn(n_bars) * 1.5 - 0.05
    else:
        # Sideways with noise
        base = 100
        returns = np.random.randn(n_bars) * 1.0

    close = [base]
    for r in returns[1:]:
        close.append(close[-1] * (1 + r / 100))

    close = np.array(close)

    # Generate OHLC
    high = close * (1 + np.abs(np.random.randn(n_bars) * 0.005))
    low = close * (1 - np.abs(np.random.randn(n_bars) * 0.005))
    open_price = np.roll(high, 1)
    open_price[0] = close[0]

    return pd.DataFrame({
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.random.randint(1000, 10000, n_bars),
    }, index=dates)


def load_real_data(symbol: str = "ES=F") -> pd.DataFrame | None:
    """Load real market data."""
    candidates = [
        PROJECT_ROOT / "data" / "us_futures" / symbol / "1d.parquet",
        PROJECT_ROOT / "data" / "us_futures" / symbol / "1d.csv",
    ]

    for path in candidates:
        if path.exists():
            if path.suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path)

            df.columns = df.columns.str.lower()
            if "timestamp" in df.columns:
                df = df.set_index("timestamp")
            return df.sort_index()

    return None


def run_performance_test():
    """Performance benchmark."""
    print("=" * 60)
    print("MTES V4 Performance Test")
    print("=" * 60)

    # Load real data
    df = load_real_data("ES=F")
    if df is None:
        print("⚠️  No real data, using synthetic data")
        df = generate_test_data(500, "bull")

    print(f"\nData: {len(df)} bars")

    # Test different configurations
    configs = [
        ("Default", LeanMTESConfig()),
        ("Sensitive", LeanMTESConfig(adx_threshold=15.0, adx_strong=25.0)),
        ("Conservative", LeanMTESConfig(adx_threshold=25.0, adx_strong=35.0)),
    ]

    print("\n" + "-" * 60)
    print(f"{'Config':<20} {'Time':>10} {'Direction':>10} {'Score':>10} {'ADX':>8} {'Strength':>10}")
    print("-" * 60)

    for name, config in configs:
        mtes = LeanMTES(config)

        # Warm up
        _ = mtes.analyze(df.iloc[-200:])

        # Benchmark
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            result = mtes.analyze(df)
        elapsed = (time.perf_counter() - start) * 1000 / iterations

        print(f"{name:<20} {elapsed:>10.2f}ms {result.direction.value:>10} "
              f"{result.final_score:>10.1f} {result.adx:>8.1f} {result.strength.value:>10}")


def run_direction_test():
    """Test direction detection on different trend types."""
    print("\n" + "=" * 60)
    print("MTES V4 Direction Test")
    print("=" * 60)

    mtes = LeanMTES()

    trends = ["bull", "bear", "sideways"]
    synthetic_data = {t: generate_test_data(300, t) for t in trends}

    for trend, df in synthetic_data.items():
        result = mtes.analyze(df)

        print(f"\n{trend.upper()} Trend:")
        print(f"  Direction: {result.direction.value}")
        print(f"  Score: {result.final_score:.1f}")
        print(f"  ADX: {result.adx:.1f}")
        print(f"  Strength: {result.strength.value}")
        print(f"  Confidence: {result.confidence:.1%}")
        print(f"  Explanation: {result.explanation}")


def run_comparison_test():
    """Compare with V2."""
    print("\n" + "=" * 60)
    print("MTES V4 vs V2 Comparison")
    print("=" * 60)

    df = load_real_data("ES=F")
    if df is None:
        print("⚠️  Skipping comparison, no real data")
        return

    # V4
    mtes_v4 = LeanMTES()
    result_v4 = mtes_v4.analyze(df)

    # V2 (if available)
    try:
        from src.analysis.major_trend_evaluator import MajorTrendEvaluator, MajorTrendConfig

        config_v2 = MajorTrendConfig(use_v2_scoring=True)
        evaluator_v2 = MajorTrendEvaluator(config_v2)
        result_v2 = evaluator_v2.evaluate(df)
    except Exception as e:
        print(f"⚠️  V2 not available: {e}")
        return

    print(f"\n{'Metric':<25} {'V2':>15} {'V4':>15}")
    print("-" * 55)
    print(f"{'Direction':<25} {result_v2.direction:>15} {result_v4.direction.value:>15}")
    print(f"{'Score':<25} {result_v2.trend_score:>15.1f} {result_v4.final_score:>15.1f}")
    print(f"{'Confidence':<25} {result_v2.confidence:>15.1%} {result_v4.confidence:>15.1%}")
    print(f"{'Match':<25} {'':>15} {'✅' if result_v2.direction == result_v4.direction.value else '❌':>15}")


def run_batch_test():
    """Test on multiple symbols."""
    print("\n" + "=" * 60)
    print("MTES V4 Batch Test (US Futures)")
    print("=" * 60)

    symbols = ["ES=F", "NQ=F", "GC=F", "SI=F", "CL=F"]
    mtes = LeanMTES()

    results = []
    for symbol in symbols:
        df = load_real_data(symbol)
        if df is None:
            print(f"\n{symbol}: ⚠️  No data")
            continue

        # Warm up
        _ = mtes.analyze(df.iloc[-100:])

        start = time.perf_counter()
        result = mtes.analyze(df)
        elapsed = (time.perf_counter() - start) * 1000

        # Market Structure
        mkt = result.market_structure
        mkt_info = f"[{mkt.structure}]" if mkt else "[N/A]"

        results.append({
            "symbol": symbol,
            "direction": result.direction.value,
            "score": result.final_score,
            "adx": result.adx,
            "strength": result.strength.value,
            "time_ms": elapsed,
        })

        status = "🟢" if result.direction.value == "BULL" else "🔴" if result.direction.value == "BEAR" else "⚪"
        print(f"\n{status} {symbol}: {result.direction.value} {mkt_info}")
        print(f"   ADX={result.adx:.1f}, Score={result.final_score:.1f}, "
              f"Strength={result.strength.value}, Time={elapsed:.1f}ms")

    # Summary
    if results:
        avg_time = sum(r["time_ms"] for r in results) / len(results)
        print(f"\n{'─' * 60}")
        print(f"Average time: {avg_time:.2f}ms")

        bull_count = sum(1 for r in results if r["direction"] == "BULL")
        bear_count = sum(1 for r in results if r["direction"] == "BEAR")
        print(f"Summary: {bull_count} BULL, {bear_count} BEAR, {len(results) - bull_count - bear_count} NEUTRAL")


def main():
    """Run all tests."""
    print("\n🚀 MTES V4 Test Suite")
    print("=" * 60)

    run_performance_test()
    run_direction_test()
    run_comparison_test()
    run_batch_test()

    print("\n" + "=" * 60)
    print("✅ All tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
