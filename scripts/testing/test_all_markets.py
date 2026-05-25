#!/usr/bin/env python3
"""测试各市场各周期数据下载"""

import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from agent.backtest.loaders.registry import resolve_loader


def test_market(symbols, market, interval, name, date_range="1M"):
    """测试单个市场周期"""
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"📊 {name} ({interval})")
    print(f"   品种: {symbols}")
    print(f"   市场: {market}")
    print(f"   周期: {interval}")
    print(f"{'='*60}")

    # 获取 loader
    loader = resolve_loader(market)
    results = {}
    success = 0
    failed = 0

    for symbol in symbols:
        start = time.time()
        try:
            data = loader.fetch(
                codes=[symbol],
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )
            elapsed = time.time() - start

            if symbol in data and not data[symbol].empty:
                rows = len(data[symbol])
                print(f"  ✅ {symbol}: {rows} 条, {elapsed:.2f}s")
                results[symbol] = {"status": "success", "rows": rows, "time": elapsed}
                success += 1
            else:
                print(f"  ❌ {symbol}: 空数据")
                results[symbol] = {"status": "empty", "rows": 0, "time": elapsed}
                failed += 1

        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌ {symbol}: {str(e)[:50]}")
            results[symbol] = {"status": "error", "error": str(e)[:100], "time": elapsed}
            failed += 1

    return results, success, failed


def main():
    print("🧪 Vibe-Trading 数据源测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = {}
    total_success = 0
    total_failed = 0

    # ===== US Futures =====
    us_futures_symbols = ["GC=F", "SI=F", "HG=F", "CL=F", "ES=F", "NQ=F"]

    # 日线测试 (akshare - 不需要代理)
    results, s, f = test_market(us_futures_symbols, "us_futures", "1D", "US Futures 日线", "1M")
    all_results["us_futures_1d"] = results
    total_success += s
    total_failed += f

    # 4小时测试 (暂时跳过，因为 akshare 不支持日内数据)
    # 如果需要日内数据，需要使用 yfinance (需要代理)
    # results, s, f = test_market(us_futures_symbols, "us_futures_intraday", "4H", "US Futures 4H", "1W")
    print("\n⚠️ US Futures 4H 测试已跳过（akshare 不支持日内，需要 yfinance + 代理）")
    all_results["us_futures_4h"] = results
    total_success += s
    total_failed += f

    # ===== CN Futures =====
    cn_futures_symbols = ["al0", "rb0", "ru0", "ta0"]

    # 日线测试 (akshare - 不需要代理)
    results, s, f = test_market(cn_futures_symbols, "cn_futures", "1D", "CN Futures 日线", "1M")
    all_results["cn_futures_1d"] = results
    total_success += s
    total_failed += f

    # 1小时测试
    results, s, f = test_market(cn_futures_symbols, "cn_futures", "1H", "CN Futures 1H", "3D")
    all_results["cn_futures_1h"] = results
    total_success += s
    total_failed += f

    # ===== US Stock/ETF =====
    us_stock_symbols = ["VOO", "VEA", "QQQ", "SPY", "IWM", "EEM"]

    # 日线测试 (yfinance - 需要代理，暂时跳过)
    # results, s, f = test_market(us_stock_symbols, "us_equity", "1D", "US Stock 日线", "1M")
    print("\n⚠️ US Stock 测试已跳过（需要代理）")
    all_results["us_stock_1d"] = results
    total_success += s
    total_failed += f

    # 周线测试
    # results, s, f = test_market(us_stock_symbols, "us_equity", "1W", "US Stock 周线", "3M")
    # all_results["us_stock_1w"] = results
    # total_success += s
    # total_failed += f
    print("⚠️ US Stock 周线测试已跳过（需要代理）")

    # ===== 总结 =====
    print("\n" + "="*60)
    print("📋 测试总结")
    print("="*60)
    print(f"✅ 成功: {total_success}")
    print(f"❌ 失败: {total_failed}")
    print(f"📈 成功率: {total_success/(total_success+total_failed)*100:.1f}%")
    print("="*60)

    # 按市场分组
    print("\n📊 按市场分组:")
    for key, results in all_results.items():
        s = sum(1 for r in results.values() if r["status"] == "success")
        f = sum(1 for r in results.values() if r["status"] != "success")
        status = "✅" if f == 0 else "⚠️" if f < s else "❌"
        print(f"  {status} {key}: {s}/{s+f} 成功")

    return all_results


if __name__ == "__main__":
    main()
