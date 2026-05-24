#!/usr/bin/env python3
"""
Watchlist 数据下载测试脚本
验证数据层能否正常下载并保存数据

用法:
    python scripts/test_watchlist_download.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import csv
from typing import Dict, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from backtest.loaders.akshare_loader import DataLoader as AKShareLoader


def load_watchlist(watchlist_path: str = "watchlist/my_watchlist.csv") -> List[Dict]:
    """加载 watchlist 配置"""
    items = []
    with open(watchlist_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue

            # 解析 CSV 行
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                items.append({
                    'symbol': parts[0],
                    'name': parts[1],
                    'market': parts[2],
                    'timeframes': parts[3] if len(parts) > 3 else '1D-1H',
                    'sector': parts[4] if len(parts) > 4 else '',
                })
    return items


def get_market_type(market: str) -> str:
    """将市场名称映射到 loader 的 market 类型"""
    market_map = {
        'us_futures': 'futures',
        'cn_futures': 'futures',
        'cn_stocks': 'a_share',
        'us_stocks': 'us_equity',
        'hk_stocks': 'hk_equity',
    }
    return market_map.get(market, 'a_share')


def download_symbol(symbol: str, market: str, start_date: str, end_date: str, data_dir: str = "data") -> pd.DataFrame:
    """下载单个品种数据

    优先从 trading-assistant 数据目录读取，失败时尝试 AKShare API
    """
    print(f"\n📥 获取: {symbol} ({market})")

    # 方案 1: 从 trading-assistant 数据目录读取
    ta_data_dir = Path("/Users/iagent/projects/trading-assistant/data/features")

    # 映射市场目录
    market_dir_map = {
        'us_futures': 'us_futures',
        'cn_stocks': 'cn_stocks',
        'us_stocks': 'us_stocks',
    }
    market_dir = market_dir_map.get(market, 'us_futures')

    ta_path = ta_data_dir / market_dir / symbol / "1d.parquet"

    if ta_path.exists():
        try:
            df = pd.read_parquet(ta_path)
            # 按日期过滤
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            print(f"   ✅ 从 trading-assistant 读取: {len(df)} 条数据")
            return df
        except Exception as e:
            print(f"   ⚠️ 读取 trading-assistant 数据失败: {e}")

    # 方案 2: 尝试 AKShare API（如果有网络）
    print(f"   🔄 尝试 AKShare API...")

    try:
        loader = AKShareLoader()
        result = loader.fetch([symbol], start_date, end_date, interval="1D")

        if symbol in result and not result[symbol].empty:
            df = result[symbol]
            print(f"   ✅ AKShare 成功: {len(df)} 条数据")
            return df
        else:
            print(f"   ❌ AKShare 无数据")
            return None

    except Exception as e:
        print(f"   ❌ AKShare 错误: {e}")
        return None


def save_data(df: pd.DataFrame, symbol: str, market: str, data_dir: str = "data") -> Path:
    """保存数据到本地"""
    # 构建路径: data/{market}/{symbol}/1d.parquet
    market_dir = market.replace('_', '/')  # cn_stocks -> cn/stocks (不对)
    # 实际应该: us_futures -> us_futures
    market_dir = market

    save_dir = Path(data_dir) / market_dir / symbol
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / "1d.parquet"

    # 保存为 parquet
    df.to_parquet(save_path, compression='snappy')
    print(f"   💾 保存: {save_path}")

    return save_path


def main():
    print("=" * 60)
    print("Watchlist 数据下载测试")
    print("=" * 60)

    # 配置
    watchlist_path = "watchlist/my_watchlist.csv"
    data_dir = "data"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"\n📅 时间范围: {start_date} ~ {end_date}")

    # 加载 watchlist
    print(f"\n📋 加载 Watchlist: {watchlist_path}")
    items = load_watchlist(watchlist_path)
    print(f"   找到 {len(items)} 个品种")

    if not items:
        print("❌ Watchlist 为空")
        return

    # 显示品种列表
    for i, item in enumerate(items, 1):
        print(f"   {i}. {item['symbol']} - {item['name']} ({item['market']})")

    # 下载数据
    print("\n" + "=" * 60)
    print("开始下载数据...")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for item in items:
        symbol = item['symbol']
        market = item['market']

        # 下载
        df = download_symbol(symbol, market, start_date, end_date, data_dir)

        if df is not None and not df.empty:
            # 保存
            save_path = save_data(df, symbol, market, data_dir)
            success_count += 1
        else:
            fail_count += 1

    # 总结
    print("\n" + "=" * 60)
    print("下载完成")
    print("=" * 60)
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")

    # 显示保存的数据
    if success_count > 0:
        print("\n📁 保存的数据:")
        data_path = Path(data_dir)
        if data_path.exists():
            for market_dir in sorted(data_path.iterdir()):
                if market_dir.is_dir():
                    print(f"\n   {market_dir.name}/")
                    for symbol_dir in sorted(market_dir.iterdir()):
                        if symbol_dir.is_dir():
                            files = list(symbol_dir.glob("*.parquet"))
                            if files:
                                print(f"      {symbol_dir.name}/: {files[0].name} ({files[0].stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
