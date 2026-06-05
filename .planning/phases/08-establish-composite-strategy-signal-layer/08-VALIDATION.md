---
phase: 08
slug: establish-composite-strategy-signal-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for Composite Strategy Signal Layer planning and execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py agent/tests/strategies/test_composite_trend_strategy.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest agent/tests/strategies -q` |
| **Estimated runtime** | ~1-5 seconds for focused strategy tests |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py agent/tests/strategies/test_composite_trend_strategy.py -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest agent/tests/strategies -q`
- **Before `/gsd:verify-work`:** Focused composite tests and existing strategy adapter tests must be green
- **Max feedback latency:** ~5 seconds for focused tests

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | PH08-CONTRACT: `TradingSignal` exposes direction/status/readiness/score/confidence/components/reasons/warnings/source_results/metadata and serializes via `to_dict()` | T-08-01 | No sensitive data in signal payload | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | PH08-CLAMP: Non-finite/out-of-range `signal_score` and `confidence` clamp to public ranges | T-08-02 | Non-finite numeric poisoning is normalized | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | PH08-DEFER-EXEC: Composite direction remains `BULL / BEAR / NEUTRAL`; `LONG / SHORT / WAIT` are not top-level direction values | T-08-03 | Prevent semantic spoofing between research signal and execution action | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | PH08-MAP: Source `TrendResult` status/readiness maps into separate `TradingSignal.status` and `TradingSignal.readiness` | T-08-04 | Invalid source evidence cannot masquerade as a valid tradable signal | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_trend_strategy.py -q` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | PH08-SERIAL: `source_results` stores serializable source summaries, not raw analyzers/DataFrames | T-08-05 | Prevent heavy object leakage and non-serializable payloads | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_trend_strategy.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `agent/tests/strategies/test_composite_signal_base.py` — stubs for PH08-CONTRACT, PH08-CLAMP, PH08-DEFER-EXEC
- [ ] `agent/tests/strategies/test_composite_trend_strategy.py` — stubs for PH08-MAP and PH08-SERIAL
- [ ] `agent/src/strategies/composite/base.py` — public signal contract module
- [ ] `agent/src/strategies/composite/trend_composite.py` — minimal trend-result composer module

---

## Manual-Only Verifications

All phase behaviors should have automated verification in focused pytest tests.

---

## Threat Model

| Threat Ref | Pattern | Risk | Mitigation | Verification |
|------------|---------|------|------------|--------------|
| T-08-01 | Sensitive or heavy internal data included in signal payload | Information disclosure / oversized artifacts | Only serialize source summaries via `to_dict()`; do not store raw DataFrames/analyzers in required public fields | `PH08-SERIAL` tests |
| T-08-02 | NaN/inf or out-of-range score/confidence propagates downstream | Numeric poisoning / unstable consumers | Clamp non-finite values to safe defaults and bound public ranges | `PH08-CLAMP` tests |
| T-08-03 | Direction field uses execution action (`LONG/SHORT/WAIT`) instead of research direction | Semantic spoofing between signal and order layer | Type/test public direction as `BULL/BEAR/NEUTRAL`; defer execution action mapping | `PH08-DEFER-EXEC` tests |
| T-08-04 | Invalid source evidence becomes a valid composite signal | False-positive trading signal | Preserve technical `status` and map readiness separately; invalid-only evidence should block or invalidate composite output | `PH08-MAP` tests |
| T-08-05 | Source strategy exception breaks composite output | Denial of Service | Use source adapters' normalized `TrendResult` outputs and convert unhandled source errors to invalid composite state | `PH08-MAP` tests |

---

## Validation Sign-Off

- [ ] All tasks have automated verification or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s for focused checks
- [ ] `nyquist_compliant: true` set after implementation tests pass

**Approval:** pending
