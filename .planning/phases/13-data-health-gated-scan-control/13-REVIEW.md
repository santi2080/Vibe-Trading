---
phase: 13-data-health-gated-scan-control
reviewed: 2026-06-10T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - agent/cli/commands/scan.py
  - agent/tests/test_scan_gate.py
  - agent/tests/test_scan_command.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-10
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

The implementation correctly wires a data-health gate into the `/scan --run` CLI path, with the core logic in `_run_data_gate` producing correct PASS/WARN/FAIL outcomes and writing `data_health.json`. Tests are well-structured with consistent mock factories across both test files. Four warnings and four informational items were found; no correctness bugs or security vulnerabilities.

## Warnings

### WR-01: Inconsistent gate output for `--run --format json`

**File:** `agent/cli/commands/scan.py:57-60`
**Issue:** When `--format json` is used with `--run`, the gate's formatted table (`format_report_table`) is never printed, and the `pass` statement on line 60 intentionally does nothing. The JSON output only contains `data_health.json` on disk; the terminal output is the plan JSON (lines 250-258) with no gate status visible in it. This means a user running `--run --format json` sees no gate outcome in stdout.
**Fix:** After line 60, emit the gate status into stdout so the machine-readable output is complete:
```python
if format == "json":
    import json as _json
    console.print(_json.dumps(gate_dict, indent=2, default=str))
else:
    ...
```

---

### WR-02: `--format json` hardcodes static `gate_status_preview` instead of reading actual thresholds

**File:** `agent/cli/commands/scan.py:253-257`
**Issue:** `blocking_timeframes` and `staleness_thresholds` are hardcoded static values. If the thresholds in `watchlist_data_health.py` (e.g., `STALE_AFTER`) change, the JSON plan preview silently diverges from reality.
**Fix:** Import and serialize the actual constants:
```python
from src.data.watchlist_data_health import BLOCKING_TIMEFRAMES, STALE_AFTER

output_data["gate_status_preview"] = {
    "note": "Gate runs on --run. Use --watchlist-data-check to preview.",
    "blocking_timeframes": list(BLOCKING_TIMEFRAMES),
    "staleness_thresholds": {k: _str_delta(v) for k, v in STALE_AFTER.items()},
}
```

---

### WR-03: `--dry-run` prints "gate and analysis skipped" but still prints the plan table first

**File:** `agent/cli/commands/scan.py:274-292`
**Issue:** In `--run --dry-run` mode, the code first builds the scan plan (Phase 2, lines 238-247) and prints the plan table (lines 259-272), then prints the dry-run panel (lines 275-283). The output sequence is: plan table → dry-run panel. This may confuse users who expect dry-run to be "quiet." More importantly, `build_scan_plan` is executed even when `--dry-run` is set, wasting cycles on a full plan build only to discard it in the output.
**Fix:** Guard the plan build behind a `not dry_run` condition:
```python
if dry_run:
    console.print(Panel(...))  # print only the dry-run panel
else:
    plan = build_scan_plan(...)
    # output phase unchanged
```

---

### WR-04: `test_gate_preview_in_plan_mode_json` assertion is fragile due to Rich text wrapping

**File:** `agent/tests/test_scan_gate.py:220-226`
**Issue:** The test uses `output_lower = result.output.lower()` and then checks `in output_lower` for all string keys. This masks any case where the JSON is malformed — for example, if `"gate_status_preview"` were mangled to `"gate_status_preview\\": something"`, the assertion `"gate_status_preview" in output_lower` would still pass. The test should either parse the actual JSON (preferred) or validate the full JSON structure.
**Fix:** After capturing the CliRunner result, verify the full JSON:
```python
import json
data = json.loads(result.output)
assert "gate_status_preview" in data
assert data["gate_status_preview"]["blocking_timeframes"] == ["1d", "1h"]
```

---

## Info

### IN-01: Dead `pass` statement in `--run --format json` branch

**File:** `agent/cli/commands/scan.py:60`
**Issue:** The `pass` statement on line 60 is intentional (the comment says "Gate is already in data_health.json") but the intent is unclear. It should either do something visible (see WR-01 fix) or be removed and the comment clarified.

---

### IN-02: `report.gate_status` set on mock but never read in `_run_data_gate`

**File:** `agent/cli/commands/scan.py:55-70`
**Issue:** `_run_data_gate` extracts `gate_dict["status"]` (from `report.to_dict()["gate"]["status"]`), but the mock sets `report.gate_status = status` which is never accessed. This is harmless but indicates a mismatch between the mock's surface and what the real `WatchlistDataHealthReport` exposes. If the real class has `gate_status` as the primary attribute, the gate code should use it directly rather than going through `to_dict()`.

---

### IN-03: `_mock_report` duplicates identical logic in both test files

**File:** `agent/tests/test_scan_gate.py:28-54`, `agent/tests/test_scan_command.py:26-52`
**Issue:** The `_mock_report` method is copy-pasted verbatim into both test files. If the `WatchlistDataHealthReport` schema changes, both copies must be updated in sync. Factor this into a shared fixture in `conftest.py`.

---

### IN-04: `scan_plan.py` uses bare `from .watchlist import WatchlistReader` while `scan.py` uses `from src.data.scan_validators import ...`

**File:** `agent/src/data/scan_plan.py:9`, `agent/cli/commands/scan.py:25-27`
**Issue:** Within the same `src.data` package, `scan_plan.py` uses relative imports (`.watchlist`) while `scan.py` uses absolute `src.` imports. This inconsistency is minor but makes it harder to run `scan.py` as a standalone module (`python -m agent.cli.commands.scan`). The `--run` path uses the `src.` absolute import correctly; the module-level `__main__` guard at line 295-298 would also need the agent directory on `sys.path`.

---

_Reviewed: 2026-06-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
