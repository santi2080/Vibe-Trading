# Phase 14: Composite Signal Scan Buckets - Research

**Researched:** 2026-06-10
**Domain:** Signal scan bucket classification via `CompositeTrendStrategy` / `TradingSignal` semantics
**Confidence:** HIGH

## Summary

Phase 14 implements the signal scan layer (SIG-01, SIG-02) for the daily scan pipeline. It runs `CompositeTrendStrategy` on every watchlist symbol's local parquet data and classifies each into exactly one of five buckets: Actionable, Watch, Risk/Excluded, Skipped, or Failed. Output is dual-format JSON + table. The existing `TradingSignal` contract (`agent/src/strategies/composite/base.py`) already defines all signal semantics; Phase 14 wires it into the scan pipeline after the data-health gate passes.

**Primary recommendation:** Build a new `scan_signal_buckets.py` module under `agent/src/data/` that mirrors the `check_watchlist_data()` pattern: accepts a scan plan + output dir, iterates each symbol, loads parquet data, runs `CompositeTrendStrategy`, classifies into buckets via thresholds on `TradingSignal` fields, and writes `scan_results.json` + renders a table.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Output format:** JSON + table dual output
- **Bucket classification basis:** trend direction (Bull/Bear/Neutral)
- **Exception handling:** record and continue (Graceful Degradation)

### Claude's Discretion
- Bucket threshold values (具体的 Bull/Bear 阈值)
- Table column layout
- Internal module structure (where to place new code)

### Deferred Ideas
(None for Phase 14)

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SIG-01 | Eligible symbols are scanned through `CompositeTrendStrategy` / `TradingSignal` semantics | `CompositeTrendStrategy` exists at `agent/src/strategies/composite/trend_composite.py` with `analyze(df) -> TradingSignal` API. `TradingSignal` fields: `direction` (BULL/BEAR/NEUTRAL), `status` (VALID/NO_SIGNAL/FILTERED/INVALID), `readiness` (READY/WAIT/BLOCKED/EXHAUSTED), `signal_score` (-100..100), `confidence` (0..1), `reasons`, `warnings`, `source_results`. |
| SIG-02 | Every watchlist symbol is assigned to exactly one bucket: Actionable, Watch, Risk/Excluded, Skipped, or Failed | Bucket classification logic maps `TradingSignal` fields to buckets. Skipped = data-health WARN/path issues (not block but no data). Failed = exceptions raised during analysis. Bucket mapping is the primary implementation design decision. |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Local parquet data loading | `agent/src/data/` | — | `watchlist_data_health.py` already owns this; reuse `read_local_parquet()` |
| Strategy execution (CompositeTrendStrategy) | `agent/src/strategies/composite/` | — | Existing `CompositeTrendStrategy.analyze(df)` takes OHLCV DataFrame, returns `TradingSignal` |
| Bucket classification | `agent/src/data/` | — | New `scan_signal_buckets.py` dataclass; follows same `check_watchlist_data()` pattern |
| JSON artifact writing | `agent/cli/commands/scan.py` | — | Orchestrates pipeline; Phase 13 calls `_run_data_gate()`; Phase 14 adds signal scan call |
| Human-readable table output | `agent/cli/commands/scan.py` | — | Uses `rich` console (already used in Phase 12-13) |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` | 3.10+ | Immutable result dataclasses | Project convention |
| Python stdlib `pathlib` | 3.10+ | Cross-platform path handling | Already used everywhere |
| `pandas` | existing | OHLCV DataFrame for strategy input | Already a project dependency |
| `pyarrow` | existing | Parquet file reading | Already required (Phase 12 STK-01) |
| `rich` | existing | Table rendering in CLI | Already used in Phase 12-13 |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `agent/src/strategies/composite.base` | `TradingSignal` dataclass + helper functions | Bucket classification logic |
| `agent/src/strategies/composite.trend_composite` | `CompositeTrendStrategy` strategy runner | Core signal generation |
| `agent/src/strategies.trend.__init__` | Lazy imports for concrete adapters | MTES, SuperTrend adapters |

### No External Dependencies Required
Phase 14 reuses all existing infrastructure. No new packages needed.

---

## Package Legitimacy Audit

> No external packages installed. All dependencies are existing project code or stdlib.

---

## Architecture Patterns

### System Architecture Diagram

```
scan.py --run
    │
    ├─ Phase 1: validate_watchlist()         [scan_validators.py]
    │
    ├─ Phase 2: build_scan_plan()            [scan_plan.py]
    │
    ├─ Phase 3: check_watchlist_data()      [watchlist_data_health.py]
    │       └─ Write: data_health.json
    │
    ├─ [GATE: FAIL → abort, WARN → continue with caveats]
    │
    └─ Phase 4: run_signal_scan()            [NEW: scan_signal_buckets.py]
            │
            ├─ For each symbol in scan plan:
            │   ├─ Load parquet (1d) via read_local_parquet()
            │   ├─ Instantiate CompositeTrendStrategy
            │   ├─ Run strategy.analyze(df) → TradingSignal
            │   ├─ Classify into bucket
            │   └─ Record result (or exception as Failed)
            │
            ├─ Write: scan_results.json
            └─ Render: signal table (rich)

