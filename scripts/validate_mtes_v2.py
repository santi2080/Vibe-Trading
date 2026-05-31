#!/usr/bin/env python3
"""MTES v2 评分体系验证脚本

按 SPEC.md 验收标准验证新的"方向为主、强度辅助"评分体系。
"""

import sys
import pandas as pd
import numpy as np

sys.path.insert(0, "agent/src")
from analysis.major_trend_evaluator import (
    MajorTrendEvaluator,
    MajorTrendConfig,
    DIRECTION_WEIGHTS,
    STRENGTH_COMPONENTS,
)


def make_test_data(trend: str, length: int = 300, seed: int = 42) -> pd.DataFrame:
    """生成测试数据"""
    np.random.seed(seed)
    dates = pd.date_range("2023-01-01", periods=length, freq="D")

    if trend == "strong_bull":
        # 稳定上涨趋势
        close = 100 * np.exp(np.linspace(0, 0.6, length))
    elif trend == "weak_bull":
        # 缓慢上涨
        close = 100 * np.exp(np.linspace(0, 0.15, length))
    elif trend == "strong_bear":
        # 稳定下跌
        close = 100 * np.exp(np.linspace(0, -0.6, length))
    elif trend == "weak_bear":
        # 缓慢下跌
        close = 100 * np.exp(np.linspace(0, -0.15, length))
    elif trend == "choppy":
        # 震荡
        close = 100 + 10 * np.sin(np.linspace(0, 8, length))
    else:
        raise ValueError(f"Unknown trend: {trend}")

    # 添加一些随机波动
    noise = np.random.randn(length) * 0.3
    close = close * (1 + noise * 0.008)

    return pd.DataFrame({
        "datetime": dates,
        "open": close * 0.995,
        "high": close * 1.015,
        "low": close * 0.985,
        "close": close,
        "volume": 1e6,
    })


def test_score_range():
    """验证评分范围"""
    print("\n🧪 验证 1: 评分范围检查")

    evaluator = MajorTrendEvaluator()
    test_cases = [
        ("strong_bull", "stock"),
        ("weak_bull", "stock"),
        ("choppy", "stock"),
        ("weak_bear", "stock"),
        ("strong_bear", "stock"),
    ]

    all_pass = True
    for trend, asset_class in test_cases:
        df = make_test_data(trend)
        result = evaluator.evaluate(df, asset_class=asset_class)

        score_ok = -100 <= result.trend_score <= 100
        conf_ok = 0 <= result.confidence <= 1

        status = "✅" if (score_ok and conf_ok) else "❌"
        print(f"  {status} {trend}: score={result.trend_score:+.1f}, conf={result.confidence:.2f}")

        if not (score_ok and conf_ok):
            all_pass = False

    return all_pass


def test_direction_independence():
    """验证方向独立性"""
    print("\n🧪 验证 2: 方向独立性")

    evaluator = MajorTrendEvaluator()

    # 强上涨应该是 BULL
    bull_result = evaluator.evaluate(make_test_data("strong_bull"), asset_class="stock")
    # 强下跌应该是 BEAR
    bear_result = evaluator.evaluate(make_test_data("strong_bear"), asset_class="stock")

    bull_ok = bull_result.direction == "BULL" and bull_result.trend_score > 0
    bear_ok = bear_result.direction == "BEAR" and bear_result.trend_score < 0

    print(f"  {'✅' if bull_ok else '❌'} BULL: direction={bull_result.direction}, score={bull_result.trend_score:+.1f}")
    print(f"  {'✅' if bear_ok else '❌'} BEAR: direction={bear_result.direction}, score={bear_result.trend_score:+.1f}")

    return bull_ok and bear_ok


