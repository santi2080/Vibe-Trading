# Phase 11: Symbol Format Mapping Contract & Data Source Translation Optimization - Research

**Researched:** 2026-06-08
**Domain:** Internal symbol-format contract, data-source translation boundaries, routing/fallback behavior
**Confidence:** HIGH for codebase findings; MEDIUM for vendor-format recommendations that require optional live smoke.

## User Constraints (from 11-CONTEXT.md)

### Locked Decisions

- **D-01:** Canonical symbols are user-facing and stable. Vendor-specific symbols are boundary-only and must not leak into watchlists/run plans/output keys. [VERIFIED: 11-CONTEXT.md]
- **D-02:** Recommended canonical examples: A-share/ETF `600036.SH`, US equity `AAPL.US`, HK equity `0700.HK` or `00700.HK`, US futures `GC=F`, CN futures `rb0`/`IF2406`, crypto `BTC-USDT`, forex `EURUSD`. [VERIFIED: 11-CONTEXT.md]
- **D-03:** Unsupported market/vendor combinations should be explicit, not silently suffix-stripped or coerced. [VERIFIED: 11-CONTEXT.md]
- **D-04:** `SymbolTranslator` should become the documented canonical-to-vendor mapping contract. [VERIFIED: 11-CONTEXT.md]
- **D-05:** Loader compatibility shims may remain, but duplicate conversion logic should delegate to `SymbolTranslator` or be covered by contract tests. [VERIFIED: 11-CONTEXT.md]
- **D-06:** `HybridDataFetcher.fetch()` should translate before vendor fetch and map results back to canonical keys. [VERIFIED: 11-CONTEXT.md]
- **D-07:** Direct loaders (`akshare_loader`, `yfinance_loader`, `tqsdk_loader`) must preserve direct-use behavior with canonical inputs. [VERIFIED: 11-CONTEXT.md]
- **D-08/D-10:** Required verification must be mock/focused tests; live provider calls are optional because yfinance proxy availability is environment-dependent. [VERIFIED: 11-CONTEXT.md]

### Out of Scope

Daily scan CLI/run plan, remote refresh modes, data-health gate execution, strategy scanning, Markdown reporting, scheduling, yfinance proxy remediation, and TqSdk async cleanup are deferred to later phases. [VERIFIED: 11-CONTEXT.md]

## Project Constraints

- Do not modify source code during research. [VERIFIED: user request]
- Python changes must use type hints, pytest, black-compatible style, and targeted verification before claiming completion. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Keep changes surgical: every implementation-line change must trace to SYM-01/SYM-02/SYM-03. [VERIFIED: /Users/iagent/projects/CLAUDE.md]
- Sensitive config/API keys must stay in environment variables, not code or docs. [VERIFIED: /Users/iagent/projects/CLAUDE.md]

## Summary

Phase 11 is an internal contract-cleanup prerequisite for v2.2 daily scan. The codebase already has a central `SymbolTranslator`, `SymbolRouter`, loader fallback chains, and direct loader-local symbol conversion; however, these responsibilities are not consistently enforced at a single boundary. [VERIFIED: codebase]

