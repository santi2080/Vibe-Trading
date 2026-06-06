# Phase 09 Execution Summary

**Phase:** 09-composite-strategy-backtest  
**Executed:** 2026-06-06  
**Status:** implemented and verified

## Completed Plans

### 09-01 — Composite Backtest Signal Infrastructure

Implemented `agent/backtest/signals.py`:

- `KeyNodeSignal` dataclass for D-04 key-node signal records.
- `CompositeSignalOutput` dataclass for key nodes + per-source signal breakdowns.
- `KeyNodeSignalRecorder` for direction/readiness transition recording.
- Key-node semantics: first signal, direction change, or readiness change.

### 09-02 — CompositeBacktestSignalEngine + PositionManager

Implemented `agent/backtest/engines/composite_engine.py`:

- `PositionManager` with per-symbol 2×ATR trailing-stop state.
- `CompositeBacktestSignalEngine` that calls `CompositeTrendStrategy.analyze(df)` bar-by-bar.
- D-01 signal mapping:
  - `BULL + READY` → long target (`1.0`)
  - `BEAR + READY` → short target (`-1.0`)
  - otherwise hold existing position until D-02 trailing stop exits.
- Per-source signal collection for downstream reports.
- Optional `CompositeEngine` wrapper for direct composite execution and signal artifact writing.

### 09-03 — YAML Config + Runner Wiring + Signal Artifacts

Implemented:

- `agent/backtest/configs/composite_backtest.yaml`
  - Reference YAML for MTES v3 + Enhanced SuperTrend composite runs.
- `agent/backtest/configs/signal_engine.py`
  - Runner-compatible `SignalEngine` template.
  - Supports adjacent `run_dir/config.json` loading because `runner.py` instantiates `SignalEngine()` with no args.
  - Supports `strategy_variant`: `composite`, `mtes_only`, `supertrend_only`.
- `agent/backtest/composite_backtest_compare.py`
  - Three-way comparison orchestrator for composite vs MTES-only vs SuperTrend-only.
- `agent/backtest/engines/base.py`
  - Added optional `get_signal_output()` artifact hook so existing runner paths can write:
    - `artifacts/signals_key_nodes.csv`
    - `artifacts/signals_per_source.json`

### 09-04 — Metrics + Reporting Infrastructure

Implemented:

- `agent/backtest/reporting/composite_report.py`
  - `CompositeReportConfig`
  - `generate_composite_report()`
  - `load_single_strategy_metrics()`
  - `check_data_quality()`
- `agent/backtest/reporting/__init__.py`
- `agent/backtest/metrics.py` helpers:
  - `per_source_stats()`
  - `equity_gap_check()`

## Code Review Fixes Applied

During code-review pass, these correctness fixes were applied:

1. **Runner artifact gap fixed**
   - Problem: `python -m backtest.runner <run_dir>` would not write composite signal artifacts.
   - Fix: `BaseEngine.run_backtest()` now calls an optional `_write_signal_engine_artifacts()` hook when signal engines expose `get_signal_output()`.

2. **Single-market composite wrapper routing fixed**
   - Problem: `_build_rule_engines()` returns engine instances, not classes.
   - Fix: direct instance use in `CompositeEngine.__init__()`.

3. **Missing import fixed**
   - Problem: `Path` was referenced in `composite_engine.py` before import.
   - Fix: added `from pathlib import Path`.

4. **D-02 semantics fixed**
   - Problem: non-READY / no-signal bars originally mapped to flat immediately.
   - Fix: existing positions are held until the 2×ATR trailing stop exits or an opposite READY signal appears.

5. **Multi-market kwargs compatibility fixed**
   - Problem: existing cross-market `CompositeEngine` does not accept extra kwargs.
   - Fix: no extra kwargs are passed to that engine.

6. **METR-03 precision aligned**
   - Problem: Plan 04 smoke expectation uses `0.667` for 2/3.
   - Fix: `per_source_stats()` percentage fields use 3-decimal rounding.

## Verification Status

Verification completed successfully after switching to the project virtual environment (`.venv/bin/python`).

Validated coverage:

- YAML parsing for `agent/backtest/configs/composite_backtest.yaml`.
- Python bytecode compilation for all new/modified Phase 09 Python files.
- `KeyNodeSignalRecorder` key-node behavior:
  - emits first signal;
  - skips unchanged direction/readiness;
  - emits readiness transition.
- `PositionManager` 2×ATR trailing stop behavior.
- `CompositeBacktestSignalEngine` D-01/D-02 behavior with a deterministic stub composite.
- `per_source_stats()` and `equity_gap_check()` helpers.
- `generate_composite_report()` markdown report generation.
- Existing related regression tests.

Commands run:

```bash
.venv/bin/python -m py_compile \
  agent/backtest/signals.py \
  agent/backtest/engines/composite_engine.py \
  agent/backtest/configs/signal_engine.py \
  agent/backtest/composite_backtest_compare.py \
  agent/backtest/reporting/composite_report.py \
  agent/backtest/metrics.py \
  agent/backtest/engines/base.py
```

Result: passed.

```bash
.venv/bin/python - <<'PY'
# Phase 09 smoke validation: YAML, recorder, trailing stop,
# composite signal engine, metrics helpers, report generation.
PY
```

Result: `PHASE09_SMOKE: PASS`.

```bash
.venv/bin/python -m pytest -q \
  agent/tests/strategies/test_composite_signal_base.py \
  agent/tests/strategies/test_composite_trend_strategy.py \
  agent/tests/test_market_detection.py \
  agent/tests/test_metrics.py
```

Result: `127 passed in 0.32s`.

## Files Changed

- `agent/backtest/signals.py`
- `agent/backtest/engines/composite_engine.py`
- `agent/backtest/engines/base.py`
- `agent/backtest/configs/composite_backtest.yaml`
- `agent/backtest/configs/signal_engine.py`
- `agent/backtest/composite_backtest_compare.py`
- `agent/backtest/reporting/__init__.py`
- `agent/backtest/reporting/composite_report.py`
- `agent/backtest/metrics.py`

## Follow-up Verification Command

Run once Bash execution is available:

```bash
PY=.venv/bin/python; [ -x "$PY" ] || PY=python; "$PY" - <<'PY'
# See conversation log for full smoke command.
PY
```
