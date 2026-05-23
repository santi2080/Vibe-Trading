"""Tests for strategy comparison tool."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.strategies.comparison import (
    StrategyComparator,
    StrategyMetrics,
    ComparisonResult,
    compare_strategies,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_metrics_1() -> StrategyMetrics:
    """Sample strategy metrics 1."""
    return StrategyMetrics(
        name="EMA_Cross",
        total_return=0.25,
        annual_return=0.12,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        calmar_ratio=0.8,
        max_drawdown=-0.15,
        max_drawdown_duration=30,
        win_rate=0.60,
        profit_factor=1.8,
        total_trades=50,
        avg_trade_return=0.005,
        avg_holding_bars=10.5,
    )


@pytest.fixture
def sample_metrics_2() -> StrategyMetrics:
    """Sample strategy metrics 2."""
    return StrategyMetrics(
        name="RSI_Mean_Rev",
        total_return=0.18,
        annual_return=0.09,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.6,
        max_drawdown=-0.20,
        max_drawdown_duration=45,
        win_rate=0.55,
        profit_factor=1.5,
        total_trades=35,
        avg_trade_return=0.004,
        avg_holding_bars=8.2,
    )


@pytest.fixture
def sample_metrics_3() -> StrategyMetrics:
    """Sample strategy metrics 3."""
    return StrategyMetrics(
        name="Breakout",
        total_return=0.30,
        annual_return=0.15,
        sharpe_ratio=1.8,
        sortino_ratio=2.3,
        calmar_ratio=1.0,
        max_drawdown=-0.12,
        max_drawdown_duration=20,
        win_rate=0.65,
        profit_factor=2.0,
        total_trades=40,
        avg_trade_return=0.007,
        avg_holding_bars=12.0,
    )


# ---------------------------------------------------------------------------
# StrategyMetrics Tests
# ---------------------------------------------------------------------------


class TestStrategyMetrics:
    """Tests for StrategyMetrics."""

    def test_metrics_creation(self, sample_metrics_1: StrategyMetrics):
        """Test metrics can be created."""
        assert sample_metrics_1.name == "EMA_Cross"
        assert sample_metrics_1.total_return == 0.25
        assert sample_metrics_1.sharpe_ratio == 1.5

    def test_metrics_to_dict(self, sample_metrics_1: StrategyMetrics):
        """Test metrics conversion to dict."""
        d = sample_metrics_1.to_dict()

        assert d["name"] == "EMA_Cross"
        assert "returns" in d
        assert "risk" in d
        assert "trades" in d
        assert d["returns"]["total"] == "25.00%"

    def test_default_values(self):
        """Test default values."""
        metrics = StrategyMetrics(name="Test")

        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.total_trades == 0


# ---------------------------------------------------------------------------
# StrategyComparator Tests
# ---------------------------------------------------------------------------


class TestStrategyComparator:
    """Tests for StrategyComparator."""

    def test_empty_comparator(self):
        """Test empty comparator."""
        comparator = StrategyComparator()
        assert len(comparator.strategies) == 0
        assert comparator.get_best() is None
        assert comparator.get_worst() is None

    def test_add_strategy(self, sample_metrics_1: StrategyMetrics):
        """Test adding a strategy."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)

        assert len(comparator.strategies) == 1
        assert comparator.strategies[0].name == "EMA_Cross"

    def test_add_from_dict(self):
        """Test adding strategy from dict."""
        comparator = StrategyComparator()
        metrics = {
            "total_return": 0.25,
            "annual_return": 0.12,
            "sharpe": 1.5,
            "sortino": 2.0,
            "calmar": 0.8,
            "max_drawdown": -0.15,
            "win_rate": 0.60,
            "profit_factor": 1.8,
            "total_trades": 50,
        }
        comparator.add_from_dict("Test_Strategy", metrics)

        assert len(comparator.strategies) == 1
        assert comparator.strategies[0].sharpe_ratio == 1.5
        assert comparator.strategies[0].win_rate == 0.60

    def test_get_best(self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics):
        """Test getting best strategy."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)
        comparator.add_strategy(sample_metrics_2)

        best = comparator.get_best("sharpe_ratio")
        assert best is not None
        assert best.name == "EMA_Cross"

    def test_get_worst(self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics):
        """Test getting worst strategy."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)
        comparator.add_strategy(sample_metrics_2)

        worst = comparator.get_worst("sharpe_ratio")
        assert worst is not None
        assert worst.name == "RSI_Mean_Rev"

    def test_filter_by_return(self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics):
        """Test filtering by return."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)  # 25% return
        comparator.add_strategy(sample_metrics_2)  # 18% return

        filtered = comparator.filter_by_return(min_return=0.20)
        assert len(filtered) == 1
        assert filtered[0].name == "EMA_Cross"

    def test_filter_by_sharpe(self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics):
        """Test filtering by Sharpe ratio."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)  # 1.5 Sharpe
        comparator.add_strategy(sample_metrics_2)  # 1.2 Sharpe

        filtered = comparator.filter_by_sharpe(min_sharpe=1.4)
        assert len(filtered) == 1
        assert filtered[0].name == "EMA_Cross"

    def test_filter_by_drawdown(self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics):
        """Test filtering by drawdown."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)  # -15% DD
        comparator.add_strategy(sample_metrics_2)  # -20% DD

        filtered = comparator.filter_by_drawdown(max_drawdown=0.18)
        assert len(filtered) == 1
        assert filtered[0].name == "EMA_Cross"

    def test_summary(self, sample_metrics_1: StrategyMetrics):
        """Test summary generation."""
        comparator = StrategyComparator()
        comparator.add_strategy(sample_metrics_1)

        summary = comparator.summary()
        assert "EMA_Cross" in summary
        assert "Sharpe Ratio" in summary


# ---------------------------------------------------------------------------
# ComparisonResult Tests
# ---------------------------------------------------------------------------


class TestComparisonResult:
    """Tests for ComparisonResult."""

    def test_comparison_creation(
        self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics
    ):
        """Test comparison result creation."""
        result = ComparisonResult(
            strategies=[sample_metrics_1, sample_metrics_2],
            ranked_by="sharpe",
        )

        assert len(result.strategies) == 2
        assert result.ranked_by == "sharpe"

    def test_get_ranking(
        self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics
    ):
        """Test getting rankings."""
        result = ComparisonResult(
            strategies=[sample_metrics_1, sample_metrics_2],
            ranked_by="sharpe",
        )

        rankings = result.get_ranking("sharpe_ratio")
        assert len(rankings) == 2
        assert rankings[0][0] == "EMA_Cross"  # Best first
        assert rankings[1][0] == "RSI_Mean_Rev"

    def test_get_winners(
        self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics
    ):
        """Test getting winners."""
        result = ComparisonResult(
            strategies=[sample_metrics_1, sample_metrics_2],
            ranked_by="sharpe",
        )

        winners = result.get_winners("sharpe_ratio")
        assert winners == ["EMA_Cross"]

    def test_to_dataframe(
        self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics
    ):
        """Test DataFrame conversion."""
        result = ComparisonResult(
            strategies=[sample_metrics_1, sample_metrics_2],
            ranked_by="sharpe",
        )

        df = result.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "Strategy" in df.columns
        assert "Sharpe" in df.columns

    def test_to_markdown(
        self, sample_metrics_1: StrategyMetrics, sample_metrics_2: StrategyMetrics
    ):
        """Test markdown generation."""
        result = ComparisonResult(
            strategies=[sample_metrics_1, sample_metrics_2],
            ranked_by="sharpe",
        )

        md = result.to_markdown()
        assert "# Strategy Comparison" in md
        assert "## Summary" in md
        assert "EMA_Cross" in md
        assert "RSI_Mean_Rev" in md


# ---------------------------------------------------------------------------
# Convenience Function Tests
# ---------------------------------------------------------------------------


class TestCompareStrategies:
    """Tests for compare_strategies convenience function."""

    def test_compare_strategies(self):
        """Test the convenience compare function."""
        strategies = [
            ("EMA", {"sharpe": 1.5, "total_return": 0.25}),
            ("RSI", {"sharpe": 1.2, "total_return": 0.18}),
        ]

        result = compare_strategies(strategies, ranked_by="sharpe")
        assert len(result.strategies) == 2

        best = result.get_winners("sharpe")[0]
        assert best == "EMA"

    def test_compare_empty(self):
        """Test comparing empty list."""
        result = compare_strategies([])
        assert len(result.strategies) == 0
