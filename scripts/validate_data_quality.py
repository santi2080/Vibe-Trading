#!/usr/bin/env python3
"""
数据质量验证脚本

验证已下载的数据质量：
1. 字段完整性
2. 缺失值检查
3. 异常值检查
4. 数据连续性检查
"""

import sys
from pathlib import Path
from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_dataframe(df: pd.DataFrame, symbol: str) -> Dict:
    """验证单个数据框的质量"""

    results = {
        'symbol': symbol,
        'status': 'success',
        'errors': [],
        'warnings': [],
        'stats': {}
    }

    # 1. 检查必需字段
    required_fields = ['open', 'high', 'low', 'close', 'volume']
    missing_fields = [f for f in required_fields if f not in df.columns]

    if missing_fields:
        results['errors'].append(f"缺少字段: {', '.join(missing_fields)}")
        results['status'] = 'error'
        return results

    # 2. 基本统计
    results['stats']['rows'] = len(df)
    results['stats']['date_range'] = {
        'start': df.index.min().strftime('%Y-%m-%d'),
        'end': df.index.max().strftime('%Y-%m-%d'),
        'days': (df.index.max() - df.index.min()).days
    }

    # 3. 检查缺失值
    missing_counts = df[required_fields].isnull().sum()
    if missing_counts.sum() > 0:
        results['warnings'].append(f"缺失值: {missing_counts[missing_counts > 0].to_dict()}")

    results['stats']['missing_values'] = missing_counts.to_dict()

    # 4. 检查异常值

    # 4.1 价格为0或负数
    for col in ['open', 'high', 'low', 'close']:
        zero_or_negative = (df[col] <= 0).sum()
        if zero_or_negative > 0:
            results['errors'].append(f"{col} 有 {zero_or_negative} 个零或负值")
            results['status'] = 'error'

    # 4.2 成交量为负数
    negative_volume = (df['volume'] < 0).sum()
    if negative_volume > 0:
        results['errors'].append(f"volume 有 {negative_volume} 个负值")
        results['status'] = 'error'

    # 4.3 high < low (不合理)
    invalid_hl = (df['high'] < df['low']).sum()
    if invalid_hl > 0:
        results['errors'].append(f"有 {invalid_hl} 条数据 high < low")
        results['status'] = 'error'

    # 4.4 close 超出 [low, high] 范围
    invalid_close = ((df['close'] < df['low']) | (df['close'] > df['high'])).sum()
    if invalid_close > 0:
        results['errors'].append(f"有 {invalid_close} 条数据 close 超出 [low, high]")
        results['status'] = 'error'

    # 5. 价格范围统计
    results['stats']['price_range'] = {
        'min': float(df['close'].min()),
        'max': float(df['close'].max()),
        'mean': float(df['close'].mean()),
        'std': float(df['close'].std())
    }

    # 6. 成交量统计
    results['stats']['volume'] = {
        'min': int(df['volume'].min()),
        'max': int(df['volume'].max()),
        'mean': float(df['volume'].mean()),
        'zero_volume_days': int((df['volume'] == 0).sum())
    }

    if results['stats']['volume']['zero_volume_days'] > 0:
        pct = results['stats']['volume']['zero_volume_days'] / len(df) * 100
        results['warnings'].append(f"有 {results['stats']['volume']['zero_volume_days']} 天成交量为0 ({pct:.1f}%)")

    # 7. 数据连续性检查
    date_diff = df.index.to_series().diff()
    max_gap = date_diff.max()

    if max_gap > pd.Timedelta(days=7):
        results['warnings'].append(f"最大数据间隔: {max_gap.days} 天")

    results['stats']['max_gap_days'] = max_gap.days if pd.notna(max_gap) else 0

    # 8. 价格波动检查（检测异常波动）
    returns = df['close'].pct_change()
    extreme_moves = (returns.abs() > 0.2).sum()  # 单日涨跌超过20%

    if extreme_moves > 0:
        results['warnings'].append(f"有 {extreme_moves} 天单日涨跌幅超过20%")

    results['stats']['extreme_moves'] = int(extreme_moves)

    return results


