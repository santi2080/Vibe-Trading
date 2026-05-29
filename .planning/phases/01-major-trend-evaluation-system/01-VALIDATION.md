---
phase: 01
slug: major-trend-evaluation-system
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-29
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py -q` |
| **Full suite command** | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q` |
| **Estimated runtime** | ~5 seconds focused; full `agent/tests` currently has a known collection error outside MTES |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py -q` for evaluator changes, or the plan-specific command below.
- **After every plan wave:** Run `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q`.
- **Before `/gsd:verify-work`:** Focused MTES suite must be green; document the existing unrelated full-suite collection error if still present.
- **Max feedback latency:** 10 seconds for focused MTES tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01-01 | 1 | SPEC-1, SPEC-3 | — | N/A | unit | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ⬜ pending |
| 01-01-02 | 01-01 | 1 | SPEC-2, SPEC-4, SPEC-5, SPEC-6 | — | N/A | unit | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ⬜ pending |
| 01-01-03 | 01-01 | 1 | SPEC-1, SPEC-2, SPEC-5, SPEC-6, SPEC-7 | — | N/A | unit | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ⬜ pending |
| 01-02-01 | 01-02 | 2 | SPEC-7, SPEC-9 | — | N/A | unit/integration | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-02-02 | 01-02 | 2 | SPEC-3, SPEC-9 | — | N/A | unit/integration | `.venv/bin/python3 -m pytest agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-02-03 | 01-02 | 2 | SPEC-9 | — | N/A | integration | `.venv/bin/python3 -m pytest agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-03-01 | 01-03 | 2 | SPEC-8 | — | N/A | integration | `.venv/bin/python3 -m pytest agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-03-02 | 01-03 | 2 | SPEC-8 | — | N/A | integration | `.venv/bin/python3 -m pytest agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-03-03 | 01-03 | 2 | SPEC-8 | — | N/A | integration | `.venv/bin/python3 -m pytest agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-04-01 | 01-04 | 3 | SPEC-9 | — | N/A | document/source | `test -f .planning/phases/01-major-trend-evaluation-system/01-BACKTEST-VALIDATION.md` | ❌ W0 | ⬜ pending |
| 01-04-02 | 01-04 | 3 | SPEC-1..SPEC-9 | — | N/A | integration | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |
| 01-04-03 | 01-04 | 3 | SPEC-1..SPEC-9 | — | N/A | CLI/source | `.venv/bin/python3 -m pytest agent/tests/test_major_trend_evaluator.py agent/tests/test_strategy_watchlist_tools.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing focused test infrastructure covers evaluator and strategy/tool integration. Plan 01-04 must create `01-BACKTEST-VALIDATION.md` as its validation-plan artifact.

---

## Manual-Only Verifications

All phase behaviors have automated focused verification. Manual review is limited to confirming `01-BACKTEST-VALIDATION.md` names at least five baselines, five validation metrics, supported universes, transaction cost assumptions, parameter perturbation checks, and signal-delay robustness checks.

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references except the validation-plan artifact created by Plan 01-04
- [x] No watch-mode flags
- [x] Feedback latency < 10s for focused MTES tests
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
