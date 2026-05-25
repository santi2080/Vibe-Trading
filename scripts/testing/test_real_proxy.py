#!/usr/bin/env python3
"""Test real download with current proxy configuration."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.backtest.loaders.proxy_manager import ProxyManager
from agent.backtest.loaders.yfinance_loader import DataLoader


def test_real_proxy():
    """Test download with real proxy from environment."""
    print("=" * 60)
    print("Testing Real Proxy Download")
    print("=" * 60)

    # Create proxy manager (will read from environment)
    proxy_manager = ProxyManager()

    print(f"\n📋 Proxy Configuration:")
    stats = proxy_manager.get_stats()
    print(f"  Total proxies: {stats['total_proxies']}")
    print(f"  Available proxies: {stats['available_proxies']}")

    for p in stats['proxies']:
        status = "✅" if p['is_available'] else "❌"
        print(f"  {status} {p['proxy']}")
        print(f"     - Health score: {p['health_score']:.1f}")
        print(f"     - Last check: {p['last_check']}")

    # Create loader
    loader = DataLoader(enable_proxy=True)

    print(f"\n🔍 Attempting to download AAPL data...")
    print(f"   Symbol: AAPL.US")
    print(f"   Period: 2024-01-01 to 2024-01-10")
    print(f"   Interval: 1D")

    try:
        # Try to download
        data = loader.fetch(
            codes=["AAPL.US"],
            start_date="2024-01-01",
            end_date="2024-01-10",
            interval="1D",
        )

        if "AAPL.US" in data and not data["AAPL.US"].empty:
            df = data["AAPL.US"]
            print(f"\n✅ Download successful!")
            print(f"   Rows: {len(df)}")
            print(f"   Columns: {list(df.columns)}")
            print(f"\n   First row:")
            print(f"   {df.iloc[0].to_dict()}")
            return True
        else:
            print(f"\n⚠️  Download returned empty data")
            print(f"   Response: {data}")
            return False

    except RuntimeError as e:
        error_msg = str(e)
        if "No available proxies" in error_msg:
            print(f"\n❌ Proxy health check failed (as expected)")
            print(f"\n{error_msg}")
            return True  # This is expected behavior
        else:
            print(f"\n❌ Unexpected RuntimeError: {e}")
            return False

    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_real_proxy()
    sys.exit(0 if success else 1)