Artifact: scan_results.json
  ├── scan_info: { watchlist, data_dir, scan_date, total, buckets_summary }
  ├── buckets:
  │   ├── actionable: [...]
  │   ├── watch: [...]
  │   ├── risk_excluded: [...]
  │   ├── skipped: [...]
  │   └── failed: [...]
  └── metadata: { strategy_name, sources, version }
```

### Recommended Project Structure

```
agent/src/data/
    scan_signal_buckets.py   # NEW: bucket classification models + run function
    scan_results.py          # (future: consolidated scan results model)
    ...
agent/cli/commands/
    scan.py                 # MODIFY: add signal scan phase after gate
agent/tests/
    test_scan_gate.py       # Phase 13 tests
    test_scan_signal_buckets.py  # NEW: SIG-01, SIG-02 tests
```

### Pattern 1: Signal Bucket Classification

**What:** Map `TradingSignal` fields to one of five buckets.

**When to use:** Every symbol after gate PASS/WARN.

**Implementation sketch:**
```python
# Source: Derived from TradingSignal contract and CONTEXT.md decisions
from dataclasses import dataclass
from agent.src.strategies.composite.base import TradingSignal

@dataclass
class SymbolSignalResult:
    symbol: str
    name: str
    market: str
    bucket: str           # "actionable" | "watch" | "risk_excluded" | "skipped" | "failed"
    bucket_reason: str     # Human-readable reason
    trading_signal: dict | None  # TradingSignal.to_dict() or None for failed/skipped
    error: str | None     # None unless bucket == "failed"

BULL_BEAR_THRESHOLD = 0.45   # [ASSUMED] minimum confidence for actionable
WATCH_CONFIDENCE_FLOOR = 0.25  # [ASSUMED] below this = risk/watched

def classify_trading_signal(signal: TradingSignal) -> tuple[str, str]:
    """Classify TradingSignal into bucket + reason.

    Bucket thresholds are based on:
    - direction (BULL/BEAR/NEUTRAL)
    - status (VALID/NO_SIGNAL/FILTERED/INVALID)
    - readiness (READY/WAIT/BLOCKED/EXHAUSTED)
    - signal_score (-100..100)
    - confidence (0..1)

    Returns (bucket, reason).
    """
    # Failed: invalid status or blocked readiness
    if signal.status == "INVALID":
        return "failed", f"status=INVALID: {signal.warnings[0] if signal.warnings else 'unknown'}"
    if signal.status == "NO_SIGNAL":
        return "skipped", "status=NO_SIGNAL: no trend signal detected"
    if signal.readiness == "BLOCKED" or signal.readiness == "EXHAUSTED":
        return "risk_excluded", f"readiness={signal.readiness}: trend exhausted or blocked"

    # Actionable: directional + valid + ready + sufficient confidence
    if signal.direction in ("BULL", "BEAR"):
        if signal.status == "VALID" and signal.readiness == "READY":
            if signal.confidence >= BULL_BEAR_THRESHOLD:
                return "actionable", (
                    f"{signal.direction} trend, confidence={signal.confidence:.2f}, "
                    f"score={signal.signal_score:.1f}"
                )
            elif signal.confidence >= WATCH_CONFIDENCE_FLOOR:
                return "watch", (
                    f"{signal.direction} trend, low confidence={signal.confidence:.2f}"
                )
            else:
                return "risk_excluded", f"low confidence={signal.confidence:.2f}"

    # Neutral or filtered: watch or risk
    if signal.status == "FILTERED":
        return "risk_excluded", f"FILTERED: {signal.warnings[0] if signal.warnings else 'filtered out'}"
    if signal.direction == "NEUTRAL":
        return "watch", "no directional trend (NEUTRAL)"
    return "watch", f"direction={signal.direction}, status={signal.status}"
