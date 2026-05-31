"""Document contract tests for the SuperTrend Enhancement Validation Plan."""

from __future__ import annotations

from pathlib import Path


PLAN_PATH = Path(__file__).resolve().parents[2] / "docs" / "SUPERTREND_ENHANCEMENT_VALIDATION_PLAN.md"

# Required baselines for SuperTrend enhancement
REQUIRED_BASELINES = {
    "legacy Phase 02 SuperTrend",
    "corrected SuperTrend",
    "bridge baseline",
    "weekly SuperTrend",
    "daily RangeFilter",
}

# Required metrics for strategy validation
REQUIRED_METRICS = {
    "win rate",
    "profit factor",
    "max drawdown",
    "sharpe",
    "sortino",
    "cagr",
    "calmar",
    "trade count",
    "holding",
    "exposure",
    "whipsaw",
}

# Required evidence terms
REQUIRED_EVIDENCE = {
    "no-lookahead",
    "weekly alignment",
    "transaction cost",
    "slippage",
    "parameter sensitivity",
    "walk-forward",
    "monte carlo",
    "bootstrap",
}

# MTES conflict requirements
REQUIRED_MTES_TERMS = {
    "mtes conflict",
    "conflict metadata",
    "veto",
    "timeframe conflict",
}

# Required robustness checks
REQUIRED_ROBUSTNESS = {
    "parameter perturbation",
    "regime split",
    "out-of-sample",
    "walk-forward",
    "monte carlo",
}


def test_supertrend_validation_plan_exists() -> None:
    """Validation plan document must exist."""
    assert PLAN_PATH.exists(), f"Missing validation plan: {PLAN_PATH}"


def test_supertrend_validation_plan_objective() -> None:
    """Validation plan must have an objective."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    assert "objective" in lower, "Validation plan must include an objective section"


def test_validation_plan_baselines() -> None:
    """Validation plan must name required baselines including legacy vs corrected SuperTrend bridge."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    found = {b for b in REQUIRED_BASELINES if b.lower() in lower}
    missing = REQUIRED_BASELINES - found
    assert not missing, f"Missing required baseline terms: {missing}"


def test_validation_plan_metrics() -> None:
    """Validation plan must name all required trading metrics."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    found = {m for m in REQUIRED_METRICS if m in lower}
    missing = REQUIRED_METRICS - found
    assert not missing, f"Missing required metric terms: {missing}"


def test_validation_plan_evidence() -> None:
    """Validation plan must require no-lookahead, costs, and robustness evidence."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    found = {e for e in REQUIRED_EVIDENCE if e.lower() in lower}
    missing = REQUIRED_EVIDENCE - found
    assert not missing, f"Missing required evidence terms: {missing}"


def test_validation_plan_mtes_conflict() -> None:
    """Validation plan must require MTES conflict metadata and veto evidence."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    found = {t for t in REQUIRED_MTES_TERMS if t.lower() in lower}
    missing = REQUIRED_MTES_TERMS - found
    assert not missing, f"Missing required MTES conflict terms: {missing}"


def test_validation_plan_robustness() -> None:
    """Validation plan must require robustness checks."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    found = {r for r in REQUIRED_ROBUSTNESS if r.lower() in lower}
    missing = REQUIRED_ROBUSTNESS - found
    assert not missing, f"Missing required robustness terms: {missing}"


def test_validation_plan_bridge_baseline() -> None:
    """Validation plan must explicitly require legacy Phase 02 vs corrected SuperTrend bridge."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    has_legacy = "legacy" in lower
    has_corrected = "corrected" in lower
    has_bridge = "bridge" in lower
    assert has_legacy and has_corrected and has_bridge, (
        "Validation plan must explicitly require legacy Phase 02 vs corrected "
        "SuperTrend bridge baseline comparison"
    )
