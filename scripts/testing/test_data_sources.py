#!/usr/bin/env python3
"""测试 vibe-trading 数据源是否正常工作"""

import sys
import os
import time
from datetime import datetime

# 设置路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from agent.backtest.loaders.registry import resolve_loader, FALLBACK_CHAINS, LOADER_REGISTRY, _ensure_registered


def test_registry():
    """测试数据源注册情况"""
    print("\n" + "=" * 60)
    print("Test 1: 数据源注册状态")
    print("=" * 60)

    _ensure_registered()

    print("\n  已注册的数据源:")
    for name, cls in LOADER_REGISTRY.items():
        try:
            instance = cls()
            available = instance.is_available()
            status = "✅ 可用" if available else "❌ 不可用"
            print(f"    {status} {name}")
        except Exception as e:
            print(f"    ❌ 初始化失败 {name}: {str(e)[:50]}")

    print(f"\n  总计: {len(LOADER_REGISTRY)} 个数据源")

    return len(LOADER_REGISTRY) > 0


def test_fallback_chains():
    """测试回退链配置"""
    print("\n" + "=" * 60)
    print("Test 2: 回退链配置")
    print("=" * 60)

    print("\n  市场 -> 数据源回退链:")
    for market, chain in FALLBACK_CHAINS.items():
        print(f"    {market}: {' -> '.join(chain)}")


def test_fetch(market, symbol, description):
    """测试单个数据获取"""
    print(f"\n  测试 {symbol} ({description}) - {market}")

    try:
        start = time.time()
        loader = resolve_loader(market)
        elapsed = time.time() - start

        data = loader.fetch(
            codes=[symbol],
            start_date="2024-01-01",
            end_date="2024-01-10",
            interval="1d",
        )

        if symbol in data and not data[symbol].empty:
            df = data[symbol]
            print(f"    ✅ 成功: {len(df)} 行, 耗时 {elapsed:.2f}s")
            print(f"       数据范围: {df.index[0]} ~ {df.index[-1]}")
            return True, f"{len(df)} rows"
        else:
            print(f"    ⚠️  返回空数据")
            return False, "empty"

    except Exception as e:
        error_msg = str(e)[:80]
        print(f"    ❌ 失败: {error_msg}")
        return False, error_msg


def test_all_markets():
    """测试所有市场数据获取"""
    print("\n" + "=" * 60)
    print("Test 3: 各市场数据获取测试")
    print("=" * 60)

    # 测试用例: (市场, 符号, 描述)
    test_cases = [
        # 美国市场 - yfinance
        ("us_futures", "GC=F", "黄金期货"),
        ("us_futures", "CL=F", "原油期货"),
        ("us_equity", "AAPL", "苹果股票"),

        # 中国市场
        ("a_share", "600036", "招商银行"),
        ("a_share", "000001", "平安银行"),

        # 期货
        ("futures", "IF2406", "沪深300期货"),
    ]

    results = []
    for market, symbol, description in test_cases:
        success, msg = test_fetch(market, symbol, description)
        results.append((symbol, description, market, success, msg))

    return results


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 Vibe-Trading 数据源测试")
    print("=" * 60)
    print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test 1: 注册状态
    test_registry()

    # Test 2: 回退链
    test_fallback_chains()

    # Test 3: 数据获取
    results = test_all_markets()

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    success_count = sum(1 for _, _, _, success, _ in results if success)

    print("\n  各数据源测试:")
    for symbol, description, market, success, msg in results:
        status = "✅" if success else "❌"
        print(f"    {status} {symbol} {description} ({market}): {msg}")

    print(f"\n  成功率: {success_count}/{len(results)} ({100*success_count/len(results):.0f}%)")

    print("\n" + "=" * 60)
    if success_count >= len(results) * 0.5:
        print("✅ 数据源基本可用")
        return 0
    else:
        print("❌ 多个数据源无法工作")
        return 1


if __name__ == "__main__":
    sys.exit(main())
