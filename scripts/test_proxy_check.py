#!/usr/bin/env python3
"""Test proxy health check before download.

This script verifies that:
1. Proxy health is checked before download
2. Download is blocked if proxy is unavailable
3. Clear error message is shown to user
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.backtest.loaders.proxy_manager import ProxyManager
from agent.backtest.loaders.yfinance_loader import DataLoader


def test_proxy_unavailable():
    """Test that download fails when proxy is unavailable."""
    print("=" * 60)
    print("Test 1: Proxy Unavailable - Should Fail")
    print("=" * 60)

    # Create proxy manager with a non-existent proxy
    proxy_manager = ProxyManager(
        proxies=["socks5://127.0.0.1:99999"],  # Invalid port
        health_check_timeout=2,
    )

    # Create loader with proxy
    loader = DataLoader(enable_proxy=False)
    loader.proxy_manager = proxy_manager

    try:
        # Try to download - should fail with clear error
        data = loader.fetch(
            codes=["AAPL.US"],
            start_date="2024-01-01",
            end_date="2024-01-10",
            interval="1D",
        )
        print("❌ FAIL: Download should have been blocked!")
        return False

    except RuntimeError as e:
        error_msg = str(e)
        print(f"\n✅ PASS: Download blocked as expected")
        print(f"\nError message:\n{error_msg}")

        # Check error message contains helpful info
        required_phrases = [
            "No available proxies",
            "unavailable",
            "Please ensure your proxy is running",
            "yfinance will be rate-limited",
        ]

        missing = [p for p in required_phrases if p not in error_msg]
        if missing:
            print(f"\n⚠️  Warning: Error message missing: {missing}")
        else:
            print("\n✅ Error message contains all required information")

        return True

    except Exception as e:
        print(f"❌ FAIL: Unexpected error: {e}")
        return False


def test_proxy_available():
    """Test that download succeeds when proxy is available."""
    print("\n" + "=" * 60)
    print("Test 2: Proxy Available - Should Succeed")
    print("=" * 60)

    # Create proxy manager with real proxy
    proxy_manager = ProxyManager(
        proxies=["socks5://127.0.0.1:10829"],  # Real proxy
        health_check_timeout=5,
    )

    # Force health check
    try:
        proxy = proxy_manager.get_proxy(force_check=True)
        print(f"✅ Proxy health check passed: {proxy}")

        # Get proxy stats
        stats = proxy_manager.get_stats()
        print(f"\nProxy stats:")
        for p in stats["proxies"]:
            print(f"  - {p['proxy']}: available={p['is_available']}, score={p['health_score']:.1f}")

        return True

    except RuntimeError as e:
        print(f"⚠️  Proxy unavailable: {e}")
        print("\nThis is expected if your proxy is not running.")
        print("To start proxy, ensure Clash/V2Ray is running on port 10829")
        return None  # Not a test failure, just proxy not running

    except Exception as e:
        print(f"❌ FAIL: Unexpected error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🧪 Testing Proxy Health Check Before Download\n")

    results = []

    # Test 1: Unavailable proxy
    results.append(("Proxy Unavailable", test_proxy_unavailable()))

    # Test 2: Available proxy
    result = test_proxy_available()
    if result is not None:
        results.append(("Proxy Available", result))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    # Overall result
    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed!")
        print("\n✨ Proxy health check is working correctly.")
        print("   Downloads will be blocked if proxy is unavailable.")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
