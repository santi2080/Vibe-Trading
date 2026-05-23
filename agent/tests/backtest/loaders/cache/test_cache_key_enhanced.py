"""Tests for enhanced CacheKey with expression support"""

import pytest
from datetime import datetime
from agent.backtest.loaders.cache.cache_key import CacheKey


class TestCacheKeyExpression:
    """Test expression cache support in CacheKey"""

    def test_cache_key_with_expression(self):
        """Test creating cache key with expression"""
        key = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            fields=["close"],
            expression="ts_mean(close, 20)",
        )

        assert key.expression == "ts_mean(close, 20)"
        assert key.symbol == "BTC-USDT"

    def test_cache_key_without_expression(self):
        """Test creating cache key without expression (backward compatible)"""
        key = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )

        assert key.expression is None

    def test_hash_includes_expression(self):
        """Test that hash changes with different expressions"""
        key1 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            expression="ts_mean(close, 20)",
        )

        key2 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            expression="ts_mean(close, 50)",
        )

        key3 = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )

        # Different expressions should produce different hashes
        assert key1.to_hash() != key2.to_hash()
        assert key1.to_hash() != key3.to_hash()

    def test_to_dict_includes_expression(self):
        """Test that to_dict includes expression"""
        key = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            expression="EMA(close, 50)",
        )

        data = key.to_dict()
        assert "expression" in data
        assert data["expression"] == "EMA(close, 50)"

    def test_from_dict_with_expression(self):
        """Test creating CacheKey from dict with expression"""
        data = {
            "symbol": "BTC-USDT",
            "timeframe": "1h",
            "start_time": "2024-01-01T00:00:00",
            "end_time": "2024-12-31T23:59:59",
            "fields": ["close"],
            "expression": "RSI(close, 14)",
        }

        key = CacheKey.from_dict(data)
        assert key.expression == "RSI(close, 14)"
        assert key.symbol == "BTC-USDT"

    def test_from_dict_without_expression(self):
        """Test creating CacheKey from dict without expression (backward compatible)"""
        data = {
            "symbol": "BTC-USDT",
            "timeframe": "1h",
            "start_time": "2024-01-01T00:00:00",
            "end_time": "2024-12-31T23:59:59",
            "fields": ["close"],
        }

        key = CacheKey.from_dict(data)
        assert key.expression is None

    def test_expression_cache_use_case(self):
        """Test typical expression cache use case"""
        # Raw data cache key
        raw_key = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )

        # EMA calculation cache key
        ema_key = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            fields=["close"],
            expression="EMA(close, 20)",
        )

        # RSI calculation cache key
        rsi_key = CacheKey(
            symbol="BTC-USDT",
            timeframe="1h",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            fields=["close"],
            expression="RSI(close, 14)",
        )

        # All should have different hashes
        assert raw_key.to_hash() != ema_key.to_hash()
        assert raw_key.to_hash() != rsi_key.to_hash()
        assert ema_key.to_hash() != rsi_key.to_hash()

    def test_round_trip_with_expression(self):
        """Test round-trip conversion with expression"""
        original = CacheKey(
            symbol="ETH-USDT",
            timeframe="4h",
            start_time=datetime(2024, 6, 1),
            end_time=datetime(2024, 12, 31),
            fields=["open", "high", "low", "close"],
            expression="MACD(close, 12, 26, 9)",
        )

        # Convert to dict and back
        data = original.to_dict()
        restored = CacheKey.from_dict(data)

        # Should be identical
        assert restored.symbol == original.symbol
        assert restored.timeframe == original.timeframe
        assert restored.start_time == original.start_time
        assert restored.end_time == original.end_time
        assert restored.fields == original.fields
        assert restored.expression == original.expression
        assert restored.to_hash() == original.to_hash()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
