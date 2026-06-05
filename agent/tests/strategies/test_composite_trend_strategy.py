"""Tests for CompositeTrendStrategy in composite signal layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
import pytest

from src.strategies.composite.base import TradingSignal
from src.strategies.composite.trend_composite import CompositeTrendConfig, CompositeTrendStrategy
from src.strategies.trend.base import TrendDirection, TrendResult, TrendStatus


def make_ohlcv(length: int = 20) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame for testing."""
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series(range(100, 100 + length), index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        }
    )


class FakeTrendStrategy:
    """Fake TrendStrategyBase for deterministic testing."""

    def __init__(
        self,
        name: str,
        direction: TrendDirection = "BULL",
        confidence: float = 0.7,
        signed_score: float = 60.0,
        status: TrendStatus = "VALID",
        readiness: str = "READY",
    ) -> None:
        self.name = name
        self._direction = direction
        self._confidence = confidence
        self._signed_score = signed_score
        self._status = status
        self._readiness = readiness
        self.call_count = 0
        self.last_df = None

    def analyze(self, df: pd.DataFrame) -> TrendResult:
        self.call_count += 1
        self.last_df = df
        return TrendResult(
            direction=self._direction,
            confidence=self._confidence,
            signed_score=self._signed_score,
            status=self._status,
            readiness=self._readiness,
            components={self.name: self._signed_score},
            warnings=[],
            metadata={"strategy": self.name},
        )


class FailingTrendStrategy:
    """Fake strategy that raises an exception."""

    name = "failing_strategy"

    def analyze(self, df: pd.DataFrame) -> TrendResult:
        raise RuntimeError("Strategy failed unexpectedly")


class TestCompositeTrendStrategyBasics:
    """Test basic CompositeTrendStrategy behavior."""

    def test_analyze_calls_each_source_once(self) -> None:
        """analyze() calls each injected source.analyze(df) exactly once."""
        source1 = FakeTrendStrategy("source1")
        source2 = FakeTrendStrategy("source2")
        composite = CompositeTrendStrategy(sources=[source1, source2])
        df = make_ohlcv()

        composite.analyze(df)

        assert source1.call_count == 1
        assert source2.call_count == 1

    def test_analyze_calls_each_source_with_same_df(self) -> None:
        """analyze() passes the same df to all sources."""
        source1 = FakeTrendStrategy("source1")
        source2 = FakeTrendStrategy("source2")
        composite = CompositeTrendStrategy(sources=[source1, source2])
        df = make_ohlcv()

        composite.analyze(df)

        assert source1.last_df is df
        assert source2.last_df is df


class TestStatusMapping:
    """Test TrendResult status -> TradingSignal status mapping."""

    def test_invalid_status_maps_to_invalid(self) -> None:
        """TrendResult.status=INVALID maps to TradingSignal.status=INVALID."""
        source = FakeTrendStrategy("source", status="INVALID")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "INVALID"

    def test_no_signal_status_maps_to_no_signal(self) -> None:
        """TrendResult.status=NO_SIGNAL maps to TradingSignal.status=NO_SIGNAL."""
        source = FakeTrendStrategy("source", status="NO_SIGNAL")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "NO_SIGNAL"

    def test_valid_status_maps_to_valid(self) -> None:
        """TrendResult.status=VALID maps to TradingSignal.status=VALID."""
        source = FakeTrendStrategy("source", status="VALID")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "VALID"

    def test_filtered_status_maps_to_filtered(self) -> None:
        """TrendResult.status=FILTERED maps to TradingSignal.status=FILTERED."""
        source = FakeTrendStrategy("source", status="FILTERED")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "FILTERED"

    def test_any_invalid_overrides_valid(self) -> None:
        """If any source is INVALID, overall status is INVALID."""
        valid_source = FakeTrendStrategy("valid", status="VALID")
        invalid_source = FakeTrendStrategy("invalid", status="INVALID")
        composite = CompositeTrendStrategy(sources=[valid_source, invalid_source])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "INVALID"

    def test_any_filtered_overrides_valid(self) -> None:
        """If any source is FILTERED (and none INVALID), overall status is FILTERED."""
        valid_source = FakeTrendStrategy("valid", status="VALID")
        filtered_source = FakeTrendStrategy("filtered", status="FILTERED")
        composite = CompositeTrendStrategy(sources=[valid_source, filtered_source])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "FILTERED"


class TestReadinessMapping:
    """Test TrendResult readiness -> TradingSignal readiness mapping."""

    def test_not_ready_maps_to_wait(self) -> None:
        """TrendResult.readiness=NOT_READY maps to TradingSignal.readiness=WAIT."""
        source = FakeTrendStrategy("source", readiness="NOT_READY")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.readiness == "WAIT"

    def test_ready_maps_to_ready(self) -> None:
        """TrendResult.readiness=READY maps to TradingSignal.readiness=READY."""
        source = FakeTrendStrategy("source", readiness="READY")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.readiness == "READY"

    def test_exhausted_maps_to_exhausted(self) -> None:
        """TrendResult.readiness=EXHAUSTED maps to TradingSignal.readiness=EXHAUSTED."""
        source = FakeTrendStrategy("source", readiness="EXHAUSTED")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.readiness == "EXHAUSTED"

    def test_unknown_maps_to_unknown(self) -> None:
        """TrendResult.readiness=UNKNOWN maps to TradingSignal.readiness=UNKNOWN."""
        source = FakeTrendStrategy("source", readiness="UNKNOWN")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert signal.readiness == "UNKNOWN"


