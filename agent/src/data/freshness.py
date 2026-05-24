"""数据新鲜度检查器

从 trading-assistant 移植
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .market import Timeframe

logger = logging.getLogger(__name__)


class DataFreshnessChecker:
    """数据新鲜度检查器"""

    # 默认新鲜度阈值（秒）
    FRESHNESS_THRESHOLDS = {
        Timeframe.H1: 4 * 3600,    # 4 小时
        Timeframe.H4: 24 * 3600,    # 24 小时
        Timeframe.D1: 3 * 24 * 3600,  # 3 天
        Timeframe.W1: 7 * 24 * 3600,  # 7 天
    }

    def __init__(self, custom_thresholds: Optional[dict] = None):
        """初始化检查器

        Args:
            custom_thresholds: 自定义阈值 {Timeframe: 秒}
        """
        self.thresholds = {**self.FRESHNESS_THRESHOLDS}
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)

    def is_fresh(
        self,
        last_update: datetime,
        timeframe: Timeframe,
        now: Optional[datetime] = None,
    ) -> bool:
        """检查数据是否新鲜

        Args:
            last_update: 最后更新时间
            timeframe: 时间周期
            now: 当前时间（默认 now()）

        Returns:
            是否新鲜
        """
        if now is None:
            now = datetime.now()

        threshold = self.thresholds.get(timeframe, 24 * 3600)
        age = (now - last_update).total_seconds()

        return age < threshold

    def get_freshness_status(
        self,
        last_update: datetime,
        timeframe: Timeframe,
        now: Optional[datetime] = None,
    ) -> str:
        """获取新鲜度状态

        Returns:
            "fresh" / "stale" / "very_stale"
        """
        if now is None:
            now = datetime.now()

        threshold = self.thresholds.get(timeframe, 24 * 3600)
        age = (now - last_update).total_seconds()

        if age < threshold:
            return "fresh"
        elif age < threshold * 2:
            return "stale"
        else:
            return "very_stale"

    def get_age_hours(self, last_update: datetime, now: Optional[datetime] = None) -> float:
        """获取数据年龄（小时）"""
        if now is None:
            now = datetime.now()
        return (now - last_update).total_seconds() / 3600
