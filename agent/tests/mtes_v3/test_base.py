"""Tests for MTES v3 base classes."""

import pytest
import pandas as pd
import numpy as np
from agent.src.analysis.mtes_v3.base import (
    TrendBias,
    StrengthRatingResult,
    EntrySignal,
    MTESv3Result,
    BaseLayer,
)


class TestTrendBias:
    """Tests for TrendBias dataclass."""

    def test_creation(self):
        """Test TrendBias creation."""
        bias = TrendBias(
            direction="BULL",
            confidence=0.8,
            signals={"bos_confirmed": True}
        )
        assert bias.direction == "BULL"
        assert bias.confidence == 0.8
        assert bias.signals["bos_confirmed"] is True

    def test_to_dict(self):
        """Test TrendBias.to_dict()."""
        bias = TrendBias(
            direction="BEAR",
            confidence=0.7,
            signals={"mss_confirmed": False}
        )
        result = bias.to_dict()
        assert result["direction"] == "BEAR"
        assert result["confidence"] == 0.7
        assert result["signals"]["mss_confirmed"] is False


class TestStrengthRatingResult:
    """Tests for StrengthRatingResult dataclass."""

    def test_creation(self):
        """Test StrengthRatingResult creation."""
        result = StrengthRatingResult(
            rating="STRONG",
            adx_value=35.5,
            divergence=False,
            regime="TRENDING"
        )
        assert result.rating == "STRONG"
        assert result.adx_value == 35.5
        assert result.divergence is False
        assert result.regime == "TRENDING"

    def test_to_dict(self):
        """Test StrengthRatingResult.to_dict()."""
        result = StrengthRatingResult(
            rating="READY",
            adx_value=27.0,
            divergence=True,
            regime="TRENDING"
        )
        data = result.to_dict()
        assert data["rating"] == "READY"
        assert data["adx_value"] == 27.0
        assert data["divergence"] is True


class TestEntrySignal:
    """Tests for EntrySignal dataclass."""

    def test_creation(self):
        """Test EntrySignal creation."""
        signal = EntrySignal(
            signal="LONG",
            entry_price=100.5,
            stop_loss=98.0,
            reason="Strong bull trend"
        )
        assert signal.signal == "LONG"
        assert signal.entry_price == 100.5
        assert signal.stop_loss == 98.0
        assert signal.reason == "Strong bull trend"

    def test_wait_signal(self):
        """Test WAIT signal without prices."""
        signal = EntrySignal(signal="WAIT", reason="Insufficient data")
        assert signal.signal == "WAIT"
        assert signal.entry_price is None
        assert signal.stop_loss is None


class TestMTESv3Result:
    """Tests for MTESv3Result dataclass."""

    def test_creation(self):
        """Test MTESv3Result creation."""
        result = MTESv3Result(
            passed_prefilter=True,
            mtf_trend=TrendBias("BULL", 0.8, {}),
            strength=StrengthRatingResult("STRONG", 35.0),
            entry=EntrySignal("LONG"),
            final_score=75.0,
            final_confidence=0.85
        )
        assert result.passed_prefilter is True
        assert result.mtf_trend.direction == "BULL"
        assert result.final_score == 75.0

    def test_to_dict(self):
        """Test MTESv3Result.to_dict()."""
        result = MTESv3Result(
            passed_prefilter=True,
            mtf_trend=TrendBias("BEAR", 0.6, {}),
            strength=StrengthRatingResult("READY", 27.0),
            entry=EntrySignal("SHORT"),
            final_score=-50.0,
            final_confidence=0.7
        )
        data = result.to_dict()
        assert data["passed_prefilter"] is True
        assert data["final_score"] == -50.0
        assert data["mtf_trend"]["direction"] == "BEAR"


class TestBaseLayer:
    """Tests for BaseLayer abstract class."""

    def test_base_layer_cannot_be_instantiated(self):
        """Test that BaseLayer cannot be directly instantiated."""
        with pytest.raises(TypeError):
            BaseLayer()

    def test_subclass_must_implement_methods(self):
        """Test that subclasses must implement abstract methods."""

        class IncompleteLayer(BaseLayer):
            pass

        with pytest.raises(TypeError):
            IncompleteLayer()

        class CompleteLayer(BaseLayer):
            def analyze(self, df: pd.DataFrame, **kwargs):
                return {}

            def validate(self, df: pd.DataFrame) -> bool:
                return True

        # Should not raise
        layer = CompleteLayer()
        assert layer.get_name() == "CompleteLayer"
