"""Integration tests for MTES v3 full system."""
import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3 import MTESv3, MTESv3Config


@pytest.fixture
def bull_trend_df():
    """创建牛市趋势数据"""
    dates = pd.date_range('2024-01-01', periods=300, freq='D')
    np.random.seed(42)

    # 强趋势上涨
    close = 100 + np.cumsum(np.random.randn(300) * 1.5 + 0.3)
    high = close + np.random.rand(300) * 3
    low = close - np.random.rand(300) * 3

    return pd.DataFrame({
        'open': close + np.random.randn(300) * 0.5,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, 300)
    }, index=dates)


@pytest.fixture
def bear_trend_df():
    """创建熊市趋势数据"""
    dates = pd.date_range('2024-01-01', periods=300, freq='D')
    np.random.seed(43)

    # 强趋势下跌
    close = 100 + np.cumsum(np.random.randn(300) * 1.5 - 0.3)
    high = close + np.random.rand(300) * 3
    low = close - np.random.rand(300) * 3

    return pd.DataFrame({
        'open': close + np.random.randn(300) * 0.5,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, 300)
    }, index=dates)


@pytest.fixture
def range_df():
    """创建震荡数据"""
    dates = pd.date_range('2024-01-01', periods=300, freq='D')
    np.random.seed(44)

    # 震荡行情
    close = 100 + np.sin(np.linspace(0, 8 * np.pi, 300)) * 10

    return pd.DataFrame({
        'open': close + np.random.randn(300) * 0.5,
        'high': close + np.random.rand(300) * 3,
        'low': close - np.random.rand(300) * 3,
        'close': close,
        'volume': np.random.randint(1000, 10000, 300)
    }, index=dates)


class TestMTESv3Integration:
    """MTES v3 完整系统集成测试"""

    def test_mtes_v3_initialization(self):
        """测试 MTES v3 初始化"""
        mtes = MTESv3()
        assert mtes.config.adx_prefilter_threshold == 20.0
        assert mtes.config.adx_strong_threshold == 30.0

    def test_mtes_v3_initialization_custom_config(self):
        """测试自定义配置初始化"""
        config = MTESv3Config(
            adx_prefilter_threshold=25.0,
            adx_strong_threshold=35.0,
            rsi_oversold=30.0,
            rsi_overbought=70.0
        )
        mtes = MTESv3(config)
        assert mtes.config.adx_prefilter_threshold == 25.0
        assert mtes.config.adx_strong_threshold == 35.0

    def test_bull_trend_analysis(self, bull_trend_df):
        """测试牛市趋势分析"""
        mtes = MTESv3()
        result = mtes.analyze(bull_trend_df)

        assert isinstance(result.passed_prefilter, bool)
        assert result.mtf_trend.direction in ["BULL", "BEAR", "NEUTRAL"]
        assert result.strength.rating in ["STRONG", "READY", "WEAK", "EXHAUSTED"]
        assert result.entry.signal in ["LONG", "SHORT", "WAIT"]
        assert -100 <= result.final_score <= 100
        assert 0 <= result.final_confidence <= 1

    def test_bear_trend_analysis(self, bear_trend_df):
        """测试熊市趋势分析"""
        mtes = MTESv3()
        result = mtes.analyze(bear_trend_df)

        assert isinstance(result.passed_prefilter, bool)
        assert result.mtf_trend.direction in ["BULL", "BEAR", "NEUTRAL"]

    def test_range_market_analysis(self, range_df):
        """测试震荡市场分析"""
        mtes = MTESv3()
        result = mtes.analyze(range_df)

        # 震荡市场可能预过滤失败或信号为 WAIT
        assert isinstance(result.passed_prefilter, bool)
        assert result.final_score <= 100
        assert result.final_score >= -100

    def test_insufficient_data(self):
        """测试数据不足"""
        mtes = MTESv3()
        df = pd.DataFrame({'close': [100, 101, 102]})
        result = mtes.analyze(df)

        # 数据不足应该预过滤失败
        assert result.passed_prefilter is False
        assert result.final_score == 0.0
        assert result.final_confidence == 0.0

    def test_batch_analysis(self, bull_trend_df, bear_trend_df, range_df):
        """测试批量分析"""
        mtes = MTESv3()
        data = {
            "BULL": bull_trend_df,
            "BEAR": bear_trend_df,
            "RANGE": range_df
        }

        results = mtes.analyze_batch(data)

        assert len(results) == 3
        assert "BULL" in results
        assert "BEAR" in results
        assert "RANGE" in results

        for symbol, result in results.items():
            assert isinstance(result.passed_prefilter, bool)

    def test_layer1_integration(self, bull_trend_df):
        """测试 Layer 1 整合"""
        mtes = MTESv3()
        result = mtes.analyze(bull_trend_df)

        # 检查 Layer 1 信号
        signals = result.mtf_trend.signals
        assert "smc" in signals
        assert "elder" in signals
        assert "ichimoku" in signals

    def test_score_calculation_consistency(self, bull_trend_df):
        """测试评分计算一致性"""
        mtes = MTESv3()

        # 多次分析同一数据应该得到相同结果
        result1 = mtes.analyze(bull_trend_df)
        result2 = mtes.analyze(bull_trend_df)

        assert result1.final_score == result2.final_score
        assert result1.final_confidence == result2.final_confidence

    def test_result_to_dict(self, bull_trend_df):
        """测试结果转换为字典"""
        mtes = MTESv3()
        result = mtes.analyze(bull_trend_df)

        # 确保 to_dict 方法存在
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "final_score" in result_dict
        assert "final_confidence" in result_dict


class TestMTESv3Config:
    """MTES v3 配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = MTESv3Config()

        assert config.adx_prefilter_threshold == 20.0
        assert config.adx_strong_threshold == 30.0
        assert config.adx_ready_threshold == 25.0
        assert config.rsi_oversold == 35.0
        assert config.rsi_overbought == 65.0

    def test_aggressive_config(self):
        """测试激进配置"""
        config = MTESv3Config(
            adx_prefilter_threshold=25.0,
            adx_strong_threshold=35.0,
            adx_ready_threshold=30.0,
            rsi_oversold=40.0,
            rsi_overbought=60.0
        )

        assert config.adx_prefilter_threshold > 20.0
        assert config.rsi_oversold > 35.0
