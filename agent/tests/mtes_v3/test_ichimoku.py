"""Tests for Ichimoku Cloud."""
import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.layer1.ichimoku import IchimokuCloud, IchimokuSignal


@pytest.fixture
def sample_df():
    """创建样本数据 - 需要更多数据点以满足 Ichimoku 要求"""
    dates = pd.date_range('2024-01-01', periods=200, freq='D')
    np.random.seed(42)

    # 创建一个有明显趋势的数据
    close = 100 + np.cumsum(np.random.randn(200) * 0.5)
    close = np.maximum(close, 80)

    high = close + np.random.rand(200) * 2
    low = close - np.random.rand(200) * 2
    open_price = close + np.random.randn(200) * 0.3

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, 200)
    }, index=dates)


class TestIchimokuCloud:
    """Ichimoku 云图测试"""

    def test_initialization(self):
        """测试初始化"""
        ichimoku = IchimokuCloud()
        assert ichimoku.tenkan_period == 9
        assert ichimoku.kijun_period == 26
        assert ichimoku.senkou_b_period == 52
        assert ichimoku.displacement == 26

    def test_validate_insufficient_data(self):
        """测试数据不足验证"""
        ichimoku = IchimokuCloud()
        df = pd.DataFrame({'close': [1, 2, 3]})
        assert ichimoku.validate(df) is False

    def test_validate_sufficient_data(self, sample_df):
        """测试数据充足验证"""
        ichimoku = IchimokuCloud()
        assert ichimoku.validate(sample_df) is True

    def test_calculate_tenkan(self, sample_df):
        """测试转换线计算"""
        ichimoku = IchimokuCloud()
        tenkan = ichimoku.calculate_tenkan(sample_df)

        assert len(tenkan) == len(sample_df)

    def test_calculate_kijun(self, sample_df):
        """测试基准线计算"""
        ichimoku = IchimokuCloud()
        kijun = ichimoku.calculate_kijun(sample_df)

        assert len(kijun) == len(sample_df)

    def test_calculate_senkou_a(self, sample_df):
        """测试先行跨带 A 计算"""
        ichimoku = IchimokuCloud()
        senkou_a = ichimoku.calculate_senkou_a(sample_df)

        assert len(senkou_a) == len(sample_df)
        # 应该有位移，所以前面的值是 NaN
        assert pd.isna(senkou_a.iloc[0])

    def test_calculate_senkou_b(self, sample_df):
        """测试先行跨带 B 计算"""
        ichimoku = IchimokuCloud()
        senkou_b = ichimoku.calculate_senkou_b(sample_df)

        assert len(senkou_b) == len(sample_df)
        assert pd.isna(senkou_b.iloc[0])

    def test_analyze_returns_ichimoku_signal(self, sample_df):
        """测试 analyze 返回 IchimokuSignal"""
        ichimoku = IchimokuCloud()
        result = ichimoku.analyze(sample_df)

        assert isinstance(result, IchimokuSignal)
        assert result.trend in ["BULL", "BEAR", "NEUTRAL"]
        assert isinstance(result.confidence, float)
        assert 0 <= result.confidence <= 1

    def test_analyze_with_insufficient_data(self):
        """测试数据不足时的分析"""
        ichimoku = IchimokuCloud()
        df = pd.DataFrame({'close': [1, 2, 3]})
        result = ichimoku.analyze(df)

        assert result.trend == "NEUTRAL"
        assert result.confidence == 0.0