def test_trend_state_classification():
    """验证趋势状态分类"""
    print("\n🧪 验证 3: 趋势状态分类")

    evaluator = MajorTrendEvaluator()

    test_cases = [
        ("strong_bull", "BULL", ["BULL_STRONG", "BULL_CONFIRMED"]),
        ("weak_bull", "BULL", ["BULL_CONFIRMED", "BULL_EARLY"]),
        ("strong_bear", "BEAR", ["BEAR_STRONG", "BEAR_CONFIRMED"]),
    ]

    all_pass = True
    for trend, expected_dir, expected_states in test_cases:
        result = evaluator.evaluate(make_test_data(trend), asset_class="stock")

        state_ok = result.trend_state in expected_states
        dir_ok = result.direction == expected_dir

        status = "✅" if (state_ok and dir_ok) else "❌"
        print(f"  {status} {trend}: state={result.trend_state}, dir={result.direction}")

        if not (state_ok and dir_ok):
            all_pass = False

    return all_pass


def test_v2_fields():
    """验证 V2 新增字段"""
    print("\n🧪 验证 4: V2 新增字段")

    evaluator = MajorTrendEvaluator()
    result = evaluator.evaluate(make_test_data("strong_bull"), asset_class="stock")

    checks = [
        ("direction_signal", -100 <= result.direction_signal <= 100),
        ("direction_confidence", 0 <= result.direction_confidence <= 1),
        ("strength_score", 0 <= result.strength_score <= 100),
        ("strength_components", isinstance(result.strength_components, dict)),
        ("use_v2_scoring", result.use_v2_scoring == True),
    ]

    all_pass = True
    for field, ok in checks:
        print(f"  {'✅' if ok else '❌'} {field}: {getattr(result, field)}")
        if not ok:
            all_pass = False

    return all_pass


def test_v1_backward_compat():
    """验证 V1 向后兼容"""
    print("\n🧪 验证 5: V1 向后兼容")

    evaluator_v1 = MajorTrendEvaluator(config=MajorTrendConfig(use_v2_scoring=False))
    evaluator_v2 = MajorTrendEvaluator()

    df = make_test_data("strong_bull")
    v1_result = evaluator_v1.evaluate(df, asset_class="stock")
    v2_result = evaluator_v2.evaluate(df, asset_class="stock")

    # V1: score >= 50 表示 BULL
    v1_bull = v1_result.trend_score >= 50
    # V2: direction = BULL 且 score > 0
    v2_bull = v2_result.direction == "BULL" and v2_result.trend_score > 0

    print(f"  V1: score={v1_result.trend_score:.1f} (>=50 = BULL)")
    print(f"  V2: direction={v2_result.direction}, score={v2_result.trend_score:+.1f}")
    print(f"  ✅ V1 和 V2 方向一致: {v1_bull == v2_bull}")

    return v1_bull == v2_bull


def test_asset_weights():
    """验证资产类别权重配置"""
    print("\n🧪 验证 6: 资产类别权重配置")

    expected_weights = {
        "stock": 0.65,
        "etf": 0.60,
        "futures": 0.70,
        "crypto": 0.55,
        "fx": 0.75,
    }

    all_pass = True
    for asset_class, expected_weight in expected_weights.items():
        actual_weight = DIRECTION_WEIGHTS[asset_class]
        ok = abs(actual_weight - expected_weight) < 0.01
        print(f"  {'✅' if ok else '❌'} {asset_class}: {actual_weight:.2f}")
        if not ok:
            all_pass = False

    return all_pass


def test_strength_components():
    """验证强度组权重"""
    print("\n🧪 验证 7: 强度组权重")

    for asset_class, components in STRENGTH_COMPONENTS.items():
        total = sum(components.values())
        ok = abs(total - 1.0) < 0.01
        print(f"  {'✅' if ok else '❌'} {asset_class}: sum={total:.2f}")
        if not ok:
            return False

    return True


def main():
    print("=" * 60)
    print("MTES v2 评分体系验证")
    print("=" * 60)

    results = []
    results.append(("评分范围", test_score_range()))
    results.append(("方向独立性", test_direction_independence()))
    results.append(("趋势状态分类", test_trend_state_classification()))
    results.append(("V2 新增字段", test_v2_fields()))
    results.append(("V1 向后兼容", test_v1_backward_compat()))
    results.append(("资产类别权重", test_asset_weights()))
    results.append(("强度组权重", test_strength_components()))

    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有验证通过！MTES v2 评分体系符合规格要求。")
        return 0
    else:
        print("\n⚠️ 部分验证失败，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
