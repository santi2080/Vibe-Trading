"""Tests for CacheMonitor"""

import pytest
from datetime import datetime
from agent.backtest.loaders.cache.cache_monitor import CacheMonitor, CacheMetrics, HealthAlert


class TestCacheMonitor:
    """Test CacheMonitor functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = CacheMonitor()

    def _create_mock_cache(self, stats: dict) -> object:
        """Create a mock cache with specified stats"""
        class MockCache:
            def get_stats(self):
                return stats
        return MockCache()

    def test_monitor_initialization(self):
        """Test monitor initialization"""
        assert self.monitor._cache is None
        assert len(self.monitor._metrics_history) == 0
        assert len(self.monitor._alerts) == 0

    def test_set_cache(self):
        """Test setting cache instance"""
        mock_cache = self._create_mock_cache({})
        self.monitor.set_cache(mock_cache)
        assert self.monitor._cache is mock_cache

    def test_collect_metrics_no_cache(self):
        """Test collecting metrics when no cache is set"""
        metrics = self.monitor.collect_metrics()
        assert metrics.timestamp is not None
        assert metrics.l1_entries == 0
        assert metrics.l2_entries == 0

    def test_collect_metrics_with_cache(self):
        """Test collecting metrics with a cache"""
        mock_stats = {
            "memory": {
                "entries": 50,
                "memory_mb": 256.0,
            },
            "disk": {
                "entries": 200,
                "total_size_mb": 512.0,
            },
            "hits": {
                "l1_hits": 100,
                "l2_hits": 50,
                "misses": 30,
                "total_requests": 180,
                "hit_rate": 0.833,
            },
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        metrics = self.monitor.collect_metrics()

        assert metrics.l1_entries == 50
        assert metrics.l1_memory_mb == 256.0
        assert metrics.l2_entries == 200
        assert metrics.l2_size_mb == 512.0
        assert metrics.overall_hit_rate == pytest.approx(0.833, abs=0.01)

    def test_collect_metrics_updates_history(self):
        """Test that collecting metrics updates history"""
        mock_cache = self._create_mock_cache({"memory": {}, "disk": {}, "hits": {}})
        self.monitor.set_cache(mock_cache)

        assert len(self.monitor._metrics_history) == 0

        self.monitor.collect_metrics()
        assert len(self.monitor._metrics_history) == 1

        self.monitor.collect_metrics()
        assert len(self.monitor._metrics_history) == 2


class TestCacheMonitorHealthChecks:
    """Test health check functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = CacheMonitor()

    def _create_mock_cache(self, stats: dict) -> object:
        """Create a mock cache with specified stats"""
        class MockCache:
            def get_stats(self):
                return stats
        return MockCache()

    def test_check_health_no_cache(self):
        """Test health check with no cache"""
        alerts = self.monitor.check_health()
        assert len(alerts) == 0

    def test_check_health_healthy_cache(self):
        """Test health check with healthy cache"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.8, "l1_hits": 100, "l2_hits": 50, "misses": 30, "total_requests": 180},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        alerts = self.monitor.check_health()
        assert len(alerts) == 0

    def test_check_health_low_hit_rate(self):
        """Test health check detects low hit rate"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.31, "l1_hits": 30, "l2_hits": 0, "misses": 70, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        alerts = self.monitor.check_health()

        assert len(alerts) == 1
        assert alerts[0].metric == "hit_rate"
        assert alerts[0].severity == "warning"

    def test_check_health_critical_hit_rate(self):
        """Test health check detects critical hit rate"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.2, "l1_hits": 20, "l2_hits": 0, "misses": 80, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        alerts = self.monitor.check_health()

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_check_health_high_memory(self):
        """Test health check detects high memory usage"""
        mock_stats = {
            "memory": {"entries": 100, "memory_mb": 480.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.8, "l1_hits": 100, "l2_hits": 50, "misses": 30, "total_requests": 180},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        alerts = self.monitor.check_health()

        # Should have memory alert
        memory_alerts = [a for a in alerts if a.metric == "memory_usage"]
        assert len(memory_alerts) == 1
        assert memory_alerts[0].severity == "warning"

    def test_check_health_multiple_alerts(self):
        """Test multiple alerts are detected"""
        mock_stats = {
            "memory": {"entries": 1100, "memory_mb": 500.0, "max_memory_mb": 512.0},
            "disk": {"entries": 11000, "total_size_mb": 6000.0},
            "hits": {"hit_rate": 0.3, "l1_hits": 30, "l2_hits": 0, "misses": 70, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        alerts = self.monitor.check_health()

        assert len(alerts) >= 3


class TestCacheMonitorThresholds:
    """Test threshold configuration"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = CacheMonitor()

    def _create_mock_cache(self, stats: dict) -> object:
        """Create a mock cache with specified stats"""
        class MockCache:
            def get_stats(self):
                return stats
        return MockCache()

    def test_set_threshold(self):
        """Test setting custom threshold"""
        self.monitor.set_threshold("min_hit_rate", 0.7)
        assert self.monitor._thresholds["min_hit_rate"] == 0.7

    def test_set_threshold_invalid(self):
        """Test setting invalid threshold is handled"""
        # Should not raise, just log warning
        self.monitor.set_threshold("invalid_threshold", 0.5)

    def test_custom_threshold_triggers_alert(self):
        """Test that custom threshold triggers alerts"""
        # Set a high threshold
        self.monitor.set_threshold("min_hit_rate", 0.9)

        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.85, "l1_hits": 85, "l2_hits": 0, "misses": 15, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        alerts = self.monitor.check_health()

        # With 0.9 threshold and 0.85 hit rate, should trigger alert
        assert len(alerts) == 1
        assert alerts[0].metric == "hit_rate"