The main architectural gap is that `HybridDataFetcher.fetch()` groups canonical request symbols by market and calls `SourcePool.fetch(source, market_symbols, ...)` with the original canonical symbols, despite `SymbolRouter.translate_symbol()` existing. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`] This means the central translator is not the enforced boundary and loader-local conversions continue to define the actual vendor calls. [VERIFIED: codebase]

**Primary recommendation:** Add focused contract tests first, make `SymbolTranslator` the canonical-to-vendor authority with explicit unsupported combinations, then update fetch/routing boundaries to translate vendor calls while remapping all successful and unresolved results back to canonical keys. [VERIFIED: codebase]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Canonical symbol normalization | Data contract layer (`agent/src/data/symbol_translator.py`) | Market detection helpers | One stable user-facing key must feed watchlists, configs, run plans, cache keys, and output keys. [VERIFIED: 11-CONTEXT.md] |
| Vendor symbol translation | Data-source boundary | Direct loaders as compatibility shims | Vendor-specific symbols belong only at loader/API boundaries. [VERIFIED: 11-CONTEXT.md] |
| Fallback routing | Loader registry / `HybridDataFetcher` | Runner auto mode | Fallback must operate on canonical requested symbols but call loaders with vendor symbols. [VERIFIED: codebase] |
| Unresolved symbol reporting | Caller-facing tool/fetch result layer | Loader results | Missing symbols must stay visible under canonical keys, matching existing `_unresolved` behavior. [VERIFIED: `agent/mcp_server.py`] |

## Current Architecture

### Central translator

- `agent/src/data/symbol_translator.py` defines `DataVendor` for Yahoo Finance, TwelveData, AKShare, iTick, Tushare, Quandl, AlphaVantage, TqSdk, and Databento. It does not currently define OKX or CCXT vendors. [VERIFIED: `agent/src/data/symbol_translator.py`]
- The translator docstring states internal A-share canonical format is six digits and HK canonical format is five digits, which conflicts with current project usage of suffixed symbols such as `600036.SH` and `0700.HK`/`00700.HK`. [VERIFIED: `agent/src/data/symbol_translator.py`; `11-CONTEXT.md`]
- Current A-share AKShare translation returns `symbol.replace(".", "")`, so `600036.SH` becomes `600036SH`; the AKShare loader’s actual stock/ETF endpoints use Sina-style `sh600036` / `sz159915`. [VERIFIED: `agent/src/data/symbol_translator.py`; `agent/backtest/loaders/akshare_loader.py`]
- Current HK AKShare translation does `symbol.zfill(5)` without stripping `.HK`, so `00700.HK` is not transformed into the loader endpoint’s `00700` form. [VERIFIED: `agent/src/data/symbol_translator.py`; `agent/backtest/loaders/akshare_loader.py`]
- TqSdk translation already delegates to `SymbolTranslator.to_vendor_format(...)` and tests pin `rb0 -> KQ.m@SHFE.rb`, `i0 -> KQ.m@DCE.i`, `if0 -> KQ.m@CFFEX.IF`, and concrete contract casing. [VERIFIED: `agent/backtest/loaders/tqsdk_loader.py`; `agent/tests/test_tqsdk_loader.py`]

### Hybrid fetcher and routing

- `SymbolRouter` detects markets with regex patterns and has source priorities for A-share, US/HK equity, CN/US futures, crypto, fund, forex, and macro. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`]
- `SymbolRouter.SOURCE_TO_VENDOR` maps AKShare, yfinance, Tushare, TqSdk, and Databento, but not OKX or CCXT. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`]
- `SymbolRouter.translate_symbol()` maps `MarketType` to `Market` and calls `SymbolTranslator.to_vendor_format(...)`. Crypto and forex currently map to `Market.US_STOCK`, relying on default passthrough. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`]
- `HybridDataFetcher.fetch()` routes symbols, groups by market, chooses sources, and calls `self.pool.fetch(source, market_symbols, ...)` with canonical `market_symbols`; it does not call `translate_symbol()` before `pool.fetch()`. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`]
- `SourcePool.fetch()` simply delegates its input `symbols` to the selected loader and returns that loader’s result keys. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`]

### Loader-local conversions

- AKShare direct loader accepts canonical-like inputs and internally detects A-share/ETF/HK/US futures/CN futures/forex, then converts to endpoint formats. [VERIFIED: `agent/backtest/loaders/akshare_loader.py`]
- AKShare A-share stock endpoint converts `600519.SH -> sh600519`; ETF endpoint converts `518880.SH -> sh518880`; HK endpoint converts `.HK` symbols to five-digit numeric codes; US futures converts `GC=F -> GC`; CN futures maps `rb0 -> RB0`. [VERIFIED: `agent/backtest/loaders/akshare_loader.py`]
- yfinance direct loader converts `AAPL.US -> AAPL`, HK suffix symbols to a zero-padded `.HK` symbol, and leaves US futures `=F` symbols unchanged while returning results keyed by original input codes. [VERIFIED: `agent/backtest/loaders/yfinance_loader.py`]
- OKX direct loader normalizes `/` to `-` and uppercases crypto symbols. [VERIFIED: `agent/backtest/loaders/okx.py`]
- CCXT direct loader converts `BTC-USDT -> BTC/USDT` for the vendor call and returns results keyed by the input code. [VERIFIED: `agent/backtest/loaders/ccxt_loader.py`]