```

### Anti-Patterns to Avoid

- **`WatchlistAnalyzer` (legacy):** The old `analysis/watchlist_analyzer.py` uses LONG/SHORT/WAIT semantics. Do NOT use it — it predates `TradingSignal` contract. Only use `CompositeTrendStrategy`.
- **Per-symbol JSON files:** SIG-02 requires `scan_results.json` as a single artifact listing all symbols. Do NOT write `{symbol}.json` per symbol (used in Phase 12 plan phase, but signal results go into one file).
- **Blocking on failed symbols:** Graceful degradation means exceptions on one symbol are caught and recorded in the `failed` bucket. Never `raise` from the scan loop.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parquet reading | New parquet reader | `read_local_parquet()` from `watchlist_data_health.py` | Already handles engine errors, returns (df, error) tuple |
| OHLCV validation | Custom column checks | `CompositeTrendStrategy.validate(df)` | Already implemented in existing code |
| Signal contract | Custom signal dict | `TradingSignal` dataclass | Canonical, frozen, with `to_dict()` |
| Data path resolution | New path logic | `resolve_cache_file()` from `watchlist_data_health.py` | Already resolves market/timeframe to parquet path |

---

## Runtime State Inventory

Step 2.5: SKIPPED — Phase 14 is a greenfield feature addition to the scan pipeline. No rename/refactor/migration involved.

---

## Common Pitfalls

### Pitfall 1: Wrong DataFrame Used for Strategy
**What goes wrong:** Strategy runs on 1h data when 1d should be primary timeframe.
**Why it happens:** `scan_plan.py` resolves `cache_paths` for all timeframes including 1h. The strategy should run on the PRIMARY (longest) timeframe (typically 1d).
**How to avoid:** Use the first (primary) timeframe from `symbol_plan.timeframes[0]` for strategy analysis. Only 1d is relevant for trend direction.
**Warning signs:** All symbols get BULL/BEAR but with identical scores — this is suspicious for a multi-timeframe watchlist.

### Pitfall 2: `TradingSignal` Status vs Readiness Confusion
**What goes wrong:** Bucket classification uses `status` when `readiness` matters more for Actionable vs Risk.
**Why it happens:** `TradingSignal` has both `status` (VALID/NO_SIGNAL/FILTERED/INVALID) and `readiness` (READY/WAIT/BLOCKED/EXHAUSTED). Only the combination of VALID + READY + BULL/BEAR + confidence threshold is Actionable.
**How to avoid:** Use both fields. See classification sketch above.
**Warning signs:** Symbols with BULL direction in `source_results` but classified as Failed — likely ignoring `readiness`.

### Pitfall 3: Exception Swallowing Without Detail
**What goes wrong:** Failed bucket has generic "error" but no actionable detail for debugging.
**Why it happens:** Bare `except Exception` catches everything including `KeyboardInterrupt`, `SystemExit`, `MemoryError`.
**How to avoid:** Catch `(Exception,)` specifically, record `type(exc).__name__ + ": " + str(exc)`. Let `BaseException` propagate.
**Warning signs:** `scan_results.json` shows `error: ` (empty string) for failed symbols.

### Pitfall 4: Memory Exhaustion with Large Watchlists
**What goes wrong:** Loading all parquet files into memory simultaneously.
**Why it happens:** Natural to collect results in a list then serialize; but each parquet DataFrame can be 50k+ rows.
**How to avoid:** Yield results per symbol, write incrementally to the JSON list. Or load one at a time and append.
**Warning signs:** Memory usage spikes with large watchlists (100+ symbols).

### Pitfall 5: Stale Data Passed Through Gate But Produces Bad Signals
**What goes wrong:** Data-health WARN (e.g., stale 1d) passes gate but produces neutral/no_signal results.
**Why it happens:** Gate WARN does not block but data is questionable. Strategy produces NEUTRAL results.
**How to avoid:** Record WARN symbols in `skipped` bucket with reason `"data_warn"` or include data age in the `trading_signal.metadata` so downstream can see the staleness.
**Warning signs:** All symbols get `watch` or `skipped` bucket on a normal day — data staleness may be root cause.

---

## Code Examples

### Running CompositeTrendStrategy on Parquet Data

```python
# Source: Pattern from existing codebase
import pandas as pd
from src.strategies.composite.trend_composite import CompositeTrendStrategy
from src.strategies.composite.base import TradingSignal
from src.strategies.trend import EnhancedSuperTrendStrategy
from src.data.watchlist_data_health import read_local_parquet

