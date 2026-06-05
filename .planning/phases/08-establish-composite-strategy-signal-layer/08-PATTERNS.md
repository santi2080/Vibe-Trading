# Phase 08: Establish Composite Strategy Signal Layer - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 5 new/modified files
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agent/src/strategies/composite/__init__.py` | config | transform | `agent/src/strategies/trend/__init__.py` | exact |
| `agent/src/strategies/composite/base.py` | model, utility | transform | `agent/src/strategies/trend/base.py` | exact |
| `agent/src/strategies/composite/trend_composite.py` | service | transform, request-response | `agent/src/strategies/trend/mtes_v3.py` + `agent/src/strategies/trend/base.py` | role-match |
| `agent/tests/strategies/test_composite_signal_base.py` | test | transform | `agent/tests/strategies/test_trend_base.py` | exact |
| `agent/tests/strategies/test_composite_trend_strategy.py` | test | transform, request-response | `agent/tests/strategies/test_mtes_v3_trend_strategy.py` + `agent/tests/strategies/test_mtes_v2_trend_strategy.py` | role-match |

## Pattern Assignments

### `agent/src/strategies/composite/__init__.py` (config, transform)

**Analog:** `agent/src/strategies/trend/__init__.py`

Apply: export `TradingSignal`, Literal aliases, clamp helpers, and lazy-import concrete composite class if needed. Keep concrete composer imports lazy to avoid importing trend analyzers during base-contract imports.

---

### `agent/src/strategies/composite/base.py` (model, utility, transform)

**Analog:** `agent/src/strategies/trend/base.py`

Apply: define `TradingSignal` as a frozen dataclass with `direction`, `confidence`, `signal_score`, `status`, `readiness`, `reasons`, `warnings`, `components`, `source_results`, and `metadata`. Preserve `BULL/BEAR/NEUTRAL` for direction. Add `to_dict()`, `is_valid`, and an execution-readiness convenience property if useful. Reuse the non-finite-to-zero and bounded-range clamp behavior.

Key source patterns:

```python
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal
```

```python
@dataclass(frozen=True)
class TrendResult:
    direction: TrendDirection
    confidence: float
    signed_score: float
    status: TrendStatus = "VALID"
    readiness: Readiness = "UNKNOWN"
    components: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

```python
def clamp_confidence(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))
```

---

### `agent/src/strategies/composite/trend_composite.py` (service, transform/request-response)

**Primary analogs:**
- `agent/src/strategies/trend/base.py` for lifecycle, validation, exception normalization, clamp/post-check behavior.
- `agent/src/strategies/trend/mtes_v3.py` and `agent/src/strategies/trend/mtes_v2.py` for injected source adapters, analyzer calls, normalization into canonical dataclasses, components, and metadata.

Apply: composite class should accept injected `TrendStrategyBase` sources, call `source.analyze(df)` for each, collect `TrendResult.to_dict()` into `source_results`, aggregate signed scores into `signal_score`, clamp public numeric fields, and preserve invalid/no-signal/filter distinctions. If source adapters already validate OHLC and normalize exceptions, avoid duplicating analyzer internals.

Use the existing analyze lifecycle pattern:

```python
def analyze(self, df: pd.DataFrame) -> TrendResult:
    ok, reason = self.validate(df)
    if not ok:
        return TrendResult(direction="NEUTRAL", confidence=0.0, signed_score=0.0, status="INVALID")
    try:
        raw = self._analyze_raw(df)
        result = self._normalize(raw, df)
        result = self._clamp_result(result)
        result = self._post_check(result, df)
        return self._ensure_explanation(result, raw, df)
    except Exception as exc:
        return TrendResult(direction="NEUTRAL", confidence=0.0, signed_score=0.0, status="INVALID")
```

---

### `agent/tests/strategies/test_composite_signal_base.py` (test, transform)

**Analog:** `agent/tests/strategies/test_trend_base.py`

Apply: add focused tests for `TradingSignal.to_dict()`, public direction values `BULL/BEAR/NEUTRAL`, separate `status` and `readiness`, `signal_score` clamp behavior, `confidence` clamp behavior, and explicit rejection/absence of `LONG/SHORT/WAIT` as primary direction values.

Use deterministic fixture style:

```python
def make_ohlcv(length: int = 20) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series(range(100, 100 + length), index=index, dtype="float64")
    return pd.DataFrame({"open": close - 0.2, "high": close + 1.0, "low": close - 1.0, "close": close}, index=index)
```

---

### `agent/tests/strategies/test_composite_trend_strategy.py` (test, transform/request-response)

**Analogs:**
- `agent/tests/strategies/test_mtes_v3_trend_strategy.py`
- `agent/tests/strategies/test_mtes_v2_trend_strategy.py`
- `agent/tests/strategies/test_enhanced_supertrend_strategy.py`

Apply: build fake trend sources whose `analyze(df)` returns `TrendResult`. Assert every source is called exactly once, composite output uses `TradingSignal.direction`, `signal_score`, `confidence`, `status`, `readiness`, and `source_results` as serializable dictionaries. Test invalid, filtered, no-signal, exhausted, and mixed-direction source sets with deterministic expected outcomes.

## Shared Patterns

### Contract-First Frozen Dataclasses

Use frozen dataclasses, Literal aliases, default `field(default_factory=...)` for mutable collections, and explicit `to_dict()` serialization. Do not use Pydantic or raw object serialization for this phase.

### Numeric Safety / Clamping

Use the same non-finite handling for `TradingSignal.signal_score` and `TradingSignal.confidence` as `TrendResult` uses for score/confidence.

### Source Adapter Lifecycle and Exception Normalization

Composite logic should not let one source exception crash the public signal layer. Existing source adapters already return canonical invalid `TrendResult` on validation/exception; if a composite wrapper calls arbitrary injected sources, normalize unexpected exceptions into invalid source summaries and an invalid or blocked composite result.

### Serializable Source Summaries

Use `TrendResult.to_dict()` or equivalent small dictionaries in `source_results`. Do not store raw analyzers, fake source objects, pandas DataFrames, or MTES native result objects in public `TradingSignal` fields.

### Execution Boundary / Do Not Copy for Phase 08 Direction

Do not import `TradeDirection` or emit `LONG/SHORT/WAIT` as `TradingSignal.direction` in Phase 08. `agent/src/analysis/signal_executor.py` is a later execution boundary reference only.

### Test Style

Tests are small, deterministic pytest functions with fake source objects, `make_ohlcv()` helpers, explicit field assertions, and `pytest.approx` for floats. Follow existing file naming under `agent/tests/strategies/`.

## No Analog Found

No file lacks a usable codebase analog. The repository has no exact existing composite-strategy aggregator, so `agent/src/strategies/composite/trend_composite.py` should combine the role-match patterns from `TrendStrategyBase` and concrete trend adapters rather than copying a nonexistent composite implementation.

## Metadata

**Analog search scope:** `agent/src/strategies/`, `agent/tests/strategies/`, `agent/src/analysis/signal_executor.py`, `agent/tests/test_signal_executor.py`  
**Files scanned:** 12 listed/read candidate files plus Phase 08 context/research  
**Pattern extraction date:** 2026-06-05