### Registry/fallback and unresolved behavior

- Registry fallback chains define A-share `tushare -> akshare`, US equity `yfinance -> akshare`, HK equity `futu -> yfinance -> akshare`, crypto `okx -> ccxt`, CN futures `tqsdk -> tushare -> akshare`, US futures daily/intraday chains, and forex `akshare -> yfinance`. [VERIFIED: `agent/backtest/loaders/registry.py`]
- Runner auto mode groups by shared `_detect_market()`, resolves a loader, optionally normalizes crypto codes for OKX/CCXT, fetches, and runtime-falls back when the primary result is empty. [VERIFIED: `agent/backtest/runner.py`]
- MCP `get_market_data()` preserves missing requested codes in `_unresolved`, and tests require partial loader results and loader exceptions to surface unresolved symbols instead of silently dropping them. [VERIFIED: `agent/mcp_server.py`; `agent/tests/test_get_market_data_unresolved.py`]

## Key Mismatches to Fix

1. **Translator docstring vs actual canonical usage:** the translator documents A-share as six digits and HK as five digits, while Phase 11 and existing tests use suffix forms for user-facing canonical keys. [VERIFIED: `agent/src/data/symbol_translator.py`; `agent/tests/test_market_detection.py`]
2. **AKShare A-share translator output is wrong for loader endpoints:** `600036.SH -> 600036SH` centrally, but loader endpoint expects `sh600036`/`sz000001`. [VERIFIED: `agent/src/data/symbol_translator.py`; `agent/backtest/loaders/akshare_loader.py`]
3. **AKShare HK translator output is wrong for loader endpoints:** central translator can preserve `.HK`, but loader endpoint expects a five-digit numeric string. [VERIFIED: `agent/src/data/symbol_translator.py`; `agent/backtest/loaders/akshare_loader.py`]
4. **Hybrid fetcher never enforces translation:** `HybridDataFetcher.fetch()` sends canonical symbols directly to loaders, so `translate_symbol()` is only a shallow integration utility today. [VERIFIED: `agent/backtest/loaders/hybrid_fetcher.py`; `agent/tests/test_hybrid_fetcher.py`]
5. **Unsupported combinations are implicit passthrough:** `SymbolTranslator.to_vendor_format()` defaults to returning the original symbol and `is_supported_by_vendor()` always returns `True`, which conflicts with D-03. [VERIFIED: `agent/src/data/symbol_translator.py`]
6. **OKX/CCXT missing from central vendor enum:** crypto loaders implement conversion locally, but the central contract cannot express OKX/CCXT vendor formats. [VERIFIED: `agent/src/data/symbol_translator.py`; `agent/backtest/loaders/okx.py`; `agent/backtest/loaders/ccxt_loader.py`]
7. **Market detection is split:** `_market_hooks._detect_market()` and `SymbolRouter.detect_market()` use separate regex tables; they already differ on HK width acceptance and crypto hyphen support. [VERIFIED: `agent/backtest/engines/_market_hooks.py`; `agent/backtest/loaders/hybrid_fetcher.py`]
8. **Vendor translation can break result keys if implemented naively:** direct loaders return results keyed by whatever input they receive, so passing vendor symbols into loaders will return vendor keys unless the fetch boundary remaps them back to canonical keys. [VERIFIED: codebase]

## Recommended Canonical Format Table

Canonical symbols below are the user-facing/cache/output keys. Vendor symbols are boundary-only. Unsupported combinations should return an explicit unsupported result/reason rather than passthrough. [VERIFIED: 11-CONTEXT.md]

