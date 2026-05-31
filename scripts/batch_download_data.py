#!/usr/bin/env python3
"""
批量数据下载脚本

使用 HybridDataFetcher 下载美国期货和 ETF 的历史数据到 Parquet 格式

用法:
    python scripts/batch_download_data.py
    python scripts/batch_download_data.py --symbols GC=F SI=F --start 2020-01-01
    python scripts/batch_download_data.py --test  # 测试模式，只下载 1 个品种
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from backtest.loaders.hybrid_fetcher import HybridDataFetcher


# 品种配置
SYMBOLS_CONFIG = {
    # 美国期货
    "GC=F": "us_futures",
    "SI=F": "us_futures",
    "CL=F": "us_futures",
    "NG=F": "us_futures",
    "ES=F": "us_futures",
    "NQ=F": "us_futures",
    "YM=F": "us_futures",
    "HG=F": "us_futures",
    "ZC=F": "us_futures",
    "ZS=F": "us_futures",
    # ETF
    "IAU": "etf",
    "SLV": "etf",
    "GLD": "etf",
    "TLT": "etf",
    "IEF": "etf",
    "SHY": "etf",
    "SPY": "etf",
    "QQQ": "etf",
    "IWM": "etf",
    "EEM": "etf",
    "USO": "etf",
    "DBC": "etf",
}


def resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """从日线重采样到周线"""
    if df is None or df.empty:
        return df

    # 确保是日期索引
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        return df

    # 周线重采样 (每周最后一个交易日)
    weekly = df.resample('W').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })

    # 删除空值行
    weekly = weekly.dropna()

    return weekly


def save_to_parquet(df: pd.DataFrame, market: str, symbol: str, timeframe: str = "1d") -> Path | None:
    """保存数据到 Parquet"""
    if df is None or df.empty:
        return None

    # 确保必要的列
    required_cols = ["open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            print(f"  ⚠️ {symbol} 缺少列: {col}")
            return None

    # 创建目录
    output_dir = PROJECT_ROOT / "data" / market / symbol
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{timeframe}.parquet"

    # 保存
    df.to_parquet(output_path, index=True)
    return output_path


def download_single_symbol(
    symbol: str,
    start_date: str,
    end_date: str,
    fetcher: HybridDataFetcher,
    include_weekly: bool = False
) -> tuple[str, bool, str]:
    """下载单个品种

    Returns:
        (symbol, success, message)
    """
    market = SYMBOLS_CONFIG.get(symbol, "stock")

    print(f"  📥 {symbol} ({market})...")

    try:
        # 下载日线数据
        result = fetcher.fetch([symbol], start_date, end_date)

        if result is None or result.empty:
            print(f"  ❌ {symbol}: 无数据")
            return symbol, False, "无数据"

        # 保存日线
        daily_path = save_to_parquet(result, market, symbol, "1d")
        daily_count = len(result)

        weekly_path = None
        weekly_count = 0
        if include_weekly:
            weekly = resample_to_weekly(result)
            weekly_path = save_to_parquet(weekly, market, symbol, "1W")
            weekly_count = len(weekly)

        msg = f"日线:{daily_count}"
        if include_weekly and weekly_count > 0:
            msg += f" 周线:{weekly_count}"

        print(f"  ✅ {symbol}: {msg}")
        return symbol, True, msg

    except Exception as e:
        print(f"  ❌ {symbol} 错误: {e}")
        return symbol, False, str(e)


def check_existing_data(symbol: str, market: str) -> dict | None:
    """检查现有数据"""
    daily_path = PROJECT_ROOT / "data" / market / symbol / "1d.parquet"
    weekly_path = PROJECT_ROOT / "data" / market / symbol / "1W.parquet"

    info = {}
    if daily_path.exists():
        df = pd.read_parquet(daily_path)
        info["daily"] = {
            "path": str(daily_path),
            "count": len(df),
            "start": str(df.index[0].date()) if len(df) > 0 else None,
            "end": str(df.index[-1].date()) if len(df) > 0 else None,
        }
    if weekly_path.exists():
        df = pd.read_parquet(weekly_path)
        info["weekly"] = {
            "path": str(weekly_path),
            "count": len(df),
            "start": str(df.index[0].date()) if len(df) > 0 else None,
            "end": str(df.index[-1].date()) if len(df) > 0 else None,
        }

    return info if info else None


def main():
    parser = argparse.ArgumentParser(description="批量下载历史数据")
    parser.add_argument("--symbols", nargs="+", help="品种列表")
    parser.add_argument("--start", default="2020-01-01", help="开始日期")
    parser.add_argument("--end", default="2025-12-31", help="结束日期")
    parser.add_argument("--test", action="store_true", help="测试模式，只下载 1 个")
    parser.add_argument("--weekly", action="store_true", help="同时下载周线")
    parser.add_argument("--check", action="store_true", help="只检查现有数据")
    parser.add_argument("--rate-limit", type=float, default=2.0, help="请求间隔(秒)")
    args = parser.parse_args()

    # 确定要处理的品种
    if args.symbols:
        symbols = args.symbols
    else:
        symbols = list(SYMBOLS_CONFIG.keys())

    if args.test:
        symbols = symbols[:1]

    print("=" * 60)
    print(f"批量数据下载".center(50))
    print("=" * 60)
    print(f"时间范围: {args.start} ~ {args.end}")
    print(f"品种数量: {len(symbols)}")
    print(f"包含周线: {'是' if args.weekly else '否'}")
    print("=" * 60)

    # 初始化 fetcher
    fetcher = HybridDataFetcher()

    results = []

    if args.check:
        # 只检查现有数据
        print("\n📊 现有数据检查:")
        print("-" * 60)
        for symbol in symbols:
            market = SYMBOLS_CONFIG.get(symbol, "stock")
            info = check_existing_data(symbol, market)
            if info:
                daily = info.get("daily", {})
                weekly = info.get("weekly", {})
                daily_info = f"日线:{daily.get('count', 0)}条 ({daily.get('start', '?')}~{daily.get('end', '?')})"
                weekly_info = f" 周线:{weekly.get('count', 0)}条" if weekly else ""
                print(f"  ✅ {symbol}: {daily_info}{weekly_info}")
            else:
                print(f"  ❌ {symbol}: 无数据")
            results.append((symbol, info is not None, info))
    else:
        # 下载数据
        print("\n📥 开始下载:")
        print("-" * 60)
        for i, symbol in enumerate(symbols, 1):
            success, _, msg = download_single_symbol(
                symbol, args.start, args.end, fetcher, args.weekly
            )
            results.append((symbol, success, msg))

            # 限速
            if i < len(symbols) and args.rate_limit > 0:
                time.sleep(args.rate_limit)

    # 汇总
    print("\n" + "=" * 60)
    print("结果汇总")
    print("=" * 60)

    success_count = sum(1 for _, s, _ in results if s)
    print(f"成功: {success_count}/{len(results)}")

    if not args.check:
        for symbol, success, msg in results:
            status = "✅" if success else "❌"
            print(f"  {status} {symbol}: {msg}")

    return 0 if success_count == len(symbols) else 1


if __name__ == "__main__":
    sys.exit(main())
