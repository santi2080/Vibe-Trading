---
phase: "09"
slug: composite-strategy-backtest
status: verified
threats_open: 0
asvs_level: L1
created: 2026-06-06
register_authored_at_plan_time: false
security_gate: passed
---

# Phase 09 — Security

> Per-phase security contract: retroactive STRIDE threat register, accepted risks, and audit trail.

Phase 09 did not include a parseable PLAN-time `<threat_model>` block, so this SECURITY.md was generated in **retroactive-STRIDE mode** from implementation files and Phase 09 planning artifacts.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Run directory signal engine boundary | `runner.py` dynamically loads `run_dir/code/signal_engine.py`; Phase 09 adds a composite signal-engine template and comparison orchestration around this mechanism. | Python code from run directory crosses into the backtest process. |
| Backtest config boundary | YAML/JSON config controls instruments, date range, source, interval, strategy variant, ATR params, and output locations. | User-provided or run-dir-provided config crosses into strategy and runner execution. |
| Artifact output boundary | Backtest and composite engine write CSV/JSON/Markdown artifacts under run directories. | Strategy signals, source breakdowns, run-card metadata, and reports are serialized to disk. |
| Subprocess orchestration boundary | `composite_backtest_compare.py` launches `python -m backtest.runner` for composite, MTES-only, and SuperTrend-only variants. | Parent process delegates execution to subprocesses and captures stdout/stderr. |
| Market data volume boundary | Codes/date range/interval determine OHLCV rows, per-bar signal generation, and artifact size. | External market data and computed signals become in-memory records and output artifacts. |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation / Expected Control | Status |
|-----------|----------|-----------|----------|-------------|-------------------------------|--------|
| P09-S-001 | Spoofing / Elevation of Privilege | `backtest.runner` dynamic `signal_engine.py` loading | High | mitigate | Trusted-template SHA-256 allowlist with operator-approved extra hashes; existing AST validation remains defense-in-depth. | closed |
| P09-T-001 | Tampering | `composite_backtest_compare.py --run-root`; `CompositeEngine.run_backtest(run_dir)` | High | mitigate | `safe_run_dir` validation before comparison run-root creation, variant run-dir preparation, direct composite run-dir creation, and artifact writes. | closed |
| P09-T-002 | Tampering | YAML/JSON config loading | Medium | mitigate | Use safe deserialization; avoid `eval`/pickle. | closed |
| P09-T-003 | Tampering / Data Integrity | Strategy variant selection | Medium | mitigate | Restrict strategy variants to fixed allowlist. | closed |
| P09-T-004 | Tampering / Data Integrity | Signal-to-weight mapping | Medium | mitigate | Clip signal magnitudes and normalize aggregate exposure. | closed |
| P09-T-005 | Tampering / Information Disclosure | CSV signal artifacts | Medium | mitigate | CSV boundary sanitizer prefixes formula-trigger strings before all Phase 09/backtest CSV artifact writes. | closed |
| P09-R-001 | Repudiation | Run cards and comparison reports | Low | mitigate | Preserve provenance tying reports back to run artifacts/config/strategy path. | closed |
| P09-I-001 | Information Disclosure | Subprocess error handling | Medium | mitigate | Subprocess failure output is redacted and truncated before being included in exceptions. | closed |
| P09-D-001 | Denial of Service | Comparison subprocess execution | High | mitigate | Per-variant `subprocess.run(..., timeout=...)` with CLI/env-configurable timeout and bounded timeout diagnostics. | closed |
| P09-D-002 | Denial of Service | Per-bar signal generation and artifact serialization | High | mitigate | Env-configurable limits for code count, date span, per-symbol/total data rows, per-source records, and CSV artifact rows. | closed |
| P09-E-001 | Elevation of Privilege | Subprocess invocation | High | mitigate | Avoid shell injection via list-form subprocess call and `shell=False`. | closed |
| P09-I-002 | Information Disclosure / Integrity | JSON artifacts | Low | mitigate | Use structured JSON serialization/parsing rather than executable representations. | closed |

*Status: open · closed*  
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Evidence

### Newly Closed Threat Evidence

