---
phase: 08
slug: establish-composite-strategy-signal-layer
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-06
updated_by: gsd-validate-phase
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for Composite Strategy Signal Layer.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py agent/tests/strategies/test_composite_trend_strategy.py -q` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | PH08-CONTRACT | TradingSignal.direction is BULL/BEAR/NEUTRAL | unit | pytest test_composite_signal_base.py | ✅ | ✅ green |
| 08-01-02 | 01 | 1 | PH08-CLAMP | signal_score clamps to -100..100 | unit | pytest test_composite_signal_base.py | ✅ | ✅ green |
| 08-01-03 | 01 | 1 | PH08-DEFER-EXEC | source_results stores serializable dict | unit | pytest test_composite_trend_strategy.py | ✅ | ✅ green |
| 08-01-04 | 01 | 1 | PH08-MAP | Invalid source maps to INVALID/BLOCKED | unit | pytest test_composite_trend_strategy.py | ✅ | ✅ green |
| 08-01-05 | 01 | 1 | PH08-SERIAL | All field validation and runtime checks | unit | pytest test_composite_signal_base.py | ✅ | ✅ green |

*Status: ✅ green = passed, ❌ red = failed, ⚠️ flaky = inconsistent*

---

## Must-Have Verification

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TradingSignal.direction is BULL/BEAR/NEUTRAL, never LONG/SHORT/WAIT | ✅ VERIFIED | Runtime validation in `test_invalid_direction_rejected` |
| 2 | TradingSignal exposes status and readiness as separate layers | ✅ VERIFIED | `TestStatusMapping` and `TestReadinessMapping` test classes |
| 3 | signal_score clamps to -100..100, confidence clamps to 0..1 | ✅ VERIFIED | `TestClamping` test class with boundary tests |
| 4 | source_results stores serializable dict summaries, never raw objects | ✅ VERIFIED | `TestSourceResults` tests verify `.to_dict()` behavior |
| 5 | Invalid source TrendResult maps to INVALID/BLOCKED | ✅ VERIFIED | `TestStatusMapping.test_invalid_status_maps_to_invalid` |

---

## Test Results

```
agent/tests/strategies/test_composite_signal_base.py  19 passed
agent/tests/strategies/test_composite_trend_strategy.py  24 passed
─────────────────────────────────────────────────────────
Total: 43 passed in 0.31s
```

---

## Wave 0 Requirements

- [x] `agent/tests/strategies/test_composite_signal_base.py` — TradingSignal contract tests (19 tests)
- [x] `agent/tests/strategies/test_composite_trend_strategy.py` — CompositeTrendStrategy tests (24 tests)
- [x] `agent/src/strategies/composite/base.py` — TradingSignal dataclass + helpers
- [x] `agent/src/strategies/composite/trend_composite.py` — CompositeTrendStrategy implementation

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | All behaviors covered by automated tests | N/A | N/A |

---

## Validation Sign-Off

- [x] All tasks have automated verification
- [x] Sampling continuity verified
- [x] Wave 0 covers all requirements
- [x] Full suite passes (43 tests)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-06

---

## Validation Audit 2026-06-06

| Metric | Count |
|--------|-------|
| Requirements | 5 |
| Resolved | 5 |
| Manual-only | 0 |
| Total tests | 43 |
| Passed | 43 |
| Failed | 0 |
