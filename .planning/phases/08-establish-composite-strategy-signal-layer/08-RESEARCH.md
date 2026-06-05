# Phase 08: Establish Composite Strategy Signal Layer - Research

**Researched:** 2026-06-05  
**Domain:** Python trading-strategy contract design, canonical signal composition, deterministic pytest contract testing [VERIFIED: codebase]  
**Confidence:** HIGH for internal contract/test patterns; MEDIUM for provisional composition defaults because final weighting remains a user-deferred design choice [VERIFIED: codebase] [CITED: 08-CONTEXT.md]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Signal Contract

- **D-01: Direction semantics** — `TradingSignal.direction` uses `BULL / BEAR / NEUTRAL`.
  - Do **not** make `LONG / SHORT / WAIT` or `BUY / SELL / HOLD` the primary direction field in this phase.
  - Execution-specific actions can be derived later by signal execution / backtest adapters from `direction + readiness`.

- **D-02: Separate technical validity from trade readiness** — `TradingSignal` should preserve two status layers:
  - `status`: technical validity / consumability, aligned with existing `TrendResult.status` semantics such as `VALID / NO_SIGNAL / FILTERED / INVALID`.
  - `readiness`: execution readiness, recommended values `READY / WAIT / BLOCKED / EXHAUSTED / UNKNOWN`.
  - Rationale: this keeps “invalid data or failed strategy” separate from “valid signal but not ready to trade.”

- **D-03: Core scoring contract** — use a minimal stable score contract:
  - `signal_score: float` in `-100 ~ +100`, carrying signed directional strength.
  - `confidence: float` in `0.0 ~ 1.0`.
  - `components: dict[str, float]` for strategy contributions such as `mtes_v3`, `mtes_v2`, `enhanced_supertrend`, or future `confluence`.
  - Do not require a top-level `confluence_score` in v0.1; it can live in `components` or `metadata` until the composition algorithm is locked.

- **D-04: Standard explainability fields** — `TradingSignal` should include enough structure for reports, tests, and MCP/tool output:
  - `reasons: list[str]`
  - `warnings: list[str]`
  - `components: dict[str, float]`
  - `source_results: dict[str, Any]` or equivalent serializable source summary
  - `metadata: dict[str, Any]`
  - Avoid storing heavy or non-serializable raw objects as required public fields.

### Claude's Discretion
The user delegated these choices to Claude:

- Whether to include both `status` and `readiness`: decision is yes, because existing `TrendResult` already distinguishes these concepts.
- How to organize score fields: decision is minimal top-level `signal_score + confidence`, with `components`/`metadata` for extension.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- `LONG / SHORT / WAIT`, `BUY / SELL / HOLD`, order sizing, stop-loss, and take-profit semantics belong to execution adapters or later signal execution phases, not the primary Phase 8 direction contract.
- Full composition algorithm choices such as weighted voting, gate-first, leader/follower, or confluence thresholds were not discussed yet. Planner/researcher may propose a minimal implementation, but if the choice is high-impact, ask before locking it.
- Broad MCP/tool/CLI exposure is not locked by this context. Start with the Python contract unless planning finds a simple existing integration point.
</user_constraints>

## Summary

Phase 08 should be planned as a contract-first Python implementation under `agent/src/strategies/`, not as a rewrite of existing trend analyzers or as an execution/order layer. [CITED: 08-CONTEXT.md] The existing canonical upstream contract is `TrendResult`/`TrendStrategyBase`, with `direction`, `confidence`, signed score, technical `status`, `readiness`, `components`, `warnings`, `metadata`, deterministic validation, exception normalization, and `to_dict()` serialization already established. [VERIFIED: codebase]

The main planning move is to introduce a composite namespace such as `agent/src/strategies/composite/` with a frozen `TradingSignal` dataclass, Literal-based public enums, clamp helpers, readiness/status mapping from `TrendResult`, and focused pytest coverage that mirrors the existing trend-adapter tests. [VERIFIED: codebase] The first implementation should accept already-normalized `TrendResult` objects and/or injected `TrendStrategyBase` adapters, serialize source summaries via `TrendResult.to_dict()`, and avoid raw analyzer objects in the public result. [VERIFIED: codebase] [CITED: 08-CONTEXT.md]

