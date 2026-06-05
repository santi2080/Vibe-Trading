"""Tests for TradingSignal contract in composite signal layer."""

from __future__ import annotations

import math
from typing import Any, Literal

import pytest

from src.strategies.composite.base import (
    SignalDirection,
    SignalReadiness,
    SignalStatus,
    TradingSignal,
    clamp_signal_confidence,
    clamp_signal_score,
    map_trend_readiness,
)
from src.strategies.trend.base import Readiness


class TestTradingSignalBasics:
    """Test basic TradingSignal creation and methods."""

    def test_valid_signal_creation(self) -> None:
        """TradingSignal with valid fields serializes via to_dict()."""
        signal = TradingSignal(
            direction="BULL",
            status="VALID",
            readiness="READY",
            signal_score=75.0,
            confidence=0.8,
            components={"mtes_v3": 80.0, "supertrend": 70.0},
            reasons=["MTES v3 BULL confirmation", "SuperTrend confirms"],
            warnings=["overbought zone"],
            source_results={"mtes_v3": {"direction": "BULL"}, "supertrend": {"direction": "BULL"}},
            metadata={"symbol": "AAPL"},
        )
        d = signal.to_dict()
        assert d["direction"] == "BULL"
        assert d["status"] == "VALID"
        assert d["readiness"] == "READY"
        assert d["signal_score"] == 75.0
        assert d["confidence"] == 0.8
        assert d["components"] == {"mtes_v3": 80.0, "supertrend": 70.0}
        assert len(d["reasons"]) == 2
        assert len(d["warnings"]) == 1
        assert d["source_results"]["mtes_v3"]["direction"] == "BULL"
        assert d["metadata"]["symbol"] == "AAPL"

    def test_direction_accepts_only_bull_bear_neutral(self) -> None:
        """direction accepts only BULL/BEAR/NEUTRAL (not LONG/SHORT/WAIT)."""
        # Valid directions
        TradingSignal(direction="BULL", status="VALID", readiness="READY")
        TradingSignal(direction="BEAR", status="VALID", readiness="READY")
        TradingSignal(direction="NEUTRAL", status="VALID", readiness="READY")
        # Invalid directions - should fail type check
        with pytest.raises((ValueError, TypeError)):
            TradingSignal(direction="LONG", status="VALID", readiness="READY")
        with pytest.raises((ValueError, TypeError)):
            TradingSignal(direction="SHORT", status="VALID", readiness="READY")
        with pytest.raises((ValueError, TypeError)):
            TradingSignal(direction="WAIT", status="VALID", readiness="READY")

    def test_default_values(self) -> None:
        """TradingSignal has sensible defaults."""
        signal = TradingSignal(direction="NEUTRAL", status="NO_SIGNAL", readiness="UNKNOWN")
        assert signal.signal_score == 0.0
        assert signal.confidence == 0.0
        assert signal.components == {}
        assert signal.reasons == []
        assert signal.warnings == []
        assert signal.source_results == {}
        assert signal.metadata == {}


class TestSignalScoreClamping:
    """Test signal_score clamping behavior."""

    def test_clamp_nan_to_zero(self) -> None:
        """signal_score clamps NaN/inf to 0.0."""
        assert clamp_signal_score(float("nan")) == 0.0
        assert clamp_signal_score(float("inf")) == 0.0
        assert clamp_signal_score(float("-inf")) == 0.0

    def test_clamp_positive_overflow(self) -> None:
        """signal_score clamps values above 100 to 100."""
        assert clamp_signal_score(150.0) == 100.0
        assert clamp_signal_score(200.0) == 100.0
        assert clamp_signal_score(100.0) == 100.0

    def test_clamp_negative_overflow(self) -> None:
        """signal_score clamps values below -100 to -100."""
        assert clamp_signal_score(-150.0) == -100.0
        assert clamp_signal_score(-200.0) == -100.0
        assert clamp_signal_score(-100.0) == -100.0

    def test_clamp_within_range(self) -> None:
        """signal_score preserves values within -100..100."""
        assert clamp_signal_score(50.0) == 50.0
        assert clamp_signal_score(-50.0) == -50.0
        assert clamp_signal_score(0.0) == 0.0
        assert clamp_signal_score(100.0) == 100.0
        assert clamp_signal_score(-100.0) == -100.0


class TestConfidenceClamping:
    """Test confidence clamping behavior."""

    def test_clamp_nan_to_zero(self) -> None:
        """confidence clamps NaN/inf to 0.0."""
        assert clamp_signal_confidence(float("nan")) == 0.0
        assert clamp_signal_confidence(float("inf")) == 0.0
        assert clamp_signal_confidence(float("-inf")) == 0.0

    def test_clamp_positive_overflow(self) -> None:
        """confidence clamps values above 1 to 1."""
        assert clamp_signal_confidence(1.5) == 1.0
        assert clamp_signal_confidence(2.0) == 1.0
        assert clamp_signal_confidence(1.0) == 1.0

    def test_clamp_negative_overflow(self) -> None:
        """confidence clamps values below 0 to 0."""
        assert clamp_signal_confidence(-0.5) == 0.0
        assert clamp_signal_confidence(-1.0) == 0.0

    def test_clamp_within_range(self) -> None:
        """confidence preserves values within 0..1."""
        assert clamp_signal_confidence(0.5) == 0.5
        assert clamp_signal_confidence(0.0) == 0.0
        assert clamp_signal_confidence(1.0) == 1.0


class TestIsValid:
    """Test is_valid property."""

    def test_is_valid_true_when_status_valid(self) -> None:
        """is_valid returns True when status=VALID."""
        signal = TradingSignal(direction="BULL", status="VALID", readiness="READY")
        assert signal.is_valid is True

    def test_is_valid_false_for_no_signal(self) -> None:
        """is_valid returns False when status=NO_SIGNAL."""
        signal = TradingSignal(direction="NEUTRAL", status="NO_SIGNAL", readiness="UNKNOWN")
        assert signal.is_valid is False

    def test_is_valid_false_for_filtered(self) -> None:
        """is_valid returns False when status=FILTERED."""
        signal = TradingSignal(direction="BULL", status="FILTERED", readiness="WAIT")
        assert signal.is_valid is False

    def test_is_valid_false_for_invalid(self) -> None:
        """is_valid returns False when status=INVALID."""
        signal = TradingSignal(direction="NEUTRAL", status="INVALID", readiness="BLOCKED")
        assert signal.is_valid is False


class TestReadinessMapping:
    """Test readiness mapping from TrendResult readiness values."""

    def test_not_ready_maps_to_wait(self) -> None:
        """TrendResult NOT_READY maps to SignalReadiness WAIT."""
        assert map_trend_readiness("NOT_READY") == "WAIT"

    def test_ready_maps_to_ready(self) -> None:
        """TrendResult READY maps to SignalReadiness READY."""
        assert map_trend_readiness("READY") == "READY"

    def test_exhausted_maps_to_exhausted(self) -> None:
        """TrendResult EXHAUSTED maps to SignalReadiness EXHAUSTED."""
        assert map_trend_readiness("EXHAUSTED") == "EXHAUSTED"

    def test_unknown_maps_to_unknown(self) -> None:
        """TrendResult UNKNOWN maps to SignalReadiness UNKNOWN."""
        assert map_trend_readiness("UNKNOWN") == "UNKNOWN"
