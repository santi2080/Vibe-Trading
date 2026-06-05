---
phase: 05
slug: mtes-refactor
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-31
last_audited: 2026-06-05
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for MTES v2 Direction-Primary Scoring.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q` |
| **Full suite command** | `.venv/bin/python scripts/validate_mtes_v2.py` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q`
- **After every plan wave:** Run `.venv/bin/python scripts/validate_mtes_v2.py`
- **Before `/gsd:verify-work`:** Both commands must be green
- **Max feedback latency:** ~1 second for focused checks

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | `MajorTrendConfig` supports v2 scoring switch and compatible result contract | — | N/A | unit | `.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ✅ green |
| 05-01-02 | 01 | 1 | `MajorTrendResult` exposes `direction_signal`, `direction_confidence`, `strength_score`, `strength_components` | — | N/A | unit | `.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ✅ green |
| 05-01-03 | 01 | 1 | v1/v2 compatibility path remains available through `MajorTrendConfig(use_v2_scoring=False)` and `to_v1_dict()` | — | N/A | validation script | `.venv/bin/python scripts/validate_mtes_v2.py` | ✅ | ✅ green |
| 05-01-04 | 01 | 1 | Direction signal is signed and ranges `-100 ~ +100`; direction confidence ranges `0.0 ~ 1.0` | — | N/A | validation script | `.venv/bin/python scripts/validate_mtes_v2.py` | ✅ | ✅ green |
| 05-01-05 | 01 | 1 | Strength score ranges `0 ~ 100` and strength component weights sum to 1.0 per asset class | — | N/A | validation script | `.venv/bin/python scripts/validate_mtes_v2.py` | ✅ | ✅ green |
| 05-01-06 | 01 | 1 | Final `trend_score` ranges `-100 ~ +100` and direction is independent from score magnitude | — | N/A | validation script | `.venv/bin/python scripts/validate_mtes_v2.py` | ✅ | ✅ green |
| 05-01-07 | 01 | 1 | `BULL_STRONG` / `BEAR_STRONG` classification requires both signed score threshold and strength confirmation | — | N/A | unit | `.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ✅ green |
| 05-01-08 | 01 | 1 | Focused evaluator regression suite remains green for MTES existing contracts | — | N/A | unit | `.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Evidence

### 2026-06-05 Focused Unit Suite

```bash
.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q
```

Result:

```text
15 passed in 0.35s
```

### 2026-06-05 MTES v2 Validation Script

```bash
.venv/bin/python scripts/validate_mtes_v2.py
```

Result:

```text
总计: 7/7 通过
所有验证通过！MTES v2 评分体系符合规格要求。
```

---

## Validation Audit 2026-06-05

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

### Gap Resolved

- **Issue:** `weak_bull` fixture passed direction checks but was classified as `BULL_STRONG`, contradicting the phase goal that strength metrics should confirm trend quality.
- **Resolution:** `classify_trend_state_v2()` now accepts `strength_score` and requires `strength_score >= 50.0` for STRONG states. Added unit coverage for both BULL and BEAR strong-confirmation boundaries.

---

## Validation Sign-Off

- [x] All tasks have automated verification
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s for focused checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-05
