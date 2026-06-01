"""Tests for Elder Triple Screen."""
import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.layer1.elder_screen import ElderTripleScreen, ElderSignal


@pytest.fixture
def sample_df():
    """创建样本数据"""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)

    # 创建一个上涨趋势的数据
    close = 100 + np.cumsum(np.random.randn(100) * 0.5)
    close = np.maximum(close, 80)  # 确保价格不会太低

    high = close + np.random.rand(100) * 2
    low = close - np.random.rand(100) * 2
    open_price = close + np.random.randn(100) * 0.3

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)


class TestElderTripleScreen:
    """Elder 三重滤网测试"""

    def test_initialization(self):
        """测试初始化"""
        elder = ElderTripleScreen()
        assert elder.macd_fast == 12
        assert elder.macd_slow == 26
        assert elder.rsi_period == 14
        assert elder.rsi_oversold == 30
        assert elder.rsi_overbought == 70

    def test_validate_insufficient_data(self):
        """测试数据不足验证"""
        elder = ElderTripleScreen()
        df = pd.DataFrame({'close': [1, 2, 3]})
        assert elder.validate(df) is False

    def test_validate_sufficient_data(self, sample_df):
        """测试数据充足验证"""
        elder = ElderTripleScreen()
        assert elder.validate(sample_df) is True

    def test_calculate_macd(self, sample_df):
        """测试 MACD 计算"""
        elder = ElderTripleScreen()
        macd_line, signal_line, histogram = elder.calculate_macd(sample_df)

        assert len(macd_line) == len(sample_df)
        assert len(signal_line) == len(sample_df)
        assert len(histogram) == len(sample_df)

    def test_calculate_rsi(self, sample_df):
        """测试 RSI 计算"""
        elder = ElderTripleScreen()
        rsi = elder.calculate_rsi(sample_df)

        assert isinstance(rsi, float)
        assert 0 <= rsi <= 100

    def test_layer1_mtf_trend_bull(self, sample_df):
        """测试第一滤网牛市趋势"""
        elder = ElderTripleScreen()
        trend = elder.layer1_mtf_trend(sample_df)

        assert trend in ["BULL", "BEAR", "NEUTRAL"]

    def test_layer2_pullback_extremity(self, sample_df):
        """测试第二滤网极值检测"""
        elder = ElderTripleScreen()
        is_pullback = elder.layer2_pullback_extremity(sample_df, "BULL")

        assert isinstance(is_pullback, bool)

    def test_layer3_trigger(self, sample_df):
        """测试第三滤网触发器"""
        elder = ElderTripleScreen()
        trigger = elder.layer3_trigger(sample_df)

        assert trigger in ["READY", "WAIT"]

    def test_analyze_returns_elder_signal(self, sample_df):
        """测试 analyze 返回 ElderSignal"""
        elder = ElderTripleScreen()
        result = elder.analyze(sample_df)

        assert isinstance(result, ElderSignal)
        assert result.layer1_trend in ["BULL", "BEAR", "NEUTRAL"]
        assert result.layer3_trigger in ["READY", "WAIT"]
        assert isinstance(result.rsi_value, float)

    def test_analyze_with_insufficient_data(self):
        """测试数据不足时的分析"""
        elder = ElderTripleScreen()
        df = pd.DataFrame({'close': [1, 2, 3]})
        result = elder.analyze(df)

        assert result.layer1_trend == "NEUTRAL"
        assert result.layer3_trigger == "WAIT"