# Build composite with available adapters
composite = CompositeTrendStrategy(sources=[
    EnhancedSuperTrendStrategy(),
])

# Load parquet (reuse existing helper)
cache_path = Path("data/us_futures/GC=F/1d.parquet")
df, read_error = read_local_parquet(cache_path)
if read_error:
    # Record as failed
    results.append(SymbolSignalResult(symbol="GC=F", ..., bucket="failed", error=read_error))
    continue

signal: TradingSignal = composite.analyze(df)
# signal.direction: BULL | BEAR | NEUTRAL
# signal.status: VALID | NO_SIGNAL | FILTERED | INVALID
# signal.readiness: READY | WAIT | BLOCKED | EXHAUSTED
# signal.signal_score: -100..100
# signal.confidence: 0..1
```

### scan_results.json Schema

```json
// Source: Based on SIG-01, SIG-02 + CONTEXT.md decisions
{
  "scan_info": {
    "watchlist": "watchlist/us_futures_watchlist.csv",
    "data_dir": "data",
    "output_dir": "output/2026-06-10",
    "scan_date": "2026-06-10",
    "strategy": "composite_trend",
    "version": "1.0.0"
  },
  "buckets_summary": {
    "actionable": 3,
    "watch": 5,
    "risk_excluded": 2,
    "skipped": 1,
    "failed": 0,
    "total": 11
  },
  "buckets": {
    "actionable": [
      {
        "symbol": "GC=F",
        "name": "Gold",
        "market": "us_futures",
        "bucket_reason": "BULL trend, confidence=0.72, score=68.3",
        "trading_signal": {
          "direction": "BULL",
          "status": "VALID",
          "readiness": "READY",
          "signal_score": 68.3,
          "confidence": 0.72,
          "reasons": ["enhanced_supertrend: BULL", "mtes_v3: BULL"],
          "warnings": [],
          "source_results": {...}
        }
      }
    ],
    "watch": [...],
    "risk_excluded": [...],
    "skipped": [...],
    "failed": [
      {
        "symbol": "XYZ",
        "name": "XYZ Corp",
        "market": "us_stocks",
        "bucket": "failed",
        "bucket_reason": "status=INVALID: missing columns: ['low']",
        "error": "missing columns: ['low']",
        "trading_signal": null
      }
    ]
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `WatchlistAnalyzer.analyze_all()` returns `AnalysisResult` with LONG/SHORT/NEUTRAL semantics | `TradingSignal` with BULL/BEAR/NEUTRAL + VALID/READY semantics | Phase 08 (PH08 contract) | Canonical contract separates signal direction from execution action |
| Per-symbol JSON files in output dir | Single `scan_results.json` with bucket grouping | Phase 14 | Single artifact easier to consume for reporting (Phase 15) |

**Deprecated/outdated:**
- `agent/src/analysis/watchlist_analyzer.py`: Uses legacy `LONG/SHORT` semantics — do not use in Phase 14
- Phase 12 plan phase used `{symbol}.json` output paths — signal results go into `scan_results.json` instead

---

## Assumptions Log

> All claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `BULL_BEAR_THRESHOLD = 0.45` for actionable confidence | Code Examples - classify_trading_signal | Threshold may need tuning; planner should make configurable or note as TODO |
| A2 | Primary timeframe = `timeframes[0]` (first in list from watchlist) | Pitfall 1 | If watchlist order is non-deterministic, results could vary. Planner: verify watchlist CSV ordering |
| A3 | `scan_results.json` goes in same output dir as `data_health.json` | Architecture Patterns | Yes per `output_dir` argument to scan command |
| A4 | Phase 14 runs after data-health gate PASS/WARN only (not FAIL) | Architecture Patterns | Yes per GATE-01 and existing `_run_data_gate()` logic |

---

## Open Questions

1. **Confidence threshold tuning**
   - What we know: `TradingSignal.confidence` is 0..1. `BULL_BEAR_THRESHOLD` determines actionable vs watch.
   - What's unclear: Is 0.45 the right default? Should it be configurable per market or strategy?
   - Recommendation: Hardcode reasonable defaults for v2.2; expose via `--signal-config` flag in a future phase.

2. **MTES vs SuperTrend source adapters**
   - What we know: `EnhancedSuperTrendStrategy` and `MTESv3TrendStrategy` are available via lazy import.
   - What's unclear: Which adapters should be composed in `CompositeTrendStrategy` for v2.2?
   - Recommendation: Default to `EnhancedSuperTrendStrategy` + `MTESv3TrendStrategy` (both are available). This is within Claude's discretion per CONTEXT.md.

3. **Skipped bucket scope**
   - What we know: SIG-02 lists 5 buckets. "Skipped" should include symbols that passed gate but have no analyzable data.
   - What's unclear: Should data-health WARN symbols go into `skipped` or `risk_excluded`?
   - Recommendation: Gate WARN → `skipped` (data quality concern, not strategy exclusion). Gate FAIL → already aborted.

4. **Per-symbol result files vs. single artifact**
   - What we know: Phase 12 plan had `{symbol}.json` output paths in scan plan. `scan_results.json` is the signal artifact.
   - What's unclear: Should Phase 14 also write per-symbol `.json` files?
   - Recommendation: No for v2.2. `scan_results.json` is sufficient. Per-symbol files can be added in Phase 15 (report generation).

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies beyond existing project infrastructure)

All Phase 14 dependencies are existing project code:
- `agent/src/strategies/composite/` — existing, not installed packages
- `agent/src/data/` — existing, not installed packages
- `agent/src/strategies/trend/` — existing, not installed packages
- `pyarrow` — already verified installed (Phase 12 STK-01)
- `pandas` — already verified installed
- `rich` — already verified installed (Phase 12-13)

---

## Validation Architecture

> Skip if `workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`. Key absent = enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `agent/pytest.ini` or `pyproject.toml` |
| Quick run command | `cd agent && python -m pytest tests/test_scan_signal_buckets.py -x -q` |
| Full suite command | `cd agent && python -m pytest tests/ -q --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|---------------|
| SIG-01 | Strategy runs via `CompositeTrendStrategy` on valid parquet | unit | `pytest tests/test_scan_signal_buckets.py::TestSignalScan::test_strategy_runs_on_valid_data -x` | NO — Wave 0 |
| SIG-01 | `TradingSignal` fields are captured in `scan_results.json` | unit | `pytest tests/test_scan_signal_buckets.py::TestSignalScan::test_signal_fields_in_results -x` | NO — Wave 0 |
| SIG-02 | Every symbol gets exactly one bucket | unit | `pytest tests/test_scan_signal_buckets.py::TestBucketClassification::test_exactly_one_bucket_per_symbol -x` | NO — Wave 0 |
| SIG-02 | All 5 buckets appear in results for mixed inputs | unit | `pytest tests/test_scan_signal_buckets.py::TestBucketClassification::test_all_five_buckets -x` | NO — Wave 0 |
| SIG-02 | Failed symbols record error but do not block scan | unit | `pytest tests/test_scan_signal_buckets.py::TestGracefulDegradation::test_failed_symbol_does_not_abort -x` | NO — Wave 0 |
| SIG-02 | Skipped symbols record reason | unit | `pytest tests/test_scan_signal_buckets.py::TestGracefulDegradation::test_skipped_records_reason -x` | NO — Wave 0 |
| SIG-02 | JSON schema matches `scan_results.json` contract | unit | `pytest tests/test_scan_signal_buckets.py::TestScanResultsJson::test_json_schema -x` | NO — Wave 0 |
| GATE-01 | Signal scan only runs after PASS/WARN gate | integration | `pytest tests/test_scan_gate.py -k signal -x` | NO — Wave 0 |
| TST-01 | `--run --format json` includes `scan_results.json` | integration | `pytest tests/test_scan_signal_buckets.py::TestCliIntegration::test_scan_results_json_written -x` | NO — Wave 0 |

### Sampling Rate
- **Per task commit:** `cd agent && python -m pytest tests/test_scan_signal_buckets.py -x -q`
- **Per wave merge:** `cd agent && python -m pytest tests/ -q --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `agent/tests/test_scan_signal_buckets.py` — covers SIG-01, SIG-02, GATE-01, TST-01
- [ ] `agent/src/data/scan_signal_buckets.py` — covers SIG-01, SIG-02
- [ ] `agent/tests/conftest.py` — shared fixtures for scan test data (ohlcv DataFrame factory, mock parquet paths)
- Framework install: already present (pytest detected)

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

---

## Security Domain

> Required when `security_enforcement` is enabled (absent = enabled). Omit only if explicitly `false` in config.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — local scan tool, no auth |
| V3 Session Management | no | N/A — stateless CLI |
| V4 Access Control | yes | Path traversal prevention via `resolve_cache_file()` (already in `watchlist_data_health.py`) |
| V5 Input Validation | yes | CSV rows validated by `validate_watchlist()`; parquet validated by `read_local_parquet()`; `CompositeTrendStrategy.validate()` for OHLCV columns |
| V6 Cryptography | no | N/A — read-only local files |

### Known Threat Patterns for Python/Data Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via watchlist symbol | Tampering | `resolve_cache_file()` normalizes paths under `data_dir`; watchlist CSV already validated |
| Malformed parquet causing crashes | Denial of Service | `read_local_parquet()` catches all exceptions; failed symbol goes to `failed` bucket |
| Unbounded memory from large parquet | Denial of Service | Process one symbol at a time; use `pyarrow` streaming if needed |
| JSON injection in symbol results | Tampering | `TradingSignal.to_dict()` uses typed dataclass, not string formatting |

---

## Sources

### Primary (HIGH confidence)
- `agent/src/strategies/composite/base.py` — TradingSignal dataclass definition, verified by reading file
- `agent/src/strategies/composite/trend_composite.py` — CompositeTrendStrategy.analyze(), verified by reading file
- `agent/src/strategies/trend/base.py` — TrendStrategyBase, TrendResult, verified by reading file
- `agent/src/data/watchlist_data_health.py` — read_local_parquet(), resolve_cache_file(), verified by reading file
- `agent/cli/commands/scan.py` — Phase 12-13 scan CLI, verified by reading file

### Secondary (MEDIUM confidence)
- `agent/tests/strategies/test_composite_trend_strategy.py` — Test patterns for TradingSignal/CompositeTrendStrategy
- `agent/tests/test_scan_gate.py` — Test patterns for scan CLI integration

### Tertiary (LOW confidence)
- [ASSUMED] Bucket confidence thresholds (0.45 actionable, 0.25 watch floor) — based on training knowledge of typical signal confidence distributions; planner should verify or make configurable

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies are existing project code
- Architecture: HIGH — `TradingSignal` contract is canonical and stable
- Pitfalls: HIGH — derived from `TradingSignal` semantics and existing codebase patterns

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (30 days — stable domain with established contracts)
