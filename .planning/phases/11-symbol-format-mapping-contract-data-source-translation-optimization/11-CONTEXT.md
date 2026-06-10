# Phase 11: Symbol Format Mapping Contract & Data Source Translation Optimization - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 11 establishes the symbol-format prerequisite for v2.2 daily scan. The project must have one user-facing Canonical Symbol Format for watchlists, backtest configs, MCP/API inputs, local cache keys, and daily scan run plans. Data-source boundaries must translate canonical symbols into vendor-specific formats and return canonical keys to callers.

This phase should optimize `SymbolTranslator`, `HybridDataFetcher`, and loader boundary responsibilities. It should not implement the daily scan CLI/run-plan itself, remote refresh modes, data-health gate execution, strategy scanning, Markdown reporting, or scheduling. Those are Phase 12-16.

</domain>

<decisions>
## Implementation Decisions

### Canonical format direction

- **D-01:** Canonical symbols are user-facing and stable. Vendor-specific symbols are boundary-only and must not leak into watchlists/run plans/output keys.
- **D-02:** Recommended canonical examples:
  - A-share stock/ETF/LOF: `600036.SH`, `000001.SZ`, `518880.SH`, `159915.SZ`
  - US equity: `AAPL.US`
  - HK equity: `0700.HK` or `00700.HK`, normalized deterministically by contract
  - US futures continuous: `GC=F`, `CL=F`, `SI=F`, `ZC=F`
  - CN futures main continuous: `rb0`, `al0`, `ag0`, `if0`
  - CN futures concrete contract: `IF2406`, `rb2410`
  - Crypto: `BTC-USDT`
  - Forex: `EURUSD`
- **D-03:** Unsupported market/vendor combinations should be explicit. Do not silently strip suffixes into plausible but wrong symbols.

### Translation boundary

- **D-04:** `SymbolTranslator` should become the documented contract for canonical-to-vendor mapping.
- **D-05:** Loaders may keep compatibility shims, but duplicated conversion logic should either delegate to `SymbolTranslator` or be covered by contract tests.
- **D-06:** `HybridDataFetcher.fetch()` currently does not use `translate_symbol()` in its main `pool.fetch()` call. Phase 11 should fix this by translating before vendor fetch and mapping results back to canonical keys.
- **D-07:** Existing direct loaders such as `akshare_loader`, `yfinance_loader`, and `tqsdk_loader` must preserve direct-use behavior with canonical inputs.

### Verification

- **D-08:** Add focused tests before or alongside implementation to pin canonical-to-vendor contracts.
- **D-09:** Preserve existing green suites:
  - `agent/tests/test_market_detection.py`
  - `agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration`
  - non-network data routing tests used in the 2026-06-08 validation snapshot.
- **D-10:** This phase must not require live provider calls for completion. Live smoke can be optional/manual because yfinance proxy availability is environment-dependent.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning scope

- `.planning/PROJECT.md` — v2.2 project context, validated capabilities, and out-of-scope boundaries.
- `.planning/REQUIREMENTS.md` — Phase 11 requirements: SYM-01, SYM-02, SYM-03.
- `.planning/ROADMAP.md` — Phase 11 goal and success criteria.
- `.planning/STATE.md` — current GSD state and symbol mapping validation snapshot.

### Existing code references

- `agent/src/data/symbol_translator.py` — current central translator; top docstring currently conflicts with actual canonical usage for A-share/HK formats.
- `agent/src/data/market.py` — `Market` enum and parser aliases.
- `agent/backtest/engines/_market_hooks.py` — shared `_detect_market`, `_is_china_futures`, `_detect_submarket`.
- `agent/backtest/runner.py` — `_detect_source`, `_group_codes_by_market`, `_group_codes_by_source`, backtest loader selection.
- `agent/backtest/loaders/hybrid_fetcher.py` — `SymbolRouter`, `translate_symbol()`, `SourcePool.fetch()`, `HybridDataFetcher.fetch()`.
- `agent/backtest/loaders/akshare_loader.py` — actual AKShare endpoint-specific conversions for A-share, ETF, HK, US futures, CN futures, forex.
- `agent/backtest/loaders/yfinance_loader.py` — actual yfinance conversions for `.US`, `.HK`, and `=F`.
- `agent/backtest/loaders/tqsdk_loader.py` — existing `SymbolTranslator` integration for CN futures.
- `agent/backtest/loaders/okx.py`, `agent/backtest/loaders/ccxt_loader.py` — crypto vendor formats.

### Existing tests

- `agent/tests/test_market_detection.py` — market detection and source mapping tests.
- `agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration` — current translator integration tests, currently too shallow.
- `agent/tests/test_akshare_loader.py` — mocked AKShare endpoint routing tests.
- `agent/tests/test_get_market_data_unresolved.py` — unresolved requested code behavior.
- `agent/tests/test_registry.py` — fallback chain behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Validation snapshot from 2026-06-08

- `PYTHONPATH=agent .venv/bin/python -m pytest -q agent/tests/test_market_detection.py agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration` → `59 passed in 0.28s`.
- Non-network routing suite → `159 passed, 2 warnings in 2.20s`.
- Live smoke → `5/7` passed; A-share, US futures, CN futures, crypto OK; US/HK equity blocked by `No available proxies` in yfinance path.

### Current mismatches

- `SymbolTranslator` docstring says A-share canonical is six digits and HK is five digits, but actual project usage and tests use suffix forms such as `600036.SH` and `0700.HK`.
- Current `SymbolTranslator.to_vendor_format("600036.SH", AKSHARE, CN_STOCK)` returns `600036SH`, while AKShare loader actually expects Sina-style `sh600036` for stock endpoint.
- Current `SymbolTranslator.to_vendor_format("00700.HK", AKSHARE, HK_STOCK)` returns `00700.HK`, while AKShare loader expects `00700`.
- `HybridDataFetcher.translate_symbol()` exists but `HybridDataFetcher.fetch()` passes canonical `market_symbols` directly to `SourcePool.fetch()`.

</code_context>

<specifics>
## Specific Ideas

- Start with tests that define canonical-to-vendor contract in a new focused test file, likely `agent/tests/test_symbol_translator_contract.py`.
- Introduce a result object or helper that allows caller to know whether a translation is supported, but keep API simple if surrounding code expects plain strings.
- Preserve canonical output keys by translating request symbols into vendor symbols and then mapping returned data back to original canonical symbols.
- Avoid live provider tests in the required plan; use mocks to prove vendor-call symbols.

</specifics>

<deferred>
## Deferred Ideas

- yfinance proxy remediation — important but separate from symbol-format contract unless needed to preserve fallback behavior.
- TqSdk async cleanup warnings — separate reliability cleanup.
- Remote refresh modes — future `REF-01`.
- Exchange-calendar/session-aware freshness — future `CAL-01`.
- Daily scan CLI/run plan — Phase 12.
- Data-health gate — Phase 13.
- Signal buckets — Phase 14.
- Report/artifacts — Phase 15.
- Verification closure — Phase 16.

</deferred>

---

*Phase: 11-Symbol Format Mapping Contract & Data Source Translation Optimization*
*Context gathered: 2026-06-08*
