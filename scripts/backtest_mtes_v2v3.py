#!/usr/bin/env python3
"""
MTES v2 vs v3 回测验证

使用历史数据验证哪个版本的信号更准确。
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Literal
import sys

# MTES v2
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent.src.analysis.major_trend_evaluator import MajorTrendEvaluator, MajorTrendConfig

# MTES v3
from agent.src.analysis.mtes_v3 import MTESv3, MTESv3Config


@dataclass
class SignalResult:
    """单次信号结果"""
    date: pd.Timestamp
    symbol: str
    direction: Literal["BULL", "BEAR", "NEUTRAL"]
    score: float
    confidence: float
    next_1d_return: float
    next_5d_return: float
    next_20d_return: float


@dataclass
class BacktestResult:
    """回测结果"""
    version: Literal["v2", "v3"]
    total_signals: int
    bullish_signals: int
    bearish_signals: int
    avg_return_1d: float
    avg_return_5d: float
    avg_return_20d: float
    win_rate_1d: float
    win_rate_5d: float
    win_rate_20d: float
    sharpe_1d: float
    sharpe_5d: float
    sharpe_20d: float


def load_data(symbol: str, timeframe: str = "1d") -> pd.DataFrame:
    """加载市场数据"""
    data_dir = Path("data/us_futures")
    parquet_path = data_dir / symbol / f"{timeframe}.parquet"

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        df.columns = df.columns.str.lower()
        return df
    return None


def analyze_v2(df: pd.DataFrame) -> dict:
    """MTES v2 分析"""
    config = MajorTrendConfig(asset_class="futures", use_v2_scoring=True)
    evaluator = MajorTrendEvaluator(config)
    result = evaluator.evaluate(df)
    return {
        "direction": result.direction,
        "score": result.trend_score,
        "confidence": result.confidence
    }


def analyze_v3(df: pd.DataFrame) -> dict:
    """MTES v3 分析"""
    try:
        config = MTESv3Config()
        mtes = MTESv3(config)
        result = mtes.analyze(df)
        return {
            "direction": result.mtf_trend.direction,
            "score": result.final_score,
            "confidence": result.final_confidence
        }
    except Exception as e:
        # 回测中某些边界情况会失败，返回 NEUTRAL
        return {
            "direction": "NEUTRAL",
            "score": 0.0,
            "confidence": 0.0
        }


def calculate_returns(df: pd.DataFrame, lookbacks: list[int] = [1, 5, 20]) -> pd.DataFrame:
    """计算未来收益率"""
    result = df.copy()

    for lb in lookbacks:
        # 未来收益率（信号发出后 lb 天的收益）
        result[f"future_return_{lb}d"] = result['close'].shift(-lb) / result['close'] - 1

    return result


def run_backtest(symbol: str, df: pd.DataFrame, version: str) -> list[SignalResult]:
    """对单个品种运行回测"""
    # 计算收益率
    df = calculate_returns(df)

    results = []
    min_bars = 200  # 最小历史数据（v2 需要更多数据）

    for i in range(min_bars, len(df) - 20):
        # 提取历史数据
        historical = df.iloc[:i+1].copy()

        # 获取信号
        if version == "v2":
            signal = analyze_v2(historical)
        else:
            signal = analyze_v3(historical)

        # 跳过 NEUTRAL 或低置信度信号
        if signal["direction"] == "NEUTRAL":
            continue
        if signal["confidence"] < 0.5:
            continue

        # 获取未来收益
        future_1d = df[f"future_return_1d"].iloc[i] if pd.notna(df[f"future_return_1d"].iloc[i]) else 0
        future_5d = df[f"future_return_5d"].iloc[i] if pd.notna(df[f"future_return_5d"].iloc[i]) else 0
        future_20d = df[f"future_return_20d"].iloc[i] if pd.notna(df[f"future_return_20d"].iloc[i]) else 0

        results.append(SignalResult(
            date=df.index[i],
            symbol=symbol,
            direction=signal["direction"],
            score=signal["score"],
            confidence=signal["confidence"],
            next_1d_return=future_1d,
            next_5d_return=future_5d,
            next_20d_return=future_20d
        ))

    return results


def analyze_results(results: list[SignalResult], version: str) -> BacktestResult:
    """分析回测结果"""
    if not results:
        return BacktestResult(
            version=version,
            total_signals=0, bullish_signals=0, bearish_signals=0,
            avg_return_1d=0, avg_return_5d=0, avg_return_20d=0,
            win_rate_1d=0, win_rate_5d=0, win_rate_20d=0,
            sharpe_1d=0, sharpe_5d=0, sharpe_20d=0
        )

    bullish = [r for r in results if r.direction == "BULL"]
    bearish = [r for r in results if r.direction == "BEAR"]

    returns_1d = [r.next_1d_return for r in results]
    returns_5d = [r.next_5d_return for r in results]
    returns_20d = [r.next_20d_return for r in results]

    # 胜率计算（对于 BULL 信号，正收益为胜；对于 BEAR，负收益为胜）
    wins_1d = sum(1 for r in results if (r.direction == "BULL" and r.next_1d_return > 0) or (r.direction == "BEAR" and r.next_1d_return < 0))
    wins_5d = sum(1 for r in results if (r.direction == "BULL" and r.next_5d_return > 0) or (r.direction == "BEAR" and r.next_5d_return < 0))
    wins_20d = sum(1 for r in results if (r.direction == "BULL" and r.next_20d_return > 0) or (r.direction == "BEAR" and r.next_20d_return < 0))

    # 夏普比率
    def sharpe(returns: list[float], rf: float = 0.0) -> float:
        if len(returns) < 2:
            return 0
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)
        if std_ret == 0:
            return 0
        return (mean_ret - rf) / std_ret * np.sqrt(252)

    return BacktestResult(
        version=version,
        total_signals=len(results),
        bullish_signals=len(bullish),
        bearish_signals=len(bearish),
        avg_return_1d=np.mean(returns_1d) * 100,
        avg_return_5d=np.mean(returns_5d) * 100,
        avg_return_20d=np.mean(returns_20d) * 100,
        win_rate_1d=wins_1d / len(results) * 100,
        win_rate_5d=wins_5d / len(results) * 100,
        win_rate_20d=wins_20d / len(results) * 100,
        sharpe_1d=sharpe(returns_1d),
        sharpe_5d=sharpe(returns_5d),
        sharpe_20d=sharpe(returns_20d)
    )


def print_comparison(v2_result: BacktestResult, v3_result: BacktestResult):
    """打印对比结果"""
    print("\n" + "=" * 80)
    print("MTES v2 vs v3 回测对比结果")
    print("=" * 80)

    print(f"\n{'指标':<20} {'v2':>15} {'v3':>15} {'差异':>15}")
    print("-" * 65)

    metrics = [
        ("信号总数", v2_result.total_signals, v3_result.total_signals),
        ("多头信号", v2_result.bullish_signals, v3_result.bullish_signals),
        ("空头信号", v2_result.bearish_signals, v3_result.bearish_signals),
        ("", None, None, None),
        ("1日平均收益(%)", v2_result.avg_return_1d, v3_result.avg_return_1d),
        ("5日平均收益(%)", v2_result.avg_return_5d, v3_result.avg_return_5d),
        ("20日平均收益(%)", v2_result.avg_return_20d, v3_result.avg_return_20d),
        ("", None, None, None),
        ("1日胜率(%)", v2_result.win_rate_1d, v3_result.win_rate_1d),
        ("5日胜率(%)", v2_result.win_rate_5d, v3_result.win_rate_5d),
        ("20日胜率(%)", v2_result.win_rate_20d, v3_result.win_rate_20d),
        ("", None, None, None),
        ("1日夏普比率", v2_result.sharpe_1d, v3_result.sharpe_1d),
        ("5日夏普比率", v2_result.sharpe_5d, v3_result.sharpe_5d),
        ("20日夏普比率", v2_result.sharpe_20d, v3_result.sharpe_20d),
    ]

    for item in metrics:
        name, v2_val, v3_val = item[0], item[1], item[2]
        if name == "":
            print()
            continue

        if v2_val is not None and v3_val is not None:
            if isinstance(v2_val, int):
                diff = v3_val - v2_val
                print(f"{name:<20} {v2_val:>15} {v3_val:>15} {diff:>+15}")
            else:
                diff = v3_val - v2_val
                print(f"{name:<20} {v2_val:>15.2f} {v3_val:>15.2f} {diff:>+15.2f}")

    # 总结
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)

    v2_score = v2_result.sharpe_20d + v2_result.win_rate_20d / 10
    v3_score = v3_result.sharpe_20d + v3_result.win_rate_20d / 10

    if v2_score > v3_score:
        winner = "MTES v2"
        diff_pct = (v2_score - v3_score) / v3_score * 100 if v3_score != 0 else float('inf')
    elif v3_score > v2_score:
        winner = "MTES v3"
        diff_pct = (v3_score - v2_score) / v2_score * 100 if v2_score != 0 else float('inf')
    else:
        winner = "平局"
        diff_pct = 0

    print(f"\n🏆 综合胜者: {winner}")
    print(f"📊 领先幅度: {diff_pct:.1f}%")

    if winner == "MTES v3":
        print(f"\n✅ v3 更准确的原因:")
        if v3_result.win_rate_20d > v2_result.win_rate_20d:
            print(f"   - 20日胜率更高: {v3_result.win_rate_20d:.1f}% vs {v2_result.win_rate_20d:.1f}%")
        if v3_result.sharpe_20d > v2_result.sharpe_20d:
            print(f"   - 20日夏普比率更高: {v3_result.sharpe_20d:.2f} vs {v2_result.sharpe_20d:.2f}")
    elif winner == "MTES v2":
        print(f"\n✅ v2 更准确的原因:")
        if v2_result.win_rate_20d > v3_result.win_rate_20d:
            print(f"   - 20日胜率更高: {v2_result.win_rate_20d:.1f}% vs {v3_result.win_rate_20d:.1f}%")
        if v2_result.sharpe_20d > v3_result.sharpe_20d:
            print(f"   - 20日夏普比率更高: {v2_result.sharpe_20d:.2f} vs {v3_result.sharpe_20d:.2f}")


def main():
    print("=" * 80)
    print("MTES v2 vs v3 历史回测验证")
    print("=" * 80)

    # 测试品种
    symbols = ["ES=F", "NQ=F", "GC=F", "SI=F", "CL=F"]

    all_v2_results = []
    all_v3_results = []

    for symbol in symbols:
        print(f"\n📊 加载数据: {symbol}")

        df = load_data(symbol)
        if df is None:
            print(f"  ⚠️  数据不存在，跳过")
            continue

        print(f"  数据点数: {len(df)}, 日期范围: {df.index[0].date()} ~ {df.index[-1].date()}")

        # v2 回测
        print(f"  运行 v2 回测...")
        v2_signals = run_backtest(symbol, df, "v2")
        all_v2_results.extend(v2_signals)
        print(f"    生成信号: {len(v2_signals)} 个")

        # v3 回测
        print(f"  运行 v3 回测...")
        v3_signals = run_backtest(symbol, df, "v3")
        all_v3_results.extend(v3_signals)
        print(f"    生成信号: {len(v3_signals)} 个")

    # 分析结果
    print(f"\n{'='*60}")
    print(f"汇总统计")
    print(f"{'='*60}")

    v2_summary = analyze_results(all_v2_results, "v2")
    v3_summary = analyze_results(all_v3_results, "v3")

    print(f"\nv2 总信号: {v2_summary.total_signals}")
    print(f"v3 总信号: {v3_summary.total_signals}")

    # 打印对比
    print_comparison(v2_summary, v3_summary)

    # 保存详细结果
    output_dir = Path("reports/backtest")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存为 CSV
    v2_df = pd.DataFrame([{
        "date": r.date, "symbol": r.symbol, "direction": r.direction,
        "score": r.score, "confidence": r.confidence,
        "next_1d": r.next_1d_return, "next_5d": r.next_5d_return, "next_20d": r.next_20d_return
    } for r in all_v2_results])
    v2_df.to_csv(output_dir / "v2_signals.csv", index=False)

    v3_df = pd.DataFrame([{
        "date": r.date, "symbol": r.symbol, "direction": r.direction,
        "score": r.score, "confidence": r.confidence,
        "next_1d": r.next_1d_return, "next_5d": r.next_5d_return, "next_20d": r.next_20d_return
    } for r in all_v3_results])
    v3_df.to_csv(output_dir / "v3_signals.csv", index=False)

    print(f"\n详细结果已保存到: {output_dir}/")


if __name__ == "__main__":
    main()
