"""Cache monitor for real-time performance tracking and alerting

Monitors cache performance with:
- Real-time hit rate tracking
- Memory usage trends
- Performance metrics collection
- Health checks and alerts
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HealthAlert:
    """Health alert for cache issues

    Attributes:
        timestamp: When the alert was generated
        severity: Alert severity (info, warning, critical)
        message: Human-readable alert message
        metric: The metric that triggered the alert
        value: The metric value
        threshold: The threshold that was exceeded
    """

    timestamp: datetime
    severity: str  # "info", "warning", "critical"
    message: str
    metric: str
    value: float
    threshold: float


@dataclass
class CacheMetrics:
    """Snapshot of cache metrics at a point in time

    Attributes:
        timestamp: When metrics were collected
        l1_entries: Number of L1 (memory) cache entries
        l1_memory_mb: L1 memory usage in MB
        l1_hit_rate: L1 cache hit rate
        l2_entries: Number of L2 (disk) cache entries
        l2_size_mb: L2 disk cache size in MB
        l2_hit_rate: L2 cache hit rate
        overall_hit_rate: Combined cache hit rate
        api_calls_saved: Estimated API calls saved by cache
    """

    timestamp: datetime
    l1_entries: int = 0
    l1_memory_mb: float = 0.0
    l1_hit_rate: float = 0.0
    l2_entries: int = 0
    l2_size_mb: float = 0.0
    l2_hit_rate: float = 0.0
    overall_hit_rate: float = 0.0
    api_calls_saved: int = 0


class CacheMonitor:
    """Cache performance monitor with health checks and alerting

    Features:
    - Collects and stores cache metrics over time
    - Performs health checks based on configurable thresholds
    - Generates alerts for performance issues
    - Provides trend analysis and reporting

    Usage:
        monitor = CacheMonitor(cache)

        # Collect metrics
        monitor.collect_metrics()

        # Check for alerts
        alerts = monitor.check_health()

        # Get performance report
        report = monitor.get_report()
    """

    def __init__(
        self,
        cache: Optional[object] = None,
        collection_interval_seconds: int = 300,
    ):
        """Initialize cache monitor

        Args:
            cache: DataCache instance to monitor (optional)
            collection_interval_seconds: Interval for metrics collection
        """
        self._cache = cache
        self._collection_interval = collection_interval_seconds
        self._metrics_history: List[CacheMetrics] = []
        self._alerts: List[HealthAlert] = []
        self._alert_callbacks: List[Callable[[HealthAlert], None]] = []

        # Thresholds for health checks
        self._thresholds = {
            "min_hit_rate": 0.5,        # Minimum acceptable hit rate (50%)
            "max_memory_usage_pct": 0.9,  # Max memory usage (90%)
            "max_l1_entries": 1000,      # Max L1 entries
            "max_l2_entries": 10000,      # Max L2 entries
            "max_l2_size_mb": 5120,      # Max L2 size (5GB)
            "max_miss_rate": 0.3,          # Max miss rate (30%)
        }

    def set_cache(self, cache: object) -> None:
        """Set the cache instance to monitor

        Args:
            cache: DataCache instance
        """
        self._cache = cache

    def collect_metrics(self) -> CacheMetrics:
        """Collect current cache metrics

        Returns:
            CacheMetrics snapshot
        """
        if self._cache is None:
            logger.warning("No cache set, returning empty metrics")
            return CacheMetrics(timestamp=datetime.now())

        # Get stats from cache
        stats = self._cache.get_stats()

        # Extract L1 (memory) stats
        l1_stats = stats.get("memory", {})
        l1_entries = l1_stats.get("entries", 0)
        l1_memory_mb = l1_stats.get("memory_mb", 0.0)
        l1_hits = stats.get("hits", {}).get("l1_hits", 0)

        # Extract L2 (disk) stats
        l2_stats = stats.get("disk", {})
        l2_entries = l2_stats.get("entries", 0)
        l2_size_mb = l2_stats.get("total_size_mb", 0.0)
        l2_hits = stats.get("hits", {}).get("l2_hits", 0)

        # Calculate hit rates
        total_requests = stats.get("hits", {}).get("total_requests", 1)
        misses = stats.get("hits", {}).get("misses", 0)

        l1_hit_rate = l1_hits / total_requests if total_requests > 0 else 0.0
        l2_hit_rate = l2_hits / total_requests if total_requests > 0 else 0.0
        overall_hit_rate = (l1_hits + l2_hits) / total_requests if total_requests > 0 else 0.0

        # Estimate API calls saved
        api_calls_saved = l1_hits + l2_hits

        # Create metrics snapshot
        metrics = CacheMetrics(
            timestamp=datetime.now(),
            l1_entries=l1_entries,
            l1_memory_mb=l1_memory_mb,
            l1_hit_rate=l1_hit_rate,
            l2_entries=l2_entries,
            l2_size_mb=l2_size_mb,
            l2_hit_rate=l2_hit_rate,
            overall_hit_rate=overall_hit_rate,
            api_calls_saved=api_calls_saved,
        )

        # Store in history (keep last 1000 snapshots)
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 1000:
            self._metrics_history = self._metrics_history[-1000:]

        return metrics

    def check_health(self) -> List[HealthAlert]:
        """Perform health checks and return alerts

        Returns:
            List of HealthAlert objects
        """
        if self._cache is None:
            return []

        alerts = []
        stats = self._cache.get_stats()

        # Check hit rate
        hit_rate = stats.get("hits", {}).get("hit_rate", 0.0)
        if hit_rate < self._thresholds["min_hit_rate"]:
            alert = HealthAlert(
                timestamp=datetime.now(),
                severity="warning" if hit_rate > 0.3 else "critical",
                message=f"Cache hit rate ({hit_rate:.1%}) is below threshold ({self._thresholds['min_hit_rate']:.1%})",
                metric="hit_rate",
                value=hit_rate,
                threshold=self._thresholds["min_hit_rate"],
            )
            alerts.append(alert)

        # Check L1 memory usage
        memory_stats = stats.get("memory", {})
        memory_pct = memory_stats.get("memory_mb", 0) / memory_stats.get("max_memory_mb", 1)
        if memory_pct > self._thresholds["max_memory_usage_pct"]:
            alert = HealthAlert(
                timestamp=datetime.now(),
                severity="warning",
                message=f"Memory usage ({memory_pct:.1%}) exceeds threshold ({self._thresholds['max_memory_usage_pct']:.1%})",
                metric="memory_usage",
                value=memory_pct,
                threshold=self._thresholds["max_memory_usage_pct"],
            )
            alerts.append(alert)

        # Check L1 entry count
        l1_entries = memory_stats.get("entries", 0)
        if l1_entries > self._thresholds["max_l1_entries"]:
            alert = HealthAlert(
                timestamp=datetime.now(),
                severity="info",
                message=f"L1 entries ({l1_entries}) exceeds recommended threshold ({self._thresholds['max_l1_entries']})",
                metric="l1_entries",
                value=l1_entries,
                threshold=self._thresholds["max_l1_entries"],
            )
            alerts.append(alert)

        # Check L2 entry count
        disk_stats = stats.get("disk", {})
        l2_entries = disk_stats.get("entries", 0)
        if l2_entries > self._thresholds["max_l2_entries"]:
            alert = HealthAlert(
                timestamp=datetime.now(),
                severity="info",
                message=f"L2 entries ({l2_entries}) exceeds recommended threshold ({self._thresholds['max_l2_entries']})",
                metric="l2_entries",
                value=l2_entries,
                threshold=self._thresholds["max_l2_entries"],
            )
            alerts.append(alert)

        # Check L2 size
        l2_size_mb = disk_stats.get("total_size_mb", 0.0)
        if l2_size_mb > self._thresholds["max_l2_size_mb"]:
            alert = HealthAlert(
                timestamp=datetime.now(),
                severity="warning",
                message=f"L2 cache size ({l2_size_mb:.1f} MB) exceeds threshold ({self._thresholds['max_l2_size_mb']} MB)",
                metric="l2_size",
                value=l2_size_mb,
                threshold=self._thresholds["max_l2_size_mb"],
            )
            alerts.append(alert)

        # Store alerts (keep last 100)
        self._alerts.extend(alerts)
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]

        # Notify callbacks
        for alert in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.warning(f"Alert callback failed: {e}")

        return alerts

    def get_report(self) -> str:
        """Generate a human-readable monitoring report

        Returns:
            String report with cache performance summary
        """
        if self._cache is None:
            return "Cache monitor: No cache set"

        stats = self._cache.get_stats()
        hits = stats.get("hits", {})
        memory = stats.get("memory", {})
        disk = stats.get("disk", {})

        # Get recent alerts
        recent_alerts = self._alerts[-5:] if self._alerts else []

        # Build report
        report_lines = [
            "# Cache Monitor Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Performance Summary",
            f"- L1 Hits: {hits.get('l1_hits', 0):,}",
            f"- L2 Hits: {hits.get('l2_hits', 0):,}",
            f"- Misses: {hits.get('misses', 0):,}",
            f"- Overall Hit Rate: {hits.get('hit_rate', 0):.1%}",
            "",
            "## Memory Cache (L1)",
            f"- Entries: {memory.get('entries', 0):,}",
            f"- Memory: {memory.get('memory_mb', 0):.1f} MB",
            f"- Usage: {memory.get('memory_mb', 0) / max(memory.get('max_memory_mb', 1), 1):.1%}",
            "",
            "## Disk Cache (L2)",
            f"- Entries: {disk.get('entries', 0):,}",
            f"- Size: {disk.get('total_size_mb', 0):.1f} MB",
            "",
        ]

        # Add alerts section
        if recent_alerts:
            report_lines.extend([
                "## Recent Alerts",
            ])
            for alert in recent_alerts:
                severity_emoji = {
                    "info": "ℹ️",
                    "warning": "⚠️",
                    "critical": "🔴",
                }.get(alert.severity, "❓")
                report_lines.append(f"{severity_emoji} [{alert.severity.upper()}] {alert.message}")

        # Add trend analysis if we have history
        if len(self._metrics_history) >= 2:
            first = self._metrics_history[0]
            last = self._metrics_history[-1]
            trend = last.overall_hit_rate - first.overall_hit_rate
            trend_emoji = "📈" if trend > 0 else "📉" if trend < 0 else "➡️"
            report_lines.extend([
                "",
                "## Trend Analysis",
                f"- Initial Hit Rate: {first.overall_hit_rate:.1%}",
                f"- Current Hit Rate: {last.overall_hit_rate:.1%}",
                f"- Change: {trend_emoji} {abs(trend):.1%}",
            ])

        return "\n".join(report_lines)

    def get_metrics_history(self, hours: int = 24) -> List[CacheMetrics]:
        """Get metrics history for the specified time period

        Args:
            hours: Number of hours to look back

        Returns:
            List of CacheMetrics from the specified period
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        return [m for m in self._metrics_history if m.timestamp >= cutoff]

    def get_alerts(self, severity: Optional[str] = None, hours: int = 24) -> List[HealthAlert]:
        """Get alerts from the specified time period

        Args:
            severity: Filter by severity (info, warning, critical)
            hours: Number of hours to look back

        Returns:
            List of HealthAlert objects
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        alerts = [a for a in self._alerts if a.timestamp >= cutoff]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def set_threshold(self, name: str, value: float) -> None:
        """Set a health check threshold

        Args:
            name: Threshold name (see _thresholds keys)
            value: New threshold value
        """
        if name in self._thresholds:
            self._thresholds[name] = value
            logger.info(f"Set threshold {name} = {value}")
        else:
            logger.warning(f"Unknown threshold: {name}")

    def register_alert_callback(self, callback: Callable[[HealthAlert], None]) -> None:
        """Register a callback to be called when alerts are generated

        Args:
            callback: Function to call with HealthAlert
        """
        self._alert_callbacks.append(callback)

    def clear_alerts(self) -> None:
        """Clear all stored alerts"""
        self._alerts.clear()

    def get_summary(self) -> Dict:
        """Get a summary of current cache state

        Returns:
            Dictionary with cache summary
        """
        if self._cache is None:
            return {"status": "no_cache"}

        stats = self._cache.get_stats()
        hits = stats.get("hits", {})

        return {
            "status": "healthy" if hits.get("hit_rate", 0) > 0.5 else "degraded",
            "overall_hit_rate": hits.get("hit_rate", 0),
            "l1_entries": stats.get("memory", {}).get("entries", 0),
            "l2_entries": stats.get("disk", {}).get("entries", 0),
            "api_calls_saved": hits.get("l1_hits", 0) + hits.get("l2_hits", 0),
            "recent_alerts": len([a for a in self._alerts if a.timestamp > datetime.now() - timedelta(hours=1)]),
        }