class TestSourceResults:
    """Test source_results storage."""

    def test_source_results_stores_to_dict(self) -> None:
        """source_results stores TrendResult.to_dict() summaries, not raw objects."""
        source = FakeTrendStrategy("mtes_v3")
        composite = CompositeTrendStrategy(sources=[source])

        signal = composite.analyze(make_ohlcv())

        assert "mtes_v3" in signal.source_results
        result = signal.source_results["mtes_v3"]
        # Verify it's a dict (from to_dict()), not a TrendResult object
        assert isinstance(result, dict)
        assert result["direction"] == "BULL"
        assert result["status"] == "VALID"
        assert "TrendResult" not in type(result).__name__

    def test_components_maps_source_name_to_score(self) -> None:
        """components dict maps source name to source signed_score."""
        source1 = FakeTrendStrategy("mtes_v3", signed_score=75.0)
        source2 = FakeTrendStrategy("supertrend", signed_score=65.0)
        composite = CompositeTrendStrategy(sources=[source1, source2])

        signal = composite.analyze(make_ohlcv())

        assert signal.components["mtes_v3"] == 75.0
        assert signal.components["supertrend"] == 65.0


class TestDirectionAggregation:
    """Test direction aggregation from sources."""

    def test_all_bull_aggregates_to_bull(self) -> None:
        """All sources BULL -> overall direction BULL."""
        source1 = FakeTrendStrategy("s1", direction="BULL")
        source2 = FakeTrendStrategy("s2", direction="BULL")
        composite = CompositeTrendStrategy(sources=[source1, source2])

        signal = composite.analyze(make_ohlcv())

        assert signal.direction == "BULL"

    def test_all_bear_aggregates_to_bear(self) -> None:
        """All sources BEAR -> overall direction BEAR."""
        source1 = FakeTrendStrategy("s1", direction="BEAR")
        source2 = FakeTrendStrategy("s2", direction="BEAR")
        composite = CompositeTrendStrategy(sources=[source1, source2])

        signal = composite.analyze(make_ohlcv())

        assert signal.direction == "BEAR"

    def test_mixed_directions_aggregate_to_neutral(self) -> None:
        """Mixed BULL/BEAR -> overall direction NEUTRAL."""
        source1 = FakeTrendStrategy("s1", direction="BULL")
        source2 = FakeTrendStrategy("s2", direction="BEAR")
        composite = CompositeTrendStrategy(sources=[source1, source2])

        signal = composite.analyze(make_ohlcv())

        assert signal.direction == "NEUTRAL"


class TestScoreAggregation:
    """Test score and confidence aggregation."""

    def test_signal_score_aggregates_mean(self) -> None:
        """signal_score aggregates from source signed_scores via mean."""
        source1 = FakeTrendStrategy("s1", signed_score=80.0)
        source2 = FakeTrendStrategy("s2", signed_score=60.0)
        composite = CompositeTrendStrategy(sources=[source1, source2])

        signal = composite.analyze(make_ohlcv())

        assert signal.signal_score == 70.0  # mean of 80 and 60

    def test_confidence_aggregates_mean(self) -> None:
        """confidence aggregates from source confidences via mean."""
        source1 = FakeTrendStrategy("s1", confidence=0.8)
        source2 = FakeTrendStrategy("s2", confidence=0.6)
        composite = CompositeTrendStrategy(sources=[source1, source2])

        signal = composite.analyze(make_ohlcv())

        assert signal.confidence == 0.7  # mean of 0.8 and 0.6


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dataframe_returns_invalid(self) -> None:
        """analyze() with empty dataframe returns status=INVALID."""
        source = FakeTrendStrategy("source")
        composite = CompositeTrendStrategy(sources=[source])
        empty_df = pd.DataFrame()

        signal = composite.analyze(empty_df)

        assert signal.status == "INVALID"

    def test_missing_columns_returns_invalid(self) -> None:
        """analyze() with missing OHLC columns returns status=INVALID."""
        source = FakeTrendStrategy("source")
        composite = CompositeTrendStrategy(sources=[source])
        bad_df = pd.DataFrame({"close": [100, 101, 102]})

        signal = composite.analyze(bad_df)

        assert signal.status == "INVALID"

    def test_source_exception_returns_invalid_with_warning(self) -> None:
        """Source exception returns status=INVALID and captures warning."""
        failing = FailingTrendStrategy()
        composite = CompositeTrendStrategy(sources=[failing])

        signal = composite.analyze(make_ohlcv())

        assert signal.status == "INVALID"
        assert len(signal.warnings) > 0
        assert any("failed" in w.lower() or "error" in w.lower() for w in signal.warnings)


class TestConfig:
    """Test CompositeTrendConfig."""

    def test_default_name(self) -> None:
        """CompositeTrendConfig has sensible defaults."""
        config = CompositeTrendConfig()
        assert config.name == "composite_trend"

    def test_custom_name(self) -> None:
        """CompositeTrendConfig accepts custom name."""
        config = CompositeTrendConfig(name="my_composite")
        assert config.name == "my_composite"