**Primary recommendation:** Plan Wave 1 to lock `TradingSignal` + helpers + tests, then Wave 2 to implement a minimal deterministic trend-result composer using existing `EnhancedSuperTrendStrategy`, `MTESv2TrendStrategy`, and `MTESv3TrendStrategy` as injectable sources; do not expose `LONG/SHORT/WAIT` as the primary signal direction in this phase. [CITED: 08-CONTEXT.md] [VERIFIED: codebase]

## Project Constraints (from CLAUDE.md)

`./CLAUDE.md` was not present in the active worktree; project instructions were provided from `/Users/iagent/projects/CLAUDE.md` in the session context. [VERIFIED: codebase] The planner should honor these directives: Python projects follow PEP 8, use type hints, require function/class docstrings, target test coverage above 80%, use pytest, and use black formatting. [CITED: /Users/iagent/projects/CLAUDE.md] Git commits use `<type>: <description>` with types such as `feat`, `fix`, `refactor`, `test`, and `docs`. [CITED: /Users/iagent/projects/CLAUDE.md] Code review expectations include surgical changes, avoiding over-engineering, keeping solutions simple, and testing before implementation. [CITED: /Users/iagent/projects/CLAUDE.md] Security constraints prohibit committing sensitive information and require `.env` for configuration/secrets. [CITED: /Users/iagent/projects/CLAUDE.md]

## Project Skills

