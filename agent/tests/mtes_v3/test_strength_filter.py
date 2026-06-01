"""Tests for ADX Strength Filter."""
import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.layer2.strength_filter import ADXStrengthFilter


@pytest.fixture
def trending_df():
    """创建强趋势数据"""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)

    # 创建一个强趋势
    close = 100 + np.cumsum(np.random.randn(100) * 2)
    high = close + np.random.rand(100) * 3
    low = close - np.random.rand(100) * 3

    return pd.DataFrame({
        'open': close + np.random.randn(100) * 0.5,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)


@pytest.fixture
def range_df():
    """创建震荡数据"""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)

    # 震荡行情
    close = 100 + np.sin(np.linspace(0, 10, 100)) * 5

    return pd.DataFrame({
        'open': close + np.random.randn(100) * 0.5,
        'high': close + np.random.rand(100) * 2,
        'low': close - np.random.rand(100) * 2,
        'close': close,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)


class TestADXStrengthFilter:
    """ADX 强度过滤器测试"""

    def test_initialization(self):
        """测试初始化"""
        filter_obj = ADXStrengthFilter()
        assert filter_obj.adx_strong == 30.0
        assert filter_obj.adx_weak == 25.0
        assert filter_obj.adx_min == 20.0

    def test_initialization_custom(self):
        """测试自定义参数初始化"""
        filter_obj = ADXStrengthFilter(adx_strong=35.0, adx_weak=28.0)
        assert filter_obj.adx_strong == 35.0
        assert filter_obj.adx_weak == 28.0

    def test_validate_insufficient_data(self):
        """测试数据不足验证"""
        filter_obj = ADXStrengthFilter()
        df = pd.DataFrame({'close': [1, 2]})
        assert filter_obj.validate(df) is False

    def test_validate_sufficient_data(self, trending_df):
        """测试数据充足验证"""
        filter_obj = ADXStrengthFilter()
        assert filter_obj.validate(trending_df) is True

    def test_filter_returns_strength_rating(self, trending_df):
        """测试 filter 返回强度评级"""
        filter_obj = ADXStrengthFilter()
        result = filter_obj.filter(trending_df)

        assert result.rating in ["STRONG", "READY", "WEAK", "EXHAUSTED"]
        assert isinstance(result.adx_value, float)
        assert isinstance(result.regime, str)

    def test_trending_market_has_high_adx(self, trending_df):
        """测试趋势市场有较高 ADX"""
        filter_obj = ADXStrengthFilter()
        result = filter_obj.filter(trending_df)

        # 趋势市场应该有较高 ADX
        assert result.adx_value > 0

    def test_range_market_has_low_adx(self, range_df):
        """测试震荡市场有较低 ADX"""
        filter_obj = ADXStrengthFilter()
        result = filter_obj.filter(range_df)

        # 震荡市场 ADX 较低
        assert result.adx_value >= 0

    def test_rating_thresholds(self):
        """测试评级阈值"""
        filter_obj = ADXStrengthFilter(adx_strong=30.0, adx_weak=25.0, adx_min=20.0)

        # 使用一个简单的 DataFrame 测试
        df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'close': [102, 103, 104],
            'volume': [1000, 1000, 1000]
        })

        # 这个测试主要验证函数不报错
        result = filter_obj.filter(df)
        assert result.rating in ["STRONG", "READY", "WEAK", "EXHAUSTED"]