class TestCacheMonitorReporting:
    """Test reporting functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = CacheMonitor()

    def _create_mock_cache(self, stats: dict) -> object:
        """Create a mock cache with specified stats"""
        class MockCache:
            def get_stats(self):
                return stats
        return MockCache()

    def test_get_report_no_cache(self):
        """Test report with no cache"""
        report = self.monitor.get_report()
        assert "No cache set" in report

    def test_get_report_with_cache(self):
        """Test report with cache"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.8, "l1_hits": 100, "l2_hits": 50, "misses": 30, "total_requests": 180},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        report = self.monitor.get_report()

        assert "Cache Monitor Report" in report
        assert "L1 Hits: 100" in report
        assert "Overall Hit Rate: 80.0%" in report

    def test_get_summary(self):
        """Test getting summary"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.8, "l1_hits": 100, "l2_hits": 50, "misses": 30, "total_requests": 180},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        summary = self.monitor.get_summary()

        assert summary["status"] == "healthy"
        assert summary["overall_hit_rate"] == 0.8
        assert summary["l1_entries"] == 50
        assert summary["l2_entries"] == 200
        assert summary["api_calls_saved"] == 150


class TestCacheMonitorCallbacks:
    """Test alert callbacks"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = CacheMonitor()

    def _create_mock_cache(self, stats: dict) -> object:
        """Create a mock cache with specified stats"""
        class MockCache:
            def get_stats(self):
                return stats
        return MockCache()

    def test_register_alert_callback(self):
        """Test registering alert callback"""
        callback_called = []

        def callback(alert):
            callback_called.append(alert)

        self.monitor.register_alert_callback(callback)

        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.3, "l1_hits": 30, "l2_hits": 0, "misses": 70, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        self.monitor.check_health()

        assert len(callback_called) == 1
        assert callback_called[0].metric == "hit_rate"

    def test_clear_alerts(self):
        """Test clearing alerts"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.3, "l1_hits": 30, "l2_hits": 0, "misses": 70, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        self.monitor.check_health()
        assert len(self.monitor._alerts) == 1

        self.monitor.clear_alerts()
        assert len(self.monitor._alerts) == 0


class TestCacheMonitorHistory:
    """Test metrics history functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = CacheMonitor()

    def _create_mock_cache(self, stats: dict) -> object:
        """Create a mock cache with specified stats"""
        class MockCache:
            def get_stats(self):
                return stats
        return MockCache()

    def test_get_metrics_history(self):
        """Test getting metrics history"""
        mock_cache = self._create_mock_cache({
            "memory": {"entries": 50, "memory_mb": 256.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.8, "l1_hits": 100, "l2_hits": 50, "misses": 30, "total_requests": 180},
        })
        self.monitor.set_cache(mock_cache)

        # Collect some metrics
        for _ in range(3):
            self.monitor.collect_metrics()

        history = self.monitor.get_metrics_history(hours=24)
        assert len(history) == 3

    def test_get_alerts_with_severity_filter(self):
        """Test filtering alerts by severity"""
        mock_stats = {
            "memory": {"entries": 50, "memory_mb": 256.0, "max_memory_mb": 512.0},
            "disk": {"entries": 200, "total_size_mb": 512.0},
            "hits": {"hit_rate": 0.3, "l1_hits": 30, "l2_hits": 0, "misses": 70, "total_requests": 100},
        }
        mock_cache = self._create_mock_cache(mock_stats)
        self.monitor.set_cache(mock_cache)

        self.monitor.check_health()

        alerts = self.monitor.get_alerts(severity="warning")
        assert all(a.severity == "warning" for a in alerts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
