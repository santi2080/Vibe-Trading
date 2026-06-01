"""
MTES v2 适配器 - 兼容层

将 MTES v3 的结果转换为 MTES v2 格式，
确保现有代码可以无缝迁移。
"""
from typing import Optional
from dataclasses import dataclass
import pandas as pd

from .base import MTESv3Result, TrendBias, StrengthRatingResult, EntrySignal


@dataclass
class MTESv2Result:
    """MTES v2 格式兼容结果"""
    # v2 字段映射
    trend_score: float      # -100 ~ +100
    trend_direction: str   # BULL/BEAR/NEUTRAL
    trend_confidence: float  # 0-1
    adx_value: float
    adx_rating: str        # STRONG/READY/WEAK/EXHAUSTED
    entry_signal: str       # LONG/SHORT/WAIT
    entry_reason: str
    mtf_alignment: bool   # 多时间框架是否对齐
    score_components: dict # 各维度评分详情


class MTESv2Adapter:
    """MTES v2 适配器"""

    def convert(self, v3_result: MTESv3Result) -> MTESv2Result:
        """将 MTES v3 结果转换为 v2 格式"""
        return MTESv2Result(
            trend_score=v3_result.final_score,
            trend_direction=v3_result.mtf_trend.direction,
            trend_confidence=v3_result.final_confidence,
            adx_value=v3_result.strength.adx_value,
            adx_rating=v3_result.strength.rating,
            entry_signal=v3_result.entry.signal,
            entry_reason=v3_result.entry.reason or "",
            mtf_alignment=self._check_mtf_alignment(v3_result),
            score_components=self._extract_components(v3_result)
        )

    def _check_mtf_alignment(self, result: MTESv3Result) -> bool:
        """检查多时间框架对齐"""
        signals = result.mtf_trend.signals

        # 检查 SMC、Elder、Ichimoku 是否一致
        smc_dir = signals.get("smc", {}).get("direction", "NEUTRAL")
        elder_dir = signals.get("elder", {}).get("direction", "NEUTRAL")
        ichimoku_dir = signals.get("ichimoku", {}).get("direction", "NEUTRAL")

        # 至少两个系统一致
        matches = sum([
            smc_dir == elder_dir,
            smc_dir == ichimoku_dir,
            elder_dir == ichimoku_dir
        ])

        return matches >= 2

    def _extract_components(self, result: MTESv3Result) -> dict:
        """提取各维度评分"""
        signals = result.mtf_trend.signals

        return {
            "smc_confidence": signals.get("smc", {}).get("confidence", 0),
            "elder_confidence": signals.get("elder", {}).get("confidence", 0),
            "ichimoku_confidence": signals.get("ichimoku", {}).get("confidence", 0),
            "divergence_detected": result.strength.divergence,
            "rsi_value": signals.get("elder", {}).get("rsi", 50),
            "bos_confirmed": signals.get("smc", {}).get("bos_confirmed", False)
        }

    def analyze(self, df: pd.DataFrame, mtes_v3) -> MTESv2Result:
        """使用 MTES v3 进行分析并返回 v2 格式"""
        v3_result = mtes_v3.analyze(df)
        return self.convert(v3_result)


def create_mtes_v2_result(v3_result: MTESv3Result) -> MTESv2Result:
    """便捷函数：创建 v2 格式结果"""
    adapter = MTESv2Adapter()
    return adapter.convert(v3_result)
