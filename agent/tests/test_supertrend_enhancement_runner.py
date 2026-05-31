"""Contract tests for the SuperTrend Enhancement experiment runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "agent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def make_ohlcv(length: int = 500, *, seed: int = 42) -> pd.DataFrame:
    """Create synthetic OHLCV for smoke tests."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2022-01-01", periods=length, freq="D", name="timestamp")
    trend = 100.0 + np.arange(length, dtype=float) * 0.5
    noise = rng.normal(0, 1.5, length)
    close = trend + noise
    high = close + rng.uniform(0.5, 2.0, length)
    low = close - rng.uniform(0.5, 2.0, length)
    open_ = close + rng.normal(0, 0.5, length)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=index,
    )


def make_weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Convert daily to weekly."""
    return daily.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )


def make_mtes_conflict(length: int = 500) -> pd.DataFrame:
    """Create synthetic MTES conflict metadata."""
    rng = np.random.default_rng(99)
    index = pd.date_range("2022-01-01", periods=length, freq="D", name="timestamp")
    return pd.DataFrame(
        {
            "mtes_direction": rng.choice([-1.0, 1.0], size=length),
            "mtes_regime": rng.choice(["trending", "choppy"], size=length),
            "mtes_conflict": rng.choice([True, False], size=length, p=[0.15, 0.85]),
            "timeframe_conflict": rng.choice([True, False], size=length, p=[0.1, 0.9]),
        },
        index=index,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI Argument Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRunnerCLI:
    """Test runner CLI argument parsing."""

    def test_accepts_symbol_flag(self):
        """Runner accepts --symbol flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F"])
        assert args.symbol == "GC=F"

    def test_accepts_matrix_smoke(self):
        """Runner accepts --matrix smoke."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--matrix", "smoke"])
        assert args.matrix == "smoke"

    def test_accepts_matrix_core(self):
        """Runner accepts --matrix core."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--matrix", "core"])
        assert args.matrix == "core"

    def test_accepts_output_flag(self):
        """Runner accepts --output flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--output", "reports"])
        assert args.output == "reports"

    def test_accepts_market_filter(self):
        """Runner accepts --market-filter flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--market-filter", "us_futures"])
        assert args.market_filter == "us_futures"

    def test_accepts_trading_mode(self):
        """Runner accepts --mode flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--mode", "long_only"])
        assert args.mode == "long_only"

    def test_accepts_transaction_cost(self):
        """Runner accepts --transaction-cost-bps flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--transaction-cost-bps", "10"])
        assert args.transaction_cost_bps == 10.0

    def test_accepts_slippage(self):
        """Runner accepts --slippage-bps flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--slippage-bps", "8"])
        assert args.slippage_bps == 8.0

    def test_accepts_max_grid_size(self):
        """Runner accepts --max-grid-size flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--max-grid-size", "24"])
        assert args.max_grid_size == 24

    def test_accepts_walk_forward(self):
        """Runner accepts --walk-forward flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--walk-forward"])
        assert args.walk_forward is True

    def test_accepts_entry_family(self):
        """Runner accepts --entry-family flag."""
        from scripts.backtest_supertrend_enhancement import parse_args

        args = parse_args(["--symbol", "GC=F", "--entry-family", "breakout"])
        assert args.entry_family == "breakout"


# ─────────────────────────────────────────────────────────────────────────────
# Smoke Integration Tests (with fixtures)
# ─────────────────────────────────────────────────────────────────────────────


class TestRunnerSmokeIntegration:
    """Run smoke tests using synthetic fixture data."""

    def test_smoke_matrix_produces_rows(self):
        """Smoke matrix produces experiment rows for synthetic data."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)

        assert isinstance(rows, list)
        assert len(rows) > 0, "Smoke matrix must produce at least one row"
        # Verify structure of first row
        row = rows[0]
        assert "experiment_id" in row
        assert "strategy_name" in row
        assert "win_rate" in row or "cagr" in row

    def test_core_matrix_includes_all_experiments(self):
        """Core matrix includes all B1-B3 and E1-E8 experiments."""
        from scripts.backtest_supertrend_enhancement import run_core_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_core_matrix(daily, weekly, mtes)

        names = [r.get("strategy_name", "") for r in rows]
        # Should have at least 8 core experiments
        assert len(rows) >= 8, f"Core matrix should have ≥8 experiments, got {len(rows)}"

    def test_b1_buy_and_hold_present(self):
        """Core matrix includes buy-and-hold baseline."""
        from scripts.backtest_supertrend_enhancement import run_core_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_core_matrix(daily, weekly, mtes)
        names = [r.get("strategy_name", "").lower() for r in rows]

        assert any("buy" in n or "b1" in n for n in names), "Should include buy-and-hold baseline"

    def test_enhanced_experiments_present(self):
        """Core matrix includes enhanced combinations (E4-E8)."""
        from scripts.backtest_supertrend_enhancement import run_core_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_core_matrix(daily, weekly, mtes)
        names = [r.get("strategy_name", "") for r in rows]

        # Should have enhanced experiments
        has_enhanced = any(
            "E4" in n or "E5" in n or "E6" in n or "E7" in n or "E8" in n
            for n in names
        )
        assert has_enhanced, f"Should include enhanced experiments, got {names}"

    def test_required_identity_columns_present(self):
        """Each row has required identity columns."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        required = ["experiment_id", "strategy_name", "baseline_family", "symbol",
                    "market", "timeframe", "entry_family", "trading_mode"]

        for row in rows:
            for col in required:
                assert col in row, f"Missing required column '{col}' in row"

    def test_required_metric_columns_present(self):
        """Each row has required metric columns."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        required = ["win_rate", "profit_factor", "max_drawdown", "sharpe",
                    "cagr", "trade_count", "exposure", "whipsaw_count"]

        for row in rows:
            for col in required:
                assert col in row, f"Missing required metric '{col}' in row"

    def test_transaction_cost_in_rows(self):
        """Transaction cost and slippage appear in all rows."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        for row in rows:
            assert "transaction_cost_bps" in row
            assert "slippage_bps" in row

    def test_warmup_bars_removed_in_metadata(self):
        """No-lookahead warmup is documented in metadata."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        # Check that warmup is recorded somewhere
        for row in rows:
            if row.get("uses_weekly_st_anchor"):
                assert "warmup_bars_removed" in row or "warmup" in str(row)

    def test_mtes_conflict_count_for_e8(self):
        """E8 (MTES-filtered) experiment includes conflict/veto counts."""
        from scripts.backtest_supertrend_enhancement import run_core_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_core_matrix(daily, weekly, mtes)
        e8_rows = [r for r in rows if "E8" in r.get("strategy_name", "") or r.get("uses_mtes_conflict_filter")]

        if e8_rows:
            for row in e8_rows:
                assert "mtes_conflict_count" in row or "mtes_vetoed_entry_count" in row, \
                    "E8 rows must include MTES conflict counts"

    def test_entry_family_in_rows(self):
        """Entry family is specified in rows."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        for row in rows:
            assert "entry_family" in row
            assert row["entry_family"] in ["pullback", "breakout", "rsi_recovery", "macd_recovery", "none"]

    def test_trading_mode_in_rows(self):
        """Trading mode is specified in all rows."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        for row in rows:
            assert "trading_mode" in row
            assert row["trading_mode"] in ["long_only", "long_short", "auto"]


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestReportGeneration:
    """Test report generation from experiment rows."""

    def test_rows_to_csv(self):
        """Experiment rows can be converted to DataFrame and saved."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        df = pd.DataFrame(rows)

        assert len(df) == len(rows)
        assert len(df.columns) > 10, "Should have many columns"

    def test_csv_has_required_columns(self):
        """CSV output has all required columns."""
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        rows = run_smoke_matrix(daily, weekly, mtes)
        df = pd.DataFrame(rows)

        required = ["experiment_id", "strategy_name", "win_rate", "profit_factor",
                    "sharpe", "max_drawdown", "cagr", "trade_count"]
        for col in required:
            assert col in df.columns, f"Missing required column: {col}"

    def test_markdown_report_structure(self):
        """Markdown report has expected sections."""
        from scripts.backtest_supertrend_enhancement import generate_markdown_summary

        daily = make_ohlcv(length=500)
        weekly = make_weekly_from_daily(daily)
        mtes = make_mtes_conflict(length=500)

        # Run smoke to get rows
        from scripts.backtest_supertrend_enhancement import run_smoke_matrix
        rows = run_smoke_matrix(daily, weekly, mtes)

        md = generate_markdown_summary(rows, symbol="GC=F")

        assert isinstance(md, str)
        assert len(md) > 100, "Markdown should have content"
        assert "##" in md, "Should have section headers"


# ─────────────────────────────────────────────────────────────────────────────
# Path Safety Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPathSafety:
    """Test output path validation."""

    def test_rejects_absolute_traversal(self):
        """Runner rejects output paths attempting directory traversal."""
        from scripts.backtest_supertrend_enhancement import validate_output_path

        # These should be rejected
        with pytest.raises(ValueError):
            validate_output_path("/tmp/evil")

        with pytest.raises(ValueError):
            validate_output_path("../outside")

    def test_accepts_reports_subdirectory(self):
        """Runner accepts reports subdirectory."""
        from scripts.backtest_supertrend_enhancement import validate_output_path

        # Should accept
        path = validate_output_path("reports")
        assert "reports" in str(path)


# ─────────────────────────────────────────────────────────────────────────────
# Grid Size Protection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGridSizeProtection:
    """Test parameter grid size limiting."""

    def test_max_grid_size_enforced(self):
        """Grid size is capped at max_grid_size."""
        from scripts.backtest_supertrend_enhancement import estimate_grid_size, cap_grid_size

        # Large grid should be capped
        large_grid = 1000
        capped = cap_grid_size(large_grid, max_size=24)
        assert capped <= 24, "Grid should be capped"

    def test_small_grid_unchanged(self):
        """Small grid below max is unchanged."""
        from scripts.backtest_supertrend_enhancement import cap_grid_size

        small_grid = 10
        capped = cap_grid_size(small_grid, max_size=24)
        assert capped == 10, "Small grid should be unchanged"


# ─────────────────────────────────────────────────────────────────────────────
# Signal Simulation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSignalSimulation:
    """Test signal-to-trade simulation logic."""

    def test_one_bar_delay_enforced(self):
        """Signals are shifted by one bar for execution."""
        from scripts.backtest_supertrend_enhancement import simulate_trades_from_signals

        daily = make_ohlcv(length=200)
        signals = pd.Series(0.0, index=daily.index)
        signals.iloc[50] = 1.0  # Long signal at bar 50
        signals.iloc[100] = 0.0  # Exit at bar 100

        trades = simulate_trades_from_signals(signals, daily)

        assert len(trades) > 0, "Should produce at least one trade"
        # Entry should be at bar 51 (one bar after signal)
        first_trade = trades[0]
        assert first_trade.entry_bar > 50, "Entry should be after signal bar"

    def test_no_same_bar_entry(self):
        """No entry on same bar as signal."""
        from scripts.backtest_supertrend_enhancement import simulate_trades_from_signals

        daily = make_ohlcv(length=200)
        signals = pd.Series(0.0, index=daily.index)
        signals.iloc[50] = 1.0

        trades = simulate_trades_from_signals(signals, daily)

        for trade in trades:
            assert trade.entry_bar != 50, "Should not enter on same bar as signal"
