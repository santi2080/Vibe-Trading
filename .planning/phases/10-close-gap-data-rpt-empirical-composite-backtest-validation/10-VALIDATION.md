---
phase: 10
slug: close-gap-data-rpt-empirical-composite-backtest-validation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-07
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for empirical composite backtest evidence closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest -q agent/tests/test_composite_backtest_compare.py agent/tests/test_metrics.py agent/tests/test_watchlist_data_health.py` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | targeted: < 30s; full suite: project-dependent |

---

## Sampling Rate

- **After every task commit:** Run the targeted quick command or an equivalent narrower command for touched modules.
- **After every plan wave:** Run targeted suite covering comparison, metrics, watchlist data health, and runner security.
- **Before `/gsd:verify-work`:** Empirical artifacts must exist and targeted regression must pass.
- **Max feedback latency:** Keep targeted feedback under 60s where possible.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | DATA-01/02/03, RPT-03 | P09-D-002 / P09-T-001 | Environment/data audit does not bypass data limits or safe paths | CLI/artifact | `python scripts/check_watchlist_data.py --watchlist watchlist/us_futures_watchlist.csv --data-dir data --format json` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 1 | DATA-01/02/03 | P09-T-002 / P09-T-003 | Configs use safe YAML and fixed variants only | source/assertion | `python -m py_compile agent/backtest/composite_backtest_compare.py agent/backtest/configs/signal_engine.py` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 2 | METR-01/02/03, RPT-01/02 | P09-S-001 / P09-D-001 | Runner uses trusted engine verification, timeout, and safe run roots | integration/artifact | `PYTHONPATH=agent python -m backtest.composite_backtest_compare --config <config> --run-root <safe-run-root> --timeout-seconds 300` | ✅ | ⬜ pending |
| 10-04-01 | 04 | 3 | RPT-01/02/03, METR-01/02/03 | P09-R-001 | Final report links back to run cards/artifact hashes | artifact/assertion | Check report contains `Strategy Comparison (RPT-01)`, `Best Configuration (RPT-02)`, `Per-Source Performance (METR-03)`, `Data Quality (RPT-03)` | ✅ | ⬜ pending |
| 10-05-01 | 05 | 4 | all scoped requirements | — | Traceability states only verified/partial/blocked with artifact paths | docs/assertion | `grep -E "DATA-01|RPT-01|Phase 10" .planning/REQUIREMENTS.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Verify usable project Python environment before empirical runs.
- [ ] Confirm declared dependencies are importable or document blocker.
- [ ] Create Phase 10 artifacts directory before writing evidence.
- [ ] Run or document data-health checks before claiming DATA/RPT closure.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interpret whether unavailable 4H data closes as partial or blocked | DATA-03 / RPT-03 | Provider availability can be runtime/environment-specific | Review empirical run output and data-quality notes; mark DATA-03 as Verified, Partial, or Blocked with exact reason. |
| Confirm “main watchlist instruments” coverage is sufficient | DATA-02 | The minimum symbol set is a product judgment | Review run manifest symbol set and confirm it represents the intended futures/ETF watchlist scope. |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency target defined
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** draft 2026-06-07