| Market / Asset | Canonical normalized key | Tushare | AKShare | yfinance | TqSdk | OKX | CCXT | Databento | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A-share stock | `600036.SH`, `000001.SZ`, `830946.BJ` | same canonical `ts_code` | `sh600036`, `sz000001`, `bj830946` if endpoint supports BJ | unsupported | unsupported | unsupported | unsupported | unsupported | AKShare current code handles SH/SZ; BJ support should be explicit/tested before enabling. [VERIFIED: codebase] |
| CN exchange ETF/LOF | `518880.SH`, `159915.SZ` | same canonical if Tushare endpoint retained | `sh518880`, `sz159915` | unsupported | unsupported | unsupported | unsupported | unsupported | ETF prefixes must route before A-share stock endpoint. [VERIFIED: `agent/backtest/loaders/akshare_loader.py`] |
| US equity / ETF | `AAPL.US`, `SPY.US` | unsupported | `AAPL` plus loader prefix trials `105.`/`106.` | `AAPL`, `SPY` | unsupported | unsupported | unsupported | unsupported | AKShare US prefix trial is loader-specific and may remain a compatibility shim. [VERIFIED: `agent/backtest/loaders/akshare_loader.py`] |
| HK equity | Recommend canonical `00700.HK` (normalize to five digits) | unsupported | `00700` | boundary should emit a tested yfinance HK symbol (`0700.HK` or `00700.HK`) | unsupported | unsupported | unsupported | unsupported | Five-digit canonical avoids duplicate cache keys; yfinance live acceptance needs optional smoke due proxy constraints. [VERIFIED: codebase; ASSUMED: yfinance HK accepted width] |
| US futures continuous | `GC=F`, `CL=F`, `SI=F`, `ZC=F` | unsupported | `GC`, `CL`, `SI`, `ZC` | `GC=F`, `CL=F`, `SI=F`; CBOT aliases should map `C=F -> ZC=F` | unsupported | unsupported | unsupported | `GC.c.0`, `CL.c.0`, `SI.c.0` | Existing Databento map already supports common futures roots. [VERIFIED: `agent/src/data/symbol_translator.py`] |
| CN futures main continuous | `rb0`, `al0`, `ag0`, `if0` | unsupported until a dedicated futures endpoint is proven | `RB0`, `AL0`, `AG0`, `IF0` if endpoint supports | unsupported | `KQ.m@SHFE.rb`, `KQ.m@SHFE.al`, `KQ.m@SHFE.ag`, `KQ.m@CFFEX.IF` | unsupported | unsupported | unsupported | Tushare loader currently calls stock `daily()` for all codes, so CN futures via Tushare should not be silently marked supported. [VERIFIED: `agent/backtest/loaders/tushare.py`] |
| CN futures concrete contract | `IF2406`, `rb2410` | unsupported until dedicated endpoint proven | `IF2406`, `RB2410` if endpoint supports | unsupported | `CFFEX.IF2406`, `SHFE.rb2410` | unsupported | unsupported | unsupported | `_is_china_futures()` already protects bare CN futures routing. [VERIFIED: `agent/tests/test_market_detection.py`] |
| Crypto spot | `BTC-USDT`, `ETH-USDT` | unsupported | unsupported | unsupported | unsupported | `BTC-USDT`, `ETH-USDT` | `BTC/USDT`, `ETH/USDT` | unsupported | Add OKX/CCXT to central vendor enum or explicitly document crypto as loader shim. [VERIFIED: codebase] |
| Forex | `EURUSD` | unsupported | `EURUSD` | unsupported unless a future yfinance forex path is implemented | unsupported | unsupported | unsupported | unsupported | Registry lists yfinance as forex fallback, but yfinance loader does not implement forex-specific conversion. [VERIFIED: `agent/backtest/loaders/registry.py`; `agent/backtest/loaders/yfinance_loader.py`] |

## Implementation Approach

### 1. Contract tests first

Create `agent/tests/test_symbol_translator_contract.py` and pin canonical normalization, canonical-to-vendor outputs, unsupported combinations, and no-mangling behavior. [VERIFIED: 11-CONTEXT.md]

Minimum test matrix:

