"""Proxy manager for handling proxy rotation and health checks."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ProxyHealth:
    """Proxy health status."""

    proxy: str
    success_count: int = 0
    failure_count: int = 0
    total_latency: float = 0.0
    last_check: Optional[datetime] = None
    is_available: bool = True

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0-1)."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def avg_latency(self) -> float:
        """Calculate average latency in seconds."""
        return self.total_latency / self.success_count if self.success_count > 0 else 0.0

    @property
    def health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        if not self.is_available:
            return 0.0

        # Success rate: 60% weight
        success_score = self.success_rate * 60

        # Latency: 40% weight (lower is better)
        # Assume 0-5s latency range, normalize to 0-1
        latency_score = max(0, 1 - (self.avg_latency / 5.0)) * 40

        return success_score + latency_score


class ProxyManager:
    """Manage proxy pool with health checks and automatic rotation.

    Features:
    - Proxy pool management
    - Health checks with configurable interval
    - Automatic rotation on failure
    - Performance monitoring

    Example:
        >>> manager = ProxyManager(
        ...     proxies=["socks5://127.0.0.1:10829"],
        ...     health_check_interval=300,
        ... )
        >>> proxy = manager.get_proxy()
        >>> manager.record_request(proxy, success=True, latency=0.5)
    """

    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        health_check_interval: int = 300,
        health_check_timeout: int = 10,
        test_url: str = "https://finance.yahoo.com",
        max_failures: int = 3,
    ):
        """Initialize proxy manager.

        Args:
            proxies: List of proxy URLs. If None, reads from environment.
            health_check_interval: Seconds between health checks.
            health_check_timeout: Timeout for health check requests.
            test_url: URL to test proxy connectivity.
            max_failures: Max consecutive failures before marking proxy unavailable.
        """
        self.proxies = proxies or self._load_proxies_from_env()
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout
        self.test_url = test_url
        self.max_failures = max_failures

        # Health tracking
        self.health: Dict[str, ProxyHealth] = {
            proxy: ProxyHealth(proxy=proxy) for proxy in self.proxies
        }

        # Current proxy index
        self.current_index = 0

        # Request history (last 100 requests per proxy)
        self.request_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        logger.info(f"Initialized ProxyManager with {len(self.proxies)} proxies")

    def _load_proxies_from_env(self) -> List[str]:
        """Load proxies from environment variables."""
        proxies = []

        # Check common proxy environment variables
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
            proxy = os.getenv(var)
            if proxy and proxy not in proxies:
                proxies.append(proxy)

        if not proxies:
            logger.warning("No proxies configured in environment")

        return proxies

    def get_proxy(self, force_check: bool = False) -> Optional[str]:
        """Get the current best proxy.

        Args:
            force_check: If True, force health check before returning proxy.

        Returns:
            Proxy URL or None if no proxies configured.

        Raises:
            RuntimeError: If proxies are configured but none are available.
        """
        if not self.proxies:
            return None

        # Force health check if requested
        if force_check:
            logger.info("Forcing proxy health check before download")
            for proxy in self.proxies:
                self._check_proxy_health(proxy)
        else:
            # Check if health check is needed (periodic)
            self._check_health_if_needed()

        # Find best available proxy
        available_proxies = [
            (proxy, health.health_score)
            for proxy, health in self.health.items()
            if health.is_available
        ]

        if not available_proxies:
            # ❌ No available proxies - MUST NOT proceed
            proxy_status = "\n".join([
                f"  - {proxy}: {'✅ available' if health.is_available else '❌ unavailable'}"
                for proxy, health in self.health.items()
            ])
            error_msg = (
                f"No available proxies! All {len(self.proxies)} proxies are unavailable.\n"
                f"Proxy status:\n{proxy_status}\n\n"
                f"⚠️  Please ensure your proxy is running before downloading data.\n"
                f"   Without a working proxy, yfinance will be rate-limited.\n\n"
                f"To start proxy:\n"
                f"  - Check if proxy service is running (e.g., Clash, V2Ray)\n"
                f"  - Verify proxy URL: {self.proxies[0]}\n"
                f"  - Test manually: curl --proxy {self.proxies[0]} https://finance.yahoo.com"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Sort by health score (descending)
        available_proxies.sort(key=lambda x: x[1], reverse=True)
        best_proxy = available_proxies[0][0]

        logger.info(f"✅ Selected proxy: {best_proxy} (health score: {available_proxies[0][1]:.1f})")
        return best_proxy

    def record_request(self, proxy: str, success: bool, latency: float):
        """Record a request result for health tracking.

        Args:
            proxy: Proxy URL used for the request.
            success: Whether the request succeeded.
            latency: Request latency in seconds.
        """
        if proxy not in self.health:
            logger.warning(f"Unknown proxy: {proxy}")
            return

        health = self.health[proxy]

        if success:
            health.success_count += 1
            health.total_latency += latency
            # Reset failure count on success
            consecutive_failures = 0
        else:
            health.failure_count += 1
            # Count consecutive failures
            recent = list(self.request_history[proxy])[-self.max_failures:]
            consecutive_failures = sum(1 for r in recent if not r["success"])

            # Mark unavailable if too many consecutive failures
            if consecutive_failures >= self.max_failures:
                health.is_available = False
                logger.warning(
                    f"Proxy {proxy} marked unavailable after {consecutive_failures} failures"
                )

        # Record in history
        self.request_history[proxy].append({
            "success": success,
            "latency": latency,
            "timestamp": datetime.now(),
        })

        logger.debug(
            f"Recorded request for {proxy}: success={success}, latency={latency:.2f}s"
        )

    def rotate_proxy(self):
        """Rotate to the next proxy in the pool."""
        if len(self.proxies) <= 1:
            logger.debug("Only one proxy available, cannot rotate")
            return

        old_proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        new_proxy = self.proxies[self.current_index]

        logger.info(f"Rotated proxy: {old_proxy} -> {new_proxy}")

    def _check_health_if_needed(self):
        """Check proxy health if interval has passed."""
        now = datetime.now()

        for proxy, health in self.health.items():
            # Skip if recently checked
            if health.last_check:
                elapsed = (now - health.last_check).total_seconds()
                if elapsed < self.health_check_interval:
                    continue

            # Perform health check
            self._check_proxy_health(proxy)

    def _check_proxy_health(self, proxy: str):
        """Check if a proxy is healthy.

        Args:
            proxy: Proxy URL to check.
        """
        health = self.health[proxy]

        try:
            start = time.time()
            response = requests.get(
                self.test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=self.health_check_timeout,
            )
            latency = time.time() - start

            if response.status_code == 200:
                health.is_available = True
                logger.debug(f"Proxy {proxy} health check passed (latency: {latency:.2f}s)")
            else:
                health.is_available = False
                logger.warning(f"Proxy {proxy} health check failed: HTTP {response.status_code}")

        except Exception as exc:
            health.is_available = False
            logger.warning(f"Proxy {proxy} health check failed: {exc}")

        health.last_check = datetime.now()

    def get_stats(self) -> Dict:
        """Get proxy statistics.

        Returns:
            Dictionary with proxy stats.
        """
        stats = {
            "total_proxies": len(self.proxies),
            "available_proxies": sum(1 for h in self.health.values() if h.is_available),
            "proxies": [],
        }

        for proxy, health in self.health.items():
            stats["proxies"].append({
                "proxy": proxy,
                "is_available": health.is_available,
                "success_rate": health.success_rate,
                "avg_latency": health.avg_latency,
                "health_score": health.health_score,
                "total_requests": health.success_count + health.failure_count,
                "last_check": health.last_check.isoformat() if health.last_check else None,
            })

        # Sort by health score
        stats["proxies"].sort(key=lambda x: x["health_score"], reverse=True)

        return stats
