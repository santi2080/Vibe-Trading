# Phase 07: Watchlist Local Data Health Gate - Validation Strategy

**Created:** 2026-06-02
**Requirement:** REQ-001

## Validation Architecture

This phase validates that the existing watchlist data-health checker is exposed and enforced through user-facing paths without duplicating checker logic.

## Required Verification Dimensions

| Dimension | Required proof |
|---|---|
| Domain checker regression | `agent/tests/test_watchlist_data_health.py` passes |
| Tool registry exposure | `check_watchlist_data` tool is registered and executable via `build_registry()` |
| JSON contract | Tool/MCP JSON includes `gate.status`, `gate.can_backtest`, `gate.blocking_failures`, `gate.warnings`, and `items` |
| Path safety | Tool rejects watchlist paths escaping `watchlist/` |
| Blocking gate | Protected downstream analysis/backtest path returns a gate failure and does not proceed when required `1d`/`1h` data fails |
| Warning-only gate | Auxiliary timeframe warning keeps `can_backtest=True` |
| Existing behavior preserved | Existing watchlist tool tests and data-health CLI tests continue to pass |

## Recommended Test Commands

```bash
.venv/bin/python -m pytest agent/tests/test_watchlist_data_health.py -q
.venv/bin/python -m pytest agent/tests/test_strategy_watchlist_tools.py -q
```

If a new integration test file is added, include it in final verification.
