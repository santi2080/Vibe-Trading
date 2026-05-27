"""报告生成器

根据分析结果生成 Markdown 格式的报告。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .watchlist_analyzer import AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """报告配置"""

    title: str = "Watchlist 分析报告"
    include_summary: bool = True
    include_details: bool = True
    include_charts: bool = False
    format_version: str = "1.0"


class ReportGenerator:
    """报告生成器

    将 AnalysisResult 列表转换为格式化的 Markdown 报告。
    """

    def __init__(self, config: Optional[ReportConfig] = None):
        """初始化

        Args:
            config: 报告配置
        """
        self.config = config or ReportConfig()

    def generate_summary(self, results: List[AnalysisResult]) -> dict:
        """生成汇总统计

        Args:
            results: AnalysisResult 列表

        Returns:
            dict: 汇总统计
        """
        total = len(results)
        errors = sum(1 for r in results if r.error)
        success = total - errors

        # 按趋势分类
        trends = {"UP": 0, "DOWN": 0, "SIDEWAYS": 0, "-": 0}
        for r in results:
            if r.error:
                continue
            trends[r.trend] = trends.get(r.trend, 0) + 1

        # 按信号分类
        signals = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0, "-": 0}
        for r in results:
            if r.error:
                continue
            signals[r.signal_direction] = signals.get(r.signal_direction, 0) + 1

        # 有效信号
        valid_signals = [r for r in results if r.error is None and r.signal_direction in ("LONG", "SHORT")]

        return {
            "total": total,
            "success": success,
            "errors": errors,
            "trends": trends,
            "signals": signals,
            "valid_signals": valid_signals,
            "long_signals": signals.get("LONG", 0),
            "short_signals": signals.get("SHORT", 0),
            "neutral_signals": signals.get("NEUTRAL", 0),
        }

    def generate_table(self, results: List[AnalysisResult]) -> str:
        """生成 Markdown 表格

        Args:
            results: AnalysisResult 列表

        Returns:
            str: Markdown 表格
        """
        if not results:
            return "| 代码 | 名称 | 趋势 | 回调 | 信号 | 信号价 | 信号日 | 止损价 | 1N |\n|---|---|---|---|---|---|---|---|---|"

        header = "| 代码 | 名称 | 趋势 | 回调 | 信号 | 信号价 | 信号日 | 止损价 | 1N |"
        separator = "|---|---|---|---|---|---|---|---|---|"

        rows = []
        for r in results:
            if r.error:
                rows.append(
                    f"| {r.symbol} | {r.name} | - | - | ❌ | - | - | - | - |"
                )
            else:
                trend_emoji = {"UP": "🟢", "DOWN": "🔴", "SIDEWAYS": "🟡", "-": "⚪"}.get(r.trend, "⚪")
                signal_emoji = {"LONG": "📈", "SHORT": "📉", "NEUTRAL": "➡️", "-": "⏸️"}.get(
                    r.signal_direction, "⏸️"
                )

                rows.append(
                    f"| {r.symbol} | {r.name} | {trend_emoji}{r.trend} | {r.pullback} | {signal_emoji}{r.signal_direction} | "
                    f"{f'{r.signal_price:.2f}' if r.signal_price else '-'} | {r.signal_date or '-'} | "
                    f"{f'{r.stop_loss:.2f}' if r.stop_loss else '-'} | {f'{r.atr_1n:.2f}' if r.atr_1n else '-'} |"
                )

        return "\n".join([header, separator] + rows)

    def generate_markdown(self, results: List[AnalysisResult], watchlist_name: str = "") -> str:
        """生成 Markdown 格式报告

        Args:
            results: AnalysisResult 列表
            watchlist_name: watchlist 名称

        Returns:
            str: Markdown 报告
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        summary = self.generate_summary(results)

        # 构建报告
        lines = [
            f"# {self.config.title}",
            "",
            f"**生成时间**: {timestamp}",
            f"**Watchlist**: {watchlist_name}",
            f"**证券数量**: {summary['total']}",
            "",
            "---",
            "",
        ]

        # 汇总统计
        if self.config.include_summary:
            lines.extend(
                [
                    "## 汇总统计",
                    "",
                    "| 指标 | 数量 |",
                    "|---|---|",
                    f"| 总计 | {summary['total']} |",
                    f"| 成功分析 | {summary['success']} |",
                    f"| 分析失败 | {summary['errors']} |",
                    "",
                    "### 趋势分布",
                    "",
                    "| 趋势 | 数量 |",
                    "|---|---|",
                    f"| 🟢 上涨 (UP) | {summary['trends'].get('UP', 0)} |",
                    f"| 🔴 下跌 (DOWN) | {summary['trends'].get('DOWN', 0)} |",
                    f"| 🟡 震荡 (SIDEWAYS) | {summary['trends'].get('SIDEWAYS', 0)} |",
                    "",
                    "### 信号分布",
                    "",
                    "| 信号 | 数量 |",
                    "|---|---|",
                    f"| 📈 多头 (LONG) | {summary['long_signals']} |",
                    f"| 📉 空头 (SHORT) | {summary['short_signals']} |",
                    f"| ➡️ 中性 (NEUTRAL) | {summary['neutral_signals']} |",
                    "",
                    "---",
                    "",
                ]
            )

        # 详细表格
        if self.config.include_details:
            lines.extend(
                [
                    "## 详细分析",
                    "",
                    self.generate_table(results),
                    "",
                    "---",
                    "",
                ]
            )

        # 有效信号详情
        if summary["valid_signals"]:
            lines.extend(
                [
                    "## 有效信号",
                    "",
                ]
            )
            for r in summary["valid_signals"]:
                direction_emoji = "📈" if r.signal_direction == "LONG" else "📉"
                stop_loss = f"{r.stop_loss:.2f}" if r.stop_loss is not None else "-"
                atr_1n = f"{r.atr_1n:.2f}" if r.atr_1n is not None else "-"
                lines.append(
                    f"- **{direction_emoji} {r.symbol} ({r.name})**: {r.signal_direction} @ {r.signal_price:.2f}, "
                    f"止损 {stop_loss} ({atr_1n} ATR)"
                )
            lines.append("")

        # 页脚
        lines.extend(
            [
                "---",
                "",
                "*报告由 Vibe-Trading 自动生成*",
            ]
        )

        return "\n".join(lines)

    def save_report(
        self, results: List[AnalysisResult], output_path: str, watchlist_name: str = ""
    ) -> str:
        """保存报告到文件

        Args:
            results: AnalysisResult 列表
            output_path: 输出文件路径
            watchlist_name: watchlist 名称

        Returns:
            str: 保存的文件路径
        """
        report = self.generate_markdown(results, watchlist_name)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"报告已保存: {output_path}")
        return output_path

    def print_summary(self, results: List[AnalysisResult]) -> None:
        """打印汇总到控制台

        Args:
            results: AnalysisResult 列表
        """
        summary = self.generate_summary(results)

        print()
        print("=" * 60)
        print("分析汇总")
        print("=" * 60)
        print(f"总计: {summary['total']} | 成功: {summary['success']} | 失败: {summary['errors']}")
        print()
        print(f"🟢 上涨: {summary['trends'].get('UP', 0)} | 🔴 下跌: {summary['trends'].get('DOWN', 0)} | 🟡 震荡: {summary['trends'].get('SIDEWAYS', 0)}")
        print()
        print(f"📈 多头: {summary['long_signals']} | 📉 空头: {summary['short_signals']} | ➡️ 中性: {summary['neutral_signals']}")
        print("=" * 60)
        print()

        # 列出有效信号
        valid = summary["valid_signals"]
        if valid:
            print("有效信号:")
            for r in valid:
                emoji = "📈" if r.signal_direction == "LONG" else "📉"
                print(f"  {emoji} {r.symbol}: {r.signal_direction} @ {r.signal_price:.2f}")