| Threat ID | Evidence |
|-----------|----------|
| P09-S-001 | `agent/backtest/runner.py` adds `_sha256_file`, `_trusted_signal_engine_hashes`, and `_verify_trusted_signal_engine`; `main()` verifies `run_dir/code/signal_engine.py` before dynamic import. Tests in `agent/tests/test_backtest_runner_security.py` verify packaged template trust, untrusted AST-safe rejection, and operator-approved extra hash acceptance. |
| P09-T-001 | `agent/backtest/composite_backtest_compare.py` applies `safe_run_dir` to comparison `run_root` and each prepared variant run directory; `agent/backtest/engines/composite_engine.py` applies `safe_run_dir` before direct composite run-dir creation. Tests in `agent/tests/test_composite_backtest_compare.py` verify unsafe roots are rejected and configured roots are accepted. |
| P09-T-005 | `agent/backtest/csv_safety.py` implements `sanitize_csv_value`, `sanitize_csv_frame`, and `safe_to_csv`; `agent/backtest/engines/base.py` and `agent/backtest/engines/composite_engine.py` use `safe_to_csv` for CSV artifact writes. Tests in `agent/tests/test_csv_safety.py` verify formula escaping, numeric preservation, non-mutation, and safe CSV output. |
| P09-I-001 | `agent/backtest/composite_backtest_compare.py` adds `_redact_output`, `_truncate_output`, and `_format_subprocess_output`; failed variants now raise bounded diagnostics rather than raw stdout/stderr. Tests in `agent/tests/test_composite_backtest_compare.py` verify secrets are redacted and long output is truncated. |
| P09-D-001 | `agent/backtest/composite_backtest_compare.py` adds `_compare_timeout_seconds`, CLI `--timeout-seconds`, and `subprocess.run(..., timeout=...)`; timeout exceptions are converted to bounded RuntimeError diagnostics. Tests in `agent/tests/test_composite_backtest_compare.py` verify timeout propagation and bounded redacted timeout output. |
| P09-D-002 | `agent/backtest/runner.py` enforces `VIBE_TRADING_MAX_BACKTEST_CODES`, `VIBE_TRADING_MAX_BACKTEST_DATE_DAYS`, `VIBE_TRADING_MAX_BACKTEST_ROWS_PER_SYMBOL`, and `VIBE_TRADING_MAX_BACKTEST_TOTAL_ROWS`; `agent/backtest/engines/composite_engine.py` caps retained per-source signal records via `VIBE_TRADING_MAX_PER_SOURCE_SIGNAL_RECORDS`; `agent/backtest/csv_safety.py` enforces `VIBE_TRADING_MAX_ARTIFACT_ROWS` before CSV artifact writes. Tests in `agent/tests/test_engine_robustness.py` and `agent/tests/test_csv_safety.py` verify config/data/artifact caps. |

### Previously Closed Threat Evidence

| Threat ID | Evidence |
|-----------|----------|
| P09-T-002 | `agent/backtest/composite_backtest_compare.py` uses `yaml.safe_load`; `agent/backtest/configs/signal_engine.py` uses `json.loads`. |
| P09-T-003 | `agent/backtest/composite_backtest_compare.py` defines fixed variants; `agent/backtest/configs/signal_engine.py` whitelists supported `strategy_variant` values and rejects unknown values. |
| P09-T-004 | `agent/backtest/engines/base.py` clips each symbol's signal to `[-1.0, 1.0]` and normalizes aggregate exposure. |
| P09-R-001 | `agent/backtest/engines/base.py` writes run cards with config, metrics, data sources, and strategy path; comparison/reporting code records or loads run directories and run cards. |
| P09-E-001 | `agent/backtest/composite_backtest_compare.py` uses list-form subprocess command with `sys.executable`, fixed `-m backtest.runner`, and default `shell=False`. |
| P09-I-002 | `agent/backtest/engines/base.py`, `agent/backtest/engines/composite_engine.py`, and `agent/backtest/reporting/composite_report.py` use structured JSON serialization/parsing, not pickle/eval. |

---

## Accepted Risks Log

No accepted risks.

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|

---

## Security Audit 2026-06-06

| Metric | Count |
|--------|-------|
| Threats found | 12 |
| Closed | 12 |
| Open | 0 |
| Open High | 0 |

### Verification Evidence

```bash
.venv/bin/python -m pytest -q \
  agent/tests/test_csv_safety.py \
  agent/tests/test_composite_backtest_compare.py \
  agent/tests/test_backtest_runner_security.py \
  agent/tests/test_engine_robustness.py
```

Result: `49 passed in 0.67s`.

```bash
.venv/bin/python -m py_compile \
  agent/backtest/runner.py \
  agent/backtest/composite_backtest_compare.py \
  agent/backtest/csv_safety.py \
  agent/backtest/engines/base.py \
  agent/backtest/engines/composite_engine.py
```

Result: passed.

```bash
.venv/bin/python -m pytest -q \
  agent/tests/test_run_card.py \
  agent/tests/test_metrics.py \
  agent/tests/test_market_detection.py \
  agent/tests/strategies/test_composite_signal_base.py \
  agent/tests/strategies/test_composite_trend_strategy.py \
  agent/tests/test_backtest_runner_security.py \
  agent/tests/test_path_safety.py
```

Result: `161 passed, 2 warnings in 1.15s`.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-06 | 12 | 6 | 6 | gsd-security-auditor |
| 2026-06-06 | 12 | 12 | 0 | Claude Code |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-06.