- `600036.SH -> AKSHARE sh600036`, `000001.SZ -> AKSHARE sz000001`; `600036.SH -> TUSHARE 600036.SH`. [VERIFIED: codebase]
- `518880.SH -> AKSHARE sh518880`, `159915.SZ -> AKSHARE sz159915`. [VERIFIED: codebase]
- `00700.HK -> AKSHARE 00700`; canonical normalization should make `0700.HK` and `00700.HK` resolve to one canonical key. [VERIFIED: 11-CONTEXT.md]
- `AAPL.US -> YAHOO_FINANCE AAPL`; `AAPL.US -> AKSHARE AAPL` or explicit loader-shim marker. [VERIFIED: codebase]
- `GC=F -> AKSHARE GC`, `GC=F -> DATABENTO GC.c.0`, `C=F -> YAHOO_FINANCE ZC=F`. [VERIFIED: `agent/src/data/symbol_translator.py`]
- `rb0 -> TQSDK KQ.m@SHFE.rb`, `if0 -> TQSDK KQ.m@CFFEX.IF`, `RB2405 -> TQSDK SHFE.rb2405`. [VERIFIED: `agent/tests/test_tqsdk_loader.py`]
- `BTC-USDT -> OKX BTC-USDT`, `BTC-USDT -> CCXT BTC/USDT`. [VERIFIED: codebase]
- Unsupported combinations raise/return explicit unsupported status: e.g. `AAPL.US` to TqSdk, `BTC-USDT` to Tushare, `EURUSD` to yfinance unless implemented. [VERIFIED: 11-CONTEXT.md]

### 2. Refactor translator API without breaking direct loaders

Recommended shape:

```python
@dataclass(frozen=True)
class TranslationResult:
    canonical: str
    vendor_symbol: str | None
    supported: bool
    reason: str | None = None
```

Add a new strict method such as `SymbolTranslator.translate(symbol, vendor, market, *, normalize=True) -> TranslationResult`. Keep `to_vendor_format(...) -> str` as a compatibility shim for existing direct loader tests, but make new fetch/routing code use `translate(...)` so unsupported combinations are visible. [VERIFIED: codebase]

### 3. Normalize canonical symbols once

Add `normalize_canonical_symbol(symbol, market_hint=None)` or equivalent so Phase 12 scan plans can reuse the same contract. Recommended normalizations:

- Uppercase suffixes: `.sh -> .SH`, `.hk -> .HK`. [VERIFIED: existing tests cover case-insensitive detection]
- HK to one deterministic width, preferably five digits for canonical cache/output keys: `0700.HK -> 00700.HK`. [ASSUMED: canonical width decision; risk if user prefers four-digit HK display]
- Crypto slash form to hyphen canonical: `BTC/USDT -> BTC-USDT`; reserve slash for CCXT vendor only. [VERIFIED: existing OKX/runner normalization]
- Forex strip optional `.FX`: `EURUSD.FX -> EURUSD`. [VERIFIED: `agent/backtest/loaders/akshare_loader.py`]

### 4. Enforce translation in `HybridDataFetcher.fetch()`

For each market/source batch:

1. Build `canonical_symbols = [normalize(symbol) for symbol in market_symbols]` while retaining original request order. [VERIFIED: 11-CONTEXT.md]
2. For each source, translate only supported canonical symbols into vendor symbols; skip unsupported vendor/market combos and record per-symbol/source errors. [VERIFIED: 11-CONTEXT.md]
3. Call `self.pool.fetch(source, vendor_symbols, ...)`. [VERIFIED: current boundary in `hybrid_fetcher.py`]
4. Remap returned frames back to canonical keys via `vendor_to_canonical`; also accept `raw.get(canonical)` as a compatibility fallback for loaders that keep direct canonical keys. [VERIFIED: direct loaders return input keys]
5. Populate `FetchResult(symbol=canonical, df=..., source=...)` and pass canonical keys into quality/freshness validation. [VERIFIED: `hybrid_fetcher.py`]
6. Preserve output as `{canonical: DataFrame}` only; vendor keys must not escape. [VERIFIED: 11-CONTEXT.md]

### 5. Preserve fallback and unresolved semantics