No `.claude/skills/` or `.agents/skills/` directory exists in the active worktree, so no project-local skill rules were loaded for this research. [VERIFIED: codebase] The repository does package many runtime skills under `agent/src/skills/`, but the GSD project-skill discovery rule only targets `.claude/skills/` and `.agents/skills/` for planning-context rules. [VERIFIED: codebase] [CITED: project-skills-discovery.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Composite signal contract | API / Backend | — | The contract is Python dataclass/domain code consumed by tests, backtests, reports, and later adapters. [VERIFIED: codebase] |
| Trend evidence gathering | API / Backend | Database / Storage | Existing `TrendStrategyBase` adapters consume pandas OHLC data and return `TrendResult`; storage/data loaders are upstream and out of scope. [VERIFIED: codebase] |
| Composition/scoring | API / Backend | — | Score aggregation belongs beside strategy adapters under `agent/src/strategies/`, not frontend or execution modules. [CITED: 08-CONTEXT.md] |
| Execution translation | API / Backend | — | Existing execution semantics use `TradeDirection.LONG/SHORT` in `agent/src/analysis/signal_executor.py`; this phase must defer that translation. [VERIFIED: codebase] [CITED: 08-CONTEXT.md] |
| Reporting/tool serialization | API / Backend | Browser / Client | `to_dict()` should provide machine-readable payloads for later reports/MCP/UI, while UI exposure is not locked in Phase 08. [VERIFIED: codebase] [CITED: 08-CONTEXT.md] |

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Python | `>=3.11` declared | Domain contracts, dataclasses, typing, strategy code. [CITED: pyproject.toml] | The project package requires Python `>=3.11`. [CITED: pyproject.toml] |
| `dataclasses` | stdlib | Frozen result contracts. [VERIFIED: codebase] | Existing `TrendResult`, `TrendStrategyConfig`, and strategy configs use dataclasses. [VERIFIED: codebase] |
| `typing.Literal` | stdlib | Public enum-like string contracts for direction/status/readiness. [VERIFIED: codebase] | Existing trend contract uses Literal aliases for direction/status/readiness. [VERIFIED: codebase] |
| `pandas` | `>=2.0.0` declared | OHLC input DataFrame contract. [VERIFIED: codebase] | Existing `TrendStrategyBase.analyze()` and tests accept pandas DataFrames. [VERIFIED: codebase] |
| `pytest` | `>=7.0` declared in dev extra | Focused contract and adapter tests. [VERIFIED: codebase] | Existing strategy tests are pytest tests using fixtures/fakes and `pytest.approx`. [VERIFIED: codebase] |

### Supporting

| Library / Module | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| Existing `src.strategies.trend` | repo-local | Upstream trend evidence. [VERIFIED: codebase] | Use `TrendResult`, `TrendStrategyBase`, and existing concrete adapters as source inputs. [VERIFIED: codebase] |
| Existing `src.analysis.signal_executor` | repo-local | Later execution translation boundary. [VERIFIED: codebase] | Do not depend on it for the primary Phase 08 contract; use it only as a boundary reference. [CITED: 08-CONTEXT.md] [VERIFIED: codebase] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Frozen dataclass `TradingSignal` | Pydantic `BaseModel` | Pydantic is available in the project, but existing strategy-domain result contracts use dataclasses; introducing Pydantic would add an unnecessary dependency boundary for this internal contract. [VERIFIED: codebase] |
| String Literal aliases | `Enum` classes | Existing trend adapter public contract uses Literals, while MTES v3 internal base uses Enums for lower-level analyzer concepts; matching `TrendResult` avoids adapter friction. [VERIFIED: codebase] |
| Equal/provided weighted average v0.1 | Gate-first or leader/follower algorithm | Full composition algorithm choice is explicitly deferred; a transparent provisional aggregator is safer for contract stabilization. [CITED: 08-CONTEXT.md] [ASSUMED] |

**Installation:**

No new external package installation is recommended for Phase 08. [VERIFIED: codebase]

```bash
# None — use existing Python stdlib, pandas, pytest, and repo-local strategy modules.
```

## Architecture Patterns

### Recommended Project Structure

```text
agent/src/strategies/
├── trend/                  # existing canonical trend adapters
└── composite/              # new Phase 08 namespace
    ├── __init__.py         # lightweight exports
    ├── base.py             # TradingSignal, aliases, clamp helpers, readiness/status mapping
    └── trend_composite.py  # minimal injectable composer over TrendResult/TrendStrategyBase

agent/tests/strategies/
├── test_composite_signal_base.py
└── test_composite_trend_strategy.py
```

### Pattern 1: Contract-First Frozen Dataclass

**What:** Define `TradingSignal` as a frozen dataclass with Literal aliases and `to_dict()`, mirroring `TrendResult`. [VERIFIED: codebase]  
**When to use:** Use for stable public outputs consumed by tests, reports, watchlist analysis, and later execution adapters. [CITED: 08-CONTEXT.md]

### Pattern 2: Adapter/Composer Lifecycle

**What:** Keep the fixed lifecycle from `TrendStrategyBase`: validate input, call sources, normalize/clamp, post-check status, return canonical object, and convert exceptions into invalid results. [VERIFIED: codebase]  
**When to use:** Use for a composite class that calls injected trend strategies. [VERIFIED: codebase]

### Pattern 3: Serializable Source Summaries

**What:** Store `source_results` as dictionaries from `TrendResult.to_dict()`, not raw analyzer objects. [VERIFIED: codebase] [CITED: 08-CONTEXT.md]  
**When to use:** Use whenever exposing source evidence in `TradingSignal`. [CITED: 08-CONTEXT.md]

### Anti-Patterns to Avoid

- **Making `TradingSignal.direction` execution-oriented:** `LONG/SHORT/WAIT` is explicitly deferred and already exists in execution-oriented code; keep Phase 08 direction as `BULL/BEAR/NEUTRAL`. [CITED: 08-CONTEXT.md] [VERIFIED: codebase]
- **Leaking source `NOT_READY` into public `TradingSignal.readiness`:** Existing trend readiness includes `NOT_READY`, but Phase 08 user context recommends `WAIT/BLOCKED` for the public signal layer; map it deliberately. [VERIFIED: codebase] [CITED: 08-CONTEXT.md]
- **Persisting raw pandas DataFrames or analyzer objects in `source_results`:** The user explicitly asked for serializable summaries and avoidance of heavy raw objects. [CITED: 08-CONTEXT.md]
- **Over-locking a sophisticated alpha algorithm:** Full weighted voting/gate-first/leader-follower choices are deferred; keep v0.1 composition transparent and testable. [CITED: 08-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Input OHLC validation | A new validation system for OHLC columns/min bars | Existing `TrendStrategyBase.validate()` through source adapters | Source adapters already normalize invalid input into canonical invalid `TrendResult`. [VERIFIED: codebase] |
| Trend analysis | Reimplementation of MTES v2/v3 or Enhanced SuperTrend | Existing `EnhancedSuperTrendStrategy`, `MTESv2TrendStrategy`, `MTESv3TrendStrategy` | Phase 08 is a composition layer over existing adapters. [CITED: 08-CONTEXT.md] [VERIFIED: codebase] |
| Numeric clamping | New ad-hoc score bounds logic | Existing clamp pattern from `clamp_confidence` and `clamp_signed_score`; add signal-specific helpers only if names differ | Existing code clamps non-finite values to zero and bounds confidence/score. [VERIFIED: codebase] |
| Execution instructions | New order sizing / stop-loss / take-profit model | Existing later execution module or future adapter | Execution semantics are explicitly deferred, and current execution code already models `TradeInstruction`. [CITED: 08-CONTEXT.md] [VERIFIED: codebase] |
| Serialization | Custom JSON encoders over raw objects | `to_dict()` on dataclasses/source summaries | Existing result objects expose `to_dict()` and tests expect serializable metadata. [VERIFIED: codebase] |

**Key insight:** The implementation risk is not missing infrastructure; it is semantic drift between research direction (`BULL/BEAR/NEUTRAL`), technical status (`VALID/NO_SIGNAL/FILTERED/INVALID`), readiness (`READY/WAIT/BLOCKED/EXHAUSTED/UNKNOWN`), and execution actions (`LONG/SHORT/WAIT`). [CITED: 08-CONTEXT.md] [VERIFIED: codebase]

## Common Pitfalls

### Pitfall 1: Conflating Signal Direction with Trade Action

**What goes wrong:** The composite layer emits `LONG` or `SHORT` as `TradingSignal.direction`. [CITED: 08-CONTEXT.md]  
**Why it happens:** Existing MTES v3 internal `EntrySignal` and Phase 04 execution code already use `LONG/SHORT/WAIT`. [VERIFIED: codebase]  
**How to avoid:** Keep `TradingSignal.direction` as `BULL/BEAR/NEUTRAL`; if a later adapter needs action semantics, derive action from `direction + readiness`. [CITED: 08-CONTEXT.md]  
**Warning signs:** Tests assert `signal.direction == "LONG"` or import `TradeDirection` in composite-layer tests. [VERIFIED: codebase]

### Pitfall 2: Treating Invalid Data as Merely Not Ready

**What goes wrong:** Invalid source inputs become `WAIT`, losing the distinction between unusable evidence and valid-but-not-actionable evidence. [CITED: 08-CONTEXT.md]  
**Why it happens:** Existing source adapters return `TrendResult(status="INVALID", readiness="UNKNOWN")` on validation failure/exceptions. [VERIFIED: codebase]  
**How to avoid:** Preserve `status` separately and map readiness to `BLOCKED` or `UNKNOWN` for invalid/exceptional source sets. [CITED: 08-CONTEXT.md] [ASSUMED]

### Pitfall 3: Testing with Real Analyzers Instead of Fakes First

**What goes wrong:** Phase 08 tests become slow/flaky and fail for data/analyzer reasons unrelated to the contract. [VERIFIED: codebase]  
**How to avoid:** Follow existing strategy tests: build deterministic fake indicators/evaluators and small OHLC DataFrames. [VERIFIED: codebase]

### Pitfall 4: Over-committing the First Composition Algorithm

**What goes wrong:** The plan spends Phase 08 optimizing weighted voting or confluence logic instead of stabilizing the public result contract. [CITED: 08-CONTEXT.md]  
**How to avoid:** Use a minimal deterministic aggregator for v0.1 and capture algorithm refinements as deferred decisions. [CITED: 08-CONTEXT.md]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` has `[tool.pytest.ini_options]` with `testpaths = ["agent/tests"]` and `pythonpath = ["agent"]`. |
| Quick run command | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py agent/tests/strategies/test_composite_trend_strategy.py -q` |
| Full suite command | `.venv/bin/python -m pytest agent/tests/strategies -q` |

### Phase Requirements → Test Map

No formal Phase 08 requirement IDs were present in `.planning/REQUIREMENTS.md`; existing requirements only document `REQ-001` for Phase 07. [VERIFIED: codebase]

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PH08-CONTRACT | `TradingSignal` exposes direction/status/readiness/score/confidence/components/reasons/warnings/source_results/metadata and serializes via `to_dict()`. | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` | ❌ Wave 0 |
| PH08-CLAMP | Non-finite/out-of-range `signal_score` and `confidence` clamp to public ranges. | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` | ❌ Wave 0 |
| PH08-MAP | Source `TrendResult` status/readiness maps into separate `TradingSignal.status` and `TradingSignal.readiness`. | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_trend_strategy.py -q` | ❌ Wave 0 |
| PH08-SERIAL | `source_results` stores serializable source summaries, not raw analyzers/DataFrames. | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_trend_strategy.py -q` | ❌ Wave 0 |
| PH08-DEFER-EXEC | Composite tests reject primary direction values `LONG/SHORT/WAIT`. | unit | `.venv/bin/python -m pytest agent/tests/strategies/test_composite_signal_base.py -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest agent/tests/strategies/test_trend_base.py agent/tests/strategies/test_composite_signal_base.py agent/tests/strategies/test_composite_trend_strategy.py -q`
- **Per wave merge:** `.venv/bin/python -m pytest agent/tests/strategies -q`
- **Phase gate:** run full backend suite or documented project suite before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `agent/tests/strategies/test_composite_signal_base.py` — covers PH08-CONTRACT, PH08-CLAMP, PH08-DEFER-EXEC.
- [ ] `agent/tests/strategies/test_composite_trend_strategy.py` — covers PH08-MAP and PH08-SERIAL.
- [ ] `agent/src/strategies/composite/base.py` — new public contract module.
- [ ] `agent/src/strategies/composite/trend_composite.py` — new minimal composer module if Wave 2 is included.

## Security Domain

Security domain is included because no config explicitly disables security enforcement.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth boundary changes in Phase 08. |
| V3 Session Management | no | No session state changes in Phase 08. |
| V4 Access Control | no | No user/permission boundary changes in Phase 08. |
| V5 Input Validation | yes | Reuse source adapter validation for OHLC input and validate/clamp public score/confidence fields. |
| V6 Cryptography | no | No cryptographic operations in Phase 08. |

### Known Threat Patterns for Python Trading Signal Contract

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Non-finite numeric poisoning (`NaN`, `inf`) in score/confidence | Tampering | Clamp non-finite values to safe defaults, matching existing trend helpers. |
| Heavy object leakage through `source_results` | Information Disclosure | Store `to_dict()` summaries only; avoid raw DataFrames/analyzers. |
| Semantic spoofing between direction and execution action | Tampering | Type/test direction as `BULL/BEAR/NEUTRAL` and defer `LONG/SHORT/WAIT`. |
| Unhandled source exceptions breaking composite output | Denial of Service | Normalize exceptions into invalid source/composite results as `TrendStrategyBase.analyze()` already does. |

## Sources

- `.planning/phases/08-establish-composite-strategy-signal-layer/08-CONTEXT.md` — locked user decisions and deferred scope.
- `.planning/ROADMAP.md` — Phase 08 roadmap entry.
- `.planning/STATE.md` — phase history.
- `.planning/codebase/STACK.md` — stack and dependency context.
- `.planning/codebase/INTEGRATIONS.md` — integration context.
- `agent/src/strategies/trend/base.py` — canonical upstream contract.
- `agent/src/strategies/trend/enhanced_supertrend.py` — existing source adapter.
- `agent/src/strategies/trend/mtes_v2.py` — existing source adapter.
- `agent/src/strategies/trend/mtes_v3.py` — existing source adapter.
- `agent/tests/strategies/test_trend_base.py`, `test_enhanced_supertrend_strategy.py`, `test_mtes_v2_trend_strategy.py`, `test_mtes_v3_trend_strategy.py` — focused pytest patterns.
- `agent/src/analysis/signal_executor.py` and `agent/tests/test_signal_executor.py` — execution boundary reference.
- `pyproject.toml` — package requirements and pytest config.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH
- Architecture: HIGH
- Pitfalls: HIGH for direction/status/readiness boundary, MEDIUM for readiness mapping details
- Validation: MEDIUM

**Research date:** 2026-06-05  
**Valid until:** 2026-07-05 for contract/test architecture; revisit sooner if Phase 08 discussion changes composition algorithm or readiness mapping.
