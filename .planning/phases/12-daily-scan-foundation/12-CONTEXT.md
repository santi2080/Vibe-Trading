# Phase 12 Context: Daily Scan Foundation & Run Plan

**Phase:** 12  
**Slug:** daily-scan-foundation  
**Milestone:** v2.2 daily-scan-report-loop  
**Status:** Discussed  
**Date:** 2026-06-09

## Domain

Phase 12 delivers the foundation for the daily scan workflow: a single CLI entry point (`scan` command) with watchlist validation, normalized scan plan display, and local-data-only execution mode. This is the foundation that Phase 13 (data-health gate), Phase 14 (signal scan buckets), and Phase 15 (artifacts & report) build on.

## Prior Decisions

From v2.1 milestone closure and Phase 11:

- **Local-data-first:** All scan operations use local parquet data only. No remote fetch in v2.2.
- **Canonical Symbol Format:** Phase 11 established the `SymbolTranslator` contract. Phase 12 uses this for symbol normalization.
- **Data Health Gate:** Existing `check_watchlist_data()` from `src/data/watchlist_data_health.py` provides the gate. Phase 13 integrates it as mandatory.
- **Watchlist CSV:** Existing format uses columns: symbol, market, exchange, sector, timeframes.

## Decisions

### 1. CLI Entry Point: Single Command + plan/run Semantics

**Decision:** Single `scan` command with `--plan` (default) and `--run` modes.

```
python -m agent.cli scan --watchlist watchlist/us_futures_watchlist.csv --data-dir data/ --output output/

# Default: --plan (preview, no execution)
# --run: actually execute scan
```

Rationale: Simpler UX. `--plan` is the safe default. User must explicitly `--run` to execute. Consistent with safety-first design.

**Implementation:**

- Add `scan` command to `agent/cli/commands/`
- Use Click or Typer (evaluate existing patterns in `agent/cli/`)
- `--watchlist` (required), `--data-dir` (default: `data/`), `--output` (default: `output/`), `--format` (default: `table`), `--run` (flag)

### 2. Watchlist Validation: Fail Fast

**Decision:** Immediate exit on first validation error in CLI execution mode.

- Validation rules: missing path, unsafe path, missing required columns, empty list, duplicates, unsupported market/timeframe
- `--plan` mode shows all issues in a summary table before suggesting corrective action
- `--run` mode fails immediately on first error (fail-fast)

Rationale: CLI tool convention. All validation rules are discoverable via `--help`. `--plan` mode gives complete picture before execution.

**Implementation:**

- Reuse existing `_resolve_watchlist_path()` from `watchlist_tool.py` for path validation
- Add validation functions in `agent/cli/commands/scan.py`
- Define `ValidationResult` dataclass with issue type, message, and severity

### 3. Scan Plan Format: Dual Output (Table + JSON)

**Decision:** `--format table` (default) for human-readable output; `--format json` for machine-readable.

Table format:
```
Symbol       Market       Timeframes    Status    Cache Path
--------    ---------    ----------    ------    ---------
GC=F        us_futures   1D, 4H       OK       data/us_futures/gc_f_1d.parquet
SI=F        us_futures   1D, 4H       OK       data/us_futures/si_f_1d.parquet
```

JSON format:
```json
{
  "symbols": [
    {
      "symbol": "GC=F",
      "market": "us_futures",
      "timeframes": ["1D", "4H"],
      "cache_path": "data/us_futures/gc_f_1d.parquet",
      "output_path": "output/2026-06-09/gc_f.json"
    }
  ],
  "summary": {"total": 10, "by_market": {"us_futures": 5, "us_stocks": 5}}
}
```

**Implementation:**

- `ScanPlan` dataclass in `agent/cli/commands/scan.py`
- `format_plan_table()` using `tabulate` or similar
- `format_plan_json()` using `pydantic` serialization

### 4. Output Directory Strategy: Date-Based + User Override

**Decision:** Fixed date-based directory with `--output` override.

```
# Default: output/YYYY-MM-DD/
output/2026-06-09/
├── manifest.json
├── data_health.json
├── scan_results.json
└── report.md

# User override: --output ./my-scan/
# Respects user path, creates if needed
# Does NOT auto-add date suffix
```

Rationale: Simple daily workflow. Same-date runs overwrite (acceptable for MVP). `--output` gives full control when needed.

**Implementation:**

- Derive date from `--now` timestamp (default: current time)
- `Path(output_dir) / date_str` for default layout
- User `--output` bypasses date subdirectory

### 5. Parquet Dependency: Lazy Detection

**Decision:** Runtime detection with helpful error message.

```python
try:
    import pyarrow.parquet as pq
except ImportError:
    raise ImportError(
        "pyarrow is required for Parquet I/O. "
        "Install with: pip install 'vibe-trading[parquet]'"
    )
```

Rationale: Backward compatibility. Users without Parquet use cases don't need the dependency. Clear message on install.

**Implementation:**

- Add `pyarrow` to optional dependencies in `pyproject.toml` extras
- Add runtime check at scan module import time
- Document in `--help` output

## Canonical Refs

- `agent/src/tools/watchlist_tool.py` — existing watchlist tools, path resolution, `_resolve_watchlist_path()`
- `agent/src/data/watchlist_data_health.py` — existing gate implementation (Phase 13 integration)
- `agent/cli/` — existing CLI structure (evaluate before adding `scan` command)
- `watchlist/*.csv` — existing watchlist format with columns: symbol, market, exchange, sector, timeframes
- `agent/backtest/loaders/hybrid_fetcher.py` — data loading patterns
- `.planning/phases/11-symbol-format-mapping-contract/11-CONTEXT.md` — Phase 11 decisions (SymbolTranslator)
- `.planning/ROADMAP.md` — Phase 12 success criteria
- `.planning/REQUIREMENTS.md` — STK-01, CLI-01, CLI-02, WLS-01, WLS-02

## Codebase Context

### Reusable Assets

- `_resolve_watchlist_path()` — path validation and sandboxing
- `WatchlistReader` from `src/data/watchlist.py` — CSV parsing
- `check_watchlist_data()` from `src/data/watchlist_data_health.py` — gate (Phase 13)
- `SymbolTranslator` from `agent/src/data/symbol_translator.py` — canonical format (Phase 11)

### Patterns

- Path safety: always use `.resolve()` and sandbox to watchlist root
- Error format: structured JSON with `status`, `error`, `error_type` fields
- CLI structure: commands in `agent/cli/commands/`, `__main__.py` entry point

### Integration Points

- `agent/cli/main.py` — add `scan` command registration
- `agent/src/data/watchlist.py` — `WatchlistReader` for CSV parsing
- Phase 13: data health gate integration
- Phase 14: `CompositeTrendStrategy` signal scan
- Phase 15: artifact writing

## Success Criteria

From ROADMAP.md:

1. User can invoke one daily scan command with explicit watchlist, data directory, output directory, timestamp, and JSON or human output mode.
2. User is told early when the watchlist path is missing or unsafe, required columns are absent, the list is empty, duplicate symbols exist, or market/timeframe values are unsupported.
3. User can inspect a normalized scan plan that lists each symbol, market, required timeframes, cache paths, and intended output paths before strategy results are produced.
4. The scan uses only local data inputs in v2.2; no remote provider fetch is triggered by the default daily scan command.
5. Parquet read/write support is dependable because the project explicitly declares the required Parquet engine dependency.

## Deferred Ideas

(None captured during Phase 12 discussion.)
