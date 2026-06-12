"""数据新鲜度检查器

从 trading-assistant 移植
"""

import logging
from dataclasses import dataclass
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
        """Ensure a datetime is timezone-aware UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


def _ensure_timezone(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware UTC (module-level helper)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class FreshnessReport:
    """Full session-aware freshness report for a data source.

    CAL-03: Session-aware freshness detection.
    """
    status: str           # "fresh" | "stale" | "very_stale" | "session_closed" | "holiday"
    age_hours: float
    session_status: str   # MarketSessionStatus.value or "unknown"
    threshold_hours: float
    freshness_reason: str  # Human-readable reason for the status
    last_update: datetime
    check_time: datetime

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "age_hours": round(self.age_hours, 2),
            "session_status": self.session_status,
            "threshold_hours": round(self.threshold_hours, 2),
            "freshness_reason": self.freshness_reason,
            "last_update": self.last_update.isoformat(),
            "check_time": self.check_time.isoformat(),
        }


def get_session_aware_report(
    last_update: datetime,
    timeframe: Timeframe,
    market_code: str,
    now: datetime | None = None,
) -> FreshnessReport:
    """Return a full session-aware freshness report.

    Combines session status (from trading_sessions.py) with freshness age
    to produce a rich report with human-readable status and reason.

    Args:
        last_update: Timestamp of the last data update
        timeframe: Data timeframe (H1, H4, D1, W1)
        market_code: Market identifier (e.g., 'cn_stock', 'us_stock')
        now: Current time (default now() UTC)

    Returns:
        FreshnessReport with status, age, session status, threshold, and reason
    """
    from .trading_sessions import MarketSessionStatus, get_session_status

    if now is None:
        now = datetime.now(timezone.utc)

    now = _ensure_timezone(now)
    last_update = _ensure_timezone(last_update)

    checker = DataFreshnessChecker()
    age_hours = (now - last_update).total_seconds() / 3600.0

    session_status = get_session_status(market_code, now)
    session_name = session_status.value

    # Determine freshness
    if session_status == MarketSessionStatus.HOLIDAY:
        threshold_hours = checker.thresholds.get(timeframe, 24 * 3600) / 3600 * 2
        return FreshnessReport(
            status="holiday",
            age_hours=age_hours,
            session_status=session_name,
            threshold_hours=threshold_hours,
            freshness_reason=f"Market is closed for holiday — holiday threshold ({threshold_hours:.1f}h) applied",
            last_update=last_update,
            check_time=now,
        )

    if session_status == MarketSessionStatus.CLOSED:
        threshold = checker.thresholds.get(timeframe, 24 * 3600) / 3600
        if checker._updated_today_while_closed(last_update, now, market_code):
            threshold_hours = threshold
            return FreshnessReport(
                status="session_closed",
                age_hours=age_hours,
                session_status=session_name,
                threshold_hours=threshold_hours,
                freshness_reason=f"Market closed but data updated today — base threshold ({threshold_hours:.1f}h) applies",
                last_update=last_update,
                check_time=now,
            )
        else:
            threshold_hours = threshold * 1.5
            return FreshnessReport(
                status="session_closed",
                age_hours=age_hours,
                session_status=session_name,
                threshold_hours=threshold_hours,
                freshness_reason=f"Market closed, no update today — lenient threshold ({threshold_hours:.1f}h) applied",
                last_update=last_update,
                check_time=now,
            )

    if session_status == MarketSessionStatus.POST_MARKET:
        threshold = checker.thresholds.get(timeframe, 24 * 3600) / 3600
        threshold_hours = threshold * 1.5
        return FreshnessReport(
            status="stale" if age_hours > threshold_hours else "fresh",
            age_hours=age_hours,
            session_status=session_name,
            threshold_hours=threshold_hours,
            freshness_reason=f"Post-market session — lenient threshold ({threshold_hours:.1f}h) applied",
            last_update=last_update,
            check_time=now,
        )

    # PRE_MARKET, REGULAR, CONTINUOUS
    threshold = checker.thresholds.get(timeframe, 24 * 3600) / 3600
    threshold_hours = threshold

    if age_hours < threshold:
        return FreshnessReport(
            status="fresh",
            age_hours=age_hours,
            session_status=session_name,
            threshold_hours=threshold_hours,
            freshness_reason=f"Data within freshness threshold ({threshold_hours:.1f}h)",
            last_update=last_update,
            check_time=now,
        )
    elif age_hours < threshold * 2:
        return FreshnessReport(
            status="stale",
            age_hours=age_hours,
            session_status=session_name,
            threshold_hours=threshold_hours,
            freshness_reason=f"Data exceeds threshold but within 2x — marked stale ({age_hours:.1f}h > {threshold_hours:.1f}h)",
            last_update=last_update,
            check_time=now,
        )
    else:
        return FreshnessReport(
            status="very_stale",
            age_hours=age_hours,
            session_status=session_name,
            threshold_hours=threshold_hours,
            freshness_reason=f"Data is very stale ({age_hours:.1f}h > 2x threshold of {threshold_hours:.1f}h)",
            last_update=last_update,
            check_time=now,
        )
