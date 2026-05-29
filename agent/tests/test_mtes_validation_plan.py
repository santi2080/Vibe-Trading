"""Document contract tests for the MTES backtest validation plan."""

from __future__ import annotations

from pathlib import Path


PLAN_PATH = Path(__file__).resolve().parents[2] / "docs" / "MTES_BACKTEST_VALIDATION_PLAN.md"

REQUIRED_BASELINES = {
    "SMA 200 direction",
    "Dual EMA",
    "EMA+ADX",
    "Donchian breakout",
    "Range Filter direction",
    "12-month momentum",
    "MACD",
}

REQUIRED_METRICS = {
    "cagr",
    "annualized return",
    "maximum drawdown",
    "sharpe",
    "calmar",
    "turnover",
    "whipsaw",
    "false-signal",
}

REQUIRED_UNIVERSES = {
    "stocks",
    "etfs",
    "futures",
    "crypto",
    "fx",
}

REQUIRED_HELPERS = {
    "run_validation",
    "monte_carlo_test",
    "bootstrap_sharpe_ci",
    "walk_forward_analysis",
}


def test_mtes_validation_plan_contract() -> None:
    """The MTES validation plan must name the required baselines and checks."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    lower = text.lower()

    found_baselines = {
        baseline for baseline in REQUIRED_BASELINES if baseline.lower() in lower
    }
    found_metrics = {metric for metric in REQUIRED_METRICS if metric in lower}
    found_universes = {universe for universe in REQUIRED_UNIVERSES if universe in lower}
    found_helpers = {helper for helper in REQUIRED_HELPERS if helper in text}

    assert PLAN_PATH.exists(), f"Missing validation plan: {PLAN_PATH}"
    assert "objective" in lower
    assert "evaluation-only" in lower or "evaluation only" in lower or "evaluation strategy" in lower
    assert "majortrendevaluationstrategy" in lower or "mtes wrapper" in lower
    assert len(found_baselines) >= 5, found_baselines
    assert len(found_metrics) >= 5, found_metrics
    assert found_universes == REQUIRED_UNIVERSES, found_universes
    assert "transaction" in lower and "cost" in lower
    assert "parameter perturbation" in lower or "parameter sensitivity" in lower
    assert "signal-delay" in lower or "signal delay" in lower
    assert "robustness" in lower
    assert "mtf no-look-ahead" in lower or "no-look-ahead" in lower
    assert found_helpers == REQUIRED_HELPERS, found_helpers
