"""数据新鲜度检查器

从 trading-assistant 移植
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .market import Timeframe

logger = logging.getLogger(__name__)


class DataFreshnessChecker:
    """数据新鲜度检查器"""

    # 默认新鲜度阈值（秒）
    FRESHNESS_THRESHOLDS = {
        Timeframe.H1: 4 * 3600,  # 4 小时
        Timeframe.H4: 24 * 3600,  # 24 小时
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
        session_context: Optional[str] = None,
    ) -> bool:
        """检查数据是否新鲜

        Args:
            last_update: 最后更新时间
            timeframe: 时间周期
            now: 当前时间（默认 now()）
            session_context: 市场代码；提供时会在休市且当日已更新场景抑制假陈旧

        Returns:
            是否新鲜
        """
        if now is None:
            now = datetime.now(timezone.utc)

        now = self._ensure_timezone(now)
        last_update = self._ensure_timezone(last_update)
        threshold = self.thresholds.get(timeframe, 24 * 3600)
        age = (now - last_update).total_seconds()

        if age < threshold:
            return True

        if session_context:
            from .trading_sessions import MarketSessionStatus, get_session_status

            status = get_session_status(session_context, now)
            if status == MarketSessionStatus.HOLIDAY:
                # Holiday: no special staleness suppression, but get_freshness_status returns 'holiday'
                # Fall through to normal threshold check (data from 4 hours ago is fresh, 5 hours ago is stale)
                pass
            elif status in (MarketSessionStatus.PRE_MARKET, MarketSessionStatus.POST_MARKET):
                return age < threshold * 1.5
            elif status == MarketSessionStatus.CLOSED:
                if self._updated_today_while_closed(last_update, now, session_context):
                    return True

        return False

    def get_freshness_status(
        self,
        last_update: datetime,
        timeframe: Timeframe,
        now: Optional[datetime] = None,
        session_context: Optional[str] = None,
    ) -> str:
        """获取新鲜度状态

        Returns:
            "fresh" / "stale" / "very_stale" / "session_closed"
        """
        if now is None:
            now = datetime.now(timezone.utc)

        now = self._ensure_timezone(now)
        last_update = self._ensure_timezone(last_update)
        threshold = self.thresholds.get(timeframe, 24 * 3600)
        age = (now - last_update).total_seconds()

        if session_context:
            from .trading_sessions import MarketSessionStatus, get_session_status

            status = get_session_status(session_context, now)
            if status == MarketSessionStatus.HOLIDAY:
                return "holiday"
            if status == MarketSessionStatus.CLOSED:
                if self._updated_today_while_closed(last_update, now, session_context):
                    return "session_closed"

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

    def _updated_today_while_closed(
        self,
        last_update: datetime,
        now: datetime,
        session_context: str,
    ) -> bool:
        from .trading_sessions import MARKET_TZ, MarketSessionStatus, get_session_status

        status = get_session_status(session_context, now)
        if status != MarketSessionStatus.CLOSED:
            return False
        tz_name = MARKET_TZ.get(session_context.lower())
        if not tz_name:
            return False
        market_tz = ZoneInfo(tz_name)
        return last_update.astimezone(market_tz).date() >= now.astimezone(market_tz).date()

    @staticmethod
    def _ensure_timezone(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
