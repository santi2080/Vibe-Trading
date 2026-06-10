---
phase: "15-deterministic-artifacts-markdown-report"
plan: "01"
subsystem: data-pipeline
tags: [artifacts, manifest, markdown-report, scan-pipeline, reporting]
requirements: [ART-01, RPT-01, RPT-02]

# Dependency graph
requires:
  - phase: "14-composite-signal-scan-buckets"
    provides: "ScanSignalReport, scan_results.json schema, run_signal_scan(), signal bucket classification"
provides:
  - "Manifest dataclass — scan metadata + file inventory written to manifest.json"
  - "MarkdownReportRenderer — renders report.md from JSON artifacts (data_health.json, scan_results.json)"
  - "run_reporting() — orchestrator that writes manifest.json and report.md"
  - "All four scan artifacts written deterministically per run: manifest.json, data_health.json, scan_results.json, report.md"
  - "ART-01 (four artifacts), RPT-01 (report sections), RPT-02 (report from JSON artifacts) requirements fulfilled"
affects:
  - "scan-pipeline — complete end-to-end pipeline: validate -> health gate -> signal scan -> reporting"

# Tech tracking
tech-stack:
  added: [json (stdlib)]
  patterns:
    - "Report rendered entirely from JSON artifacts, never from ad-hoc state"
    - "manifest.json written before gate so even blocked scans have a record"
    - "MarkdownReportRenderer.load_artifacts() — on-demand JSON loading if artifacts not passed"
    - "FAIL status stops report before candidate tables (scope guardrail)"

key-files:
  created:
    - "agent/src/data/scan_reporting.py — Manifest, MarkdownReportRenderer, run_reporting()"
    - "agent/tests/test_scan_reporting.py — 10 focused tests (ART-01, RPT-01, RPT-02)"
  modified:
    - "agent/cli/commands/scan.py — wired run_reporting() after signal scan; manifest writing at top of _run_data_gate()"

key-decisions:
  - "manifest.json written at START of _run_data_gate() (before gate runs) so failed scans still produce a record"
  - "report.md rendered via MarkdownReportRenderer which loads from JSON files; no ad-hoc state"
  - "FAIL status triggers early return in _render_data_health(), stopping before actionable/watch tables"
  - "_FORBIDDEN_TERMS set enforces no trading advice, ranking, or performance claims in report"
  - "scan_reporting.py uses standard json module (not orjson/pydantic) for simplicity and zero extra deps"

scope-guardrails:
  - "report.md does not contain: buy/sell/hold, best configuration, rank, performance metric, win rate, sharpe"
  - "report.md disclaimer: 'Candidates are for research only. Not financial advice.'"
  - "report.md does not rank symbols or claim 'best configuration'"

patterns-established:
  - "Pattern: four deterministic artifacts written per scan run (manifest, data_health, scan_results, report)"
  - "Pattern: manifest.json as file inventory enabling downstream consumers to discover artifacts"
  - "Pattern: FAIL gate blocks report generation after data health section"

requirements-completed: [ART-01, RPT-01, RPT-02]

# Metrics
duration: 5min
completed: 2026-06-10
---

# Phase 15: Deterministic Artifacts & Markdown Report — Plan 01 Summary

## What was done

Implemented Phase 15 of the scan pipeline: deterministic artifact generation and Markdown report rendering.

### Task 1: `agent/src/data/scan_reporting.py` (new)

Three components:

**`Manifest` dataclass** — scan metadata and file inventory. Fields: `scan_date`, `watchlist_name`, `version` (default "1.0.0"), `artifacts` (dict of name→filename), `scan_info`, `total_symbols`. Methods: `to_dict()`, `to_json(path)`.

**`MarkdownReportRenderer` class** — renders `report.md` from JSON artifacts:
- `__init__`: accepts `ScanPlan`, `output_dir`, `scan_date`, optional `signal_report` and `health_report_dict`
- `load_artifacts()`: loads `scan_results.json` and `data_health.json` from `output_dir` if not passed
- `render()`: produces full Markdown with all 7 sections (header, data health, actionable, watch, risk/excluded, skipped, failed, artifacts)
- `write(path)`: writes rendered string to file
- `_FORBIDDEN_TERMS` enforcement: no buy/sell/hold/rank/performance claims
- **FAIL stop**: `render()` stops after the Data Health section when status is FAIL

**`run_reporting(scan_plan, output_dir, *, scan_date, format, console) -> Manifest`** — orchestrator:
1. Build and write `manifest.json`
2. Load `data_health.json` + `scan_results.json` from output_dir
3. Render `report.md` via `MarkdownReportRenderer`
4. Write `report.md`
5. Print `[dim]Report written to ...[/dim]` if format=table
6. Return manifest

### Task 2: `agent/cli/commands/scan.py` (modified)

Two changes to `_run_data_gate()`:

1. **Top of function** (before gate): write `manifest.json` so even blocked scans produce a record.
2. **After `run_signal_scan()` call**: call `run_reporting()` in a try/except block (Phase 6: Reporting).

### Task 3: `agent/tests/test_scan_reporting.py` (new)

10 tests across 3 classes:

- **`TestManifest`** (3): schema, JSON roundtrip, required artifact keys
- **`TestMarkdownReportRenderer`** (5): all sections present, FAIL stop, trading-advice avoidance, artifact loading, artifact links
- **`TestRunReporting`** (2): manifest+report written, manifest written independently of gate data

All 10 tests pass.

## Verification

```
10 passed in 0.26s
CLI --help: ok
Import check: ok
```

## Files changed

| File | Change |
|------|--------|
| `agent/src/data/scan_reporting.py` | Created — 350 lines |
| `agent/cli/commands/scan.py` | Modified — +30 lines (manifest write + run_reporting call) |
| `agent/tests/test_scan_reporting.py` | Created — 320 lines, 10 tests |