- Fallback should skip sources whose translation is unsupported for a market/symbol, not call them with plausibly wrong symbols. [VERIFIED: 11-CONTEXT.md]
- Runtime fallback must be tested with a primary returning empty and fallback returning data, ensuring returned keys are canonical. [VERIFIED: `agent/backtest/runner.py`; `agent/backtest/loaders/hybrid_fetcher.py`]
- `get_market_data` unresolved behavior should continue to compare requested canonical symbols against returned canonical result keys; no vendor symbol should appear in `_unresolved`. [VERIFIED: `agent/mcp_server.py`]

### 6. Loader shims: delegate where safe, retain where endpoint-specific

- Move pure deterministic endpoint symbol conversions into `SymbolTranslator` where possible: A-share Sina prefix, ETF Sina prefix, HK numeric, US futures root, CN futures uppercase/main continuous, crypto OKX/CCXT. [VERIFIED: codebase]
- Retain loader endpoint-specific behavior that is not a single deterministic symbol, such as AKShare US prefix trials `105.`/`106.`. Cover it with loader tests rather than pretending the translator can know the correct prefix. [VERIFIED: `agent/backtest/loaders/akshare_loader.py`]
- Direct loaders must still accept canonical inputs after the refactor. Add/keep mocked tests for AKShare/yfinance/TqSdk direct use. [VERIFIED: 11-CONTEXT.md]

## Risks and Mitigations

| Risk | Why It Matters | Mitigation |
|------|----------------|------------|
| Vendor keys leak into output/cache | Phase 12 scan plans and local cache keys must be canonical. [VERIFIED: 11-CONTEXT.md] | Remap every loader result through `vendor_to_canonical`; assert no vendor keys in tests. |
| Translation breaks loaders that already convert internally | Direct loaders currently expect canonical inputs and return input keys. [VERIFIED: codebase] | Preserve direct loader behavior; only `HybridDataFetcher` should pass vendor symbols and remap results. |
| Unsupported combos silently produce wrong symbols | Current `to_vendor_format()` default passthrough and `is_supported_by_vendor()` always true allow silent errors. [VERIFIED: `symbol_translator.py`] | New strict translation result with `supported=False`; tests assert unsupported. |
| HK canonical width decision causes duplicate user/cache keys | Current code/tests accept both `0700.HK` and `00700.HK`. [VERIFIED: codebase] | Pick one normalized canonical representation and preserve display alias only if explicitly needed. |
| yfinance HK live format uncertainty | Live smoke is blocked by `No available proxies`; current yfinance conversion may preserve 5 digits. [VERIFIED: STATE.md; codebase] | Required tests should mock vendor-call symbols; make live HK smoke optional/manual. |
| Market detection remains split | Runner `_detect_market()` and `SymbolRouter.detect_market()` use separate patterns. [VERIFIED: codebase] | Add a small cross-detector compatibility test for Phase 11 canonical examples; defer full unification if out of scope. |
| Tushare CN futures appears in fallback but loader uses stock daily endpoint | Fallback can attempt Tushare for CN futures, but current loader is not CN-futures-aware. [VERIFIED: `tushare.py`; `registry.py`] | Mark CN futures/Tushare unsupported unless a tested futures endpoint is implemented. |
| Cached loader key mismatch | Registry can wrap loaders with `CachedDataLoader`; vendor-symbol fetches may cache under vendor keys. [VERIFIED: `registry.py`] | Phase 11 should at least preserve caller keys; Phase 12 local scan cache must use canonical paths. If remote cache matters, add a cache-key compatibility test. |

## Verification Commands

Required focused tests after implementation:

```bash
PYTHONPATH=agent .venv/bin/python -m pytest -q agent/tests/test_symbol_translator_contract.py
```

Required existing non-network regression suite:

```bash
PYTHONPATH=agent .venv/bin/python -m pytest -q \
  agent/tests/test_market_detection.py \
  agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration \
  agent/tests/test_akshare_loader.py \
  agent/tests/test_tqsdk_loader.py \
  agent/tests/test_registry.py \
  agent/tests/test_get_market_data_unresolved.py \
  agent/tests/test_okx_loader_bounded.py \
  agent/tests/test_ccxt_loader_bounded.py
```