def validate_all_data(data_dir: str = "data") -> List[Dict]:
    """验证所有已下载的数据"""

    data_path = Path(data_dir)
    results = []

    if not data_path.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return results

    # 遍历所有市场
    for market_dir in sorted(data_path.iterdir()):
        if not market_dir.is_dir() or market_dir.name.startswith('.'):
            continue

        market = market_dir.name

        # 遍历所有品种
        for symbol_dir in sorted(market_dir.iterdir()):
            if not symbol_dir.is_dir():
                continue

            symbol = symbol_dir.name

            # 查找 parquet 文件
            parquet_files = list(symbol_dir.glob("*.parquet"))

            if not parquet_files:
                results.append({
                    'symbol': symbol,
                    'market': market,
                    'status': 'error',
                    'errors': ['没有找到 parquet 文件'],
                    'warnings': [],
                    'stats': {}
                })
                continue

            # 验证第一个 parquet 文件
            parquet_file = parquet_files[0]

            try:
                df = pd.read_parquet(parquet_file)
                result = validate_dataframe(df, symbol)
                result['market'] = market
                result['file'] = str(parquet_file.relative_to(data_path))
                result['file_size_kb'] = parquet_file.stat().st_size // 1024
                results.append(result)

            except Exception as e:
                results.append({
                    'symbol': symbol,
                    'market': market,
                    'status': 'error',
                    'errors': [f"读取文件失败: {str(e)}"],
                    'warnings': [],
                    'stats': {}
                })

    return results


def print_report(results: List[Dict]):
    """打印验证报告"""

    print("=" * 80)
    print("数据质量验证报告")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # 统计
    total = len(results)
    success = len([r for r in results if r['status'] == 'success'])
    error = len([r for r in results if r['status'] == 'error'])

    print(f"总品种数: {total}")
    print(f"✅ 通过: {success}")
    print(f"❌ 失败: {error}")
    print()

    # 详细结果
    for result in results:
        print("-" * 80)
        print(f"品种: {result['symbol']} ({result.get('market', 'unknown')})")
        print(f"状态: {'✅ 通过' if result['status'] == 'success' else '❌ 失败'}")

        if 'file' in result:
            print(f"文件: {result['file']} ({result.get('file_size_kb', 0)} KB)")

        # 统计信息
        if result['stats']:
            stats = result['stats']

            if 'rows' in stats:
                print(f"\n数据量: {stats['rows']} 条")

            if 'date_range' in stats:
                dr = stats['date_range']
                print(f"时间范围: {dr['start']} ~ {dr['end']} ({dr['days']} 天)")

            if 'price_range' in stats:
                pr = stats['price_range']
                print(f"价格范围: {pr['min']:.2f} ~ {pr['max']:.2f} (均值: {pr['mean']:.2f})")

            if 'volume' in stats:
                vol = stats['volume']
                print(f"成交量: {vol['min']} ~ {vol['max']} (均值: {vol['mean']:.0f})")
                if vol['zero_volume_days'] > 0:
                    print(f"  ⚠️ 零成交量天数: {vol['zero_volume_days']}")

            if 'max_gap_days' in stats and stats['max_gap_days'] > 0:
                print(f"最大数据间隔: {stats['max_gap_days']} 天")

            if 'extreme_moves' in stats and stats['extreme_moves'] > 0:
                print(f"  ⚠️ 极端波动天数: {stats['extreme_moves']}")

        # 错误
        if result['errors']:
            print(f"\n❌ 错误:")
            for error in result['errors']:
                print(f"  - {error}")

        # 警告
        if result['warnings']:
            print(f"\n⚠️ 警告:")
            for warning in result['warnings']:
                print(f"  - {warning}")

        print()

    # 总结
    print("=" * 80)
    print("验证完成")
    print("=" * 80)

    if error == 0:
        print("✅ 所有数据质量检查通过")
    else:
        print(f"⚠️ 有 {error} 个品种存在问题，请检查")


def main():
    """主函数"""

    # 验证数据
    results = validate_all_data()

    # 打印报告
    print_report(results)

    # 保存报告
    report_file = f"data_quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    # 重定向输出到文件
    import io
    from contextlib import redirect_stdout

    with open(report_file, 'w', encoding='utf-8') as f:
        with redirect_stdout(f):
            print_report(results)

    print(f"\n报告已保存到: {report_file}")


if __name__ == "__main__":
    main()
