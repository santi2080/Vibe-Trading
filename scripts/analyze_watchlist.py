#!/usr/bin/env python3
"""
Watchlist 分析脚本

用法:
    python scripts/analyze_watchlist.py --watchlist watchlist/us_futures_watchlist.csv --output report.md

参数:
    --watchlist: watchlist 文件路径 (默认: watchlist/us_futures_watchlist.csv)
    --strategy: 策略名称 (默认: ema_adx)
    --timeframe: 主时间周期 (默认: 1D)
    --output: 输出报告路径 (默认: watchlist_report.md)
    --format: 输出格式 (默认: markdown)
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.src.analysis import WatchlistAnalyzer, ReportGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Watchlist 分析脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--watchlist",
        "-w",
        type=str,
        default="watchlist/us_futures_watchlist.csv",
        help="watchlist 文件路径 (默认: watchlist/us_futures_watchlist.csv)",
    )

    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        default="ema_adx",
        help="策略名称 (默认: ema_adx)",
    )

    parser.add_argument(
        "--timeframe",
        "-t",
        type=str,
        default="1D",
        help="主时间周期 (默认: 1D)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="watchlist_report.md",
        help="输出报告路径 (默认: watchlist_report.md)",
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        default="markdown",
        choices=["markdown", "json", "console"],
        help="输出格式 (默认: markdown)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 配置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 60)
    print("Vibe-Trading Watchlist 分析")
    print("=" * 60)
    print(f"Watchlist: {args.watchlist}")
    print(f"策略: {args.strategy}")
    print(f"时间周期: {args.timeframe}")
    print("=" * 60)

    # 检查 watchlist 文件
    watchlist_path = Path(args.watchlist)
    if not watchlist_path.exists():
        print(f"❌ 文件不存在: {args.watchlist}")
        print("可用 watchlist 文件:")
        for f in Path("watchlist").glob("*.csv"):
            print(f"  - {f}")
        return 1

    # 初始化分析器
    analyzer = WatchlistAnalyzer(watchlist_path=args.watchlist)

    # 执行分析
    print("\n开始分析...\n")
    results = analyzer.analyze_all(watchlist_path=args.watchlist)

    # 生成报告
    report_gen = ReportGenerator()
    report_gen.print_summary(results)

    if args.format == "markdown":
        output_path = report_gen.save_report(
            results,
            args.output,
            watchlist_name=args.watchlist,
        )
        print(f"\n📄 报告已保存: {output_path}")

    elif args.format == "json":
        import json

        output_data = [r.__dict__ for r in results]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n📄 JSON 已保存: {args.output}")

    elif args.format == "console":
        print("\n" + report_gen.generate_table(results))

    print("\n✅ 分析完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