Recommended new/expanded HybridDataFetcher tests:

```bash
PYTHONPATH=agent .venv/bin/python -m pytest -q \
  agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration \
  agent/tests/test_hybrid_fetcher.py::TestHybridDataFetcher
```

Optional manual live smoke only after mock tests pass and network/proxy availability is acceptable:

```bash
PYTHONPATH=agent .venv/bin/python -m pytest -q agent/tests/_smoke_akshare_real.py
```

## Open Questions (RESOLVED)

1. **HK canonical width — RESOLVED:** Phase 11 locks the canonical output/cache key to five-digit `.HK`, so `0700.HK` and `00700.HK` normalize to `00700.HK`. yfinance vendor-call width can be mapped separately and verified by offline mocks; optional live smoke is not a completion gate.
2. **Tushare CN futures support — RESOLVED:** Phase 11 marks Tushare/CN futures unsupported unless a dedicated, tested Tushare futures endpoint already exists. Current `tushare.py` stock `daily()` path must not be used for `rb0`/`IF2406`.
3. **Unified detector scope — RESOLVED:** Phase 11 adds cross-detector compatibility tests for canonical examples only. Full unification of `_market_hooks._detect_market()` and `SymbolRouter.detect_market()` is deferred unless those tests prove a direct SYM-01/SYM-03 blocker.

## Sources

- `.planning/PROJECT.md` — v2.2 scope and out-of-scope boundaries.
- `.planning/REQUIREMENTS.md` — SYM-01/SYM-02/SYM-03.
- `.planning/ROADMAP.md` — Phase 11 goals and success criteria.
- `.planning/STATE.md` — symbol-mapping validation snapshot.
- `.planning/phases/11-symbol-format-mapping-contract-data-source-translation-optimization/11-CONTEXT.md` — locked decisions and current mismatch snapshot.
- `agent/src/data/symbol_translator.py` — current translator and mismatch source.
- `agent/backtest/loaders/hybrid_fetcher.py` — routing/fetch boundary and current missing translation enforcement.
- `agent/backtest/loaders/akshare_loader.py` — endpoint-specific conversions.
- `agent/backtest/loaders/yfinance_loader.py` — yfinance conversion and canonical result keys.
- `agent/backtest/loaders/tqsdk_loader.py` — existing central translator integration.
- `agent/backtest/loaders/okx.py`, `agent/backtest/loaders/ccxt_loader.py` — crypto vendor conversions.
- `agent/backtest/loaders/registry.py` — fallback chains.
- `agent/backtest/engines/_market_hooks.py`, `agent/backtest/runner.py` — market detection and auto routing.
- `agent/mcp_server.py` — `get_market_data` unresolved behavior.
- `agent/tests/test_market_detection.py`, `agent/tests/test_hybrid_fetcher.py`, `agent/tests/test_akshare_loader.py`, `agent/tests/test_tqsdk_loader.py`, `agent/tests/test_registry.py`, `agent/tests/test_get_market_data_unresolved.py` — existing regression coverage.

## Assumptions Log

| # | Claim | Risk if Wrong |
|---|-------|---------------|
| A1 | Five-digit HK canonical key (`00700.HK`) is preferable for deterministic cache/output normalization. | User may prefer four-digit display/canonical; decide before implementation. |
| A2 | yfinance HK vendor call can be mapped separately from five-digit canonical, but exact accepted width requires optional live smoke. | Wrong vendor width may keep HK yfinance blocked even after symbol-contract work. |

## Research Metadata

**Confidence breakdown:**

- Current architecture: HIGH — directly verified from code and tests.
- Key mismatches: HIGH — directly verified from code and Phase 11 context.
- Canonical table: MEDIUM-HIGH — code-backed for implemented loader behavior; HK yfinance width remains environment/live-smoke dependent.
- Implementation approach: HIGH — follows locked Phase 11 decisions and current code boundaries.

**Valid until:** 2026-07-08, or until symbol translator/loader routing code changes.
