# Phase 11 Plan 01: Symbol Format Mapping Contract - Summary

**Plan:** 11-01
**Phase:** Symbol Format Mapping Contract & Data Source Translation Optimization
**Status:** COMPLETED
**Date:** 2026-06-09
**Commits:** 4

## One-liner

Established canonical symbol format contract: HK normalized to five-digit `.HK`, AKShare uses Sina `sh/sz` prefixes, HybridDataFetcher translates before provider calls and remaps results to canonical keys.

## Implementation Summary

### Canonical Format Table (Locked)

| Market | Canonical Example | Notes |
|--------|----------------|-------|
| A-share stock | `600036.SH`, `000001.SZ` | 6-digit + exchange suffix |
| A-share ETF | `518880.SH`, `159915.SZ` | 6-digit ETF prefix |
| US equity | `AAPL.US`, `TSLA.US` | Symbol.US format |
| HK equity | `00700.HK` | **Five-digit canonical** (0700.HK → 00700.HK) |
| US futures | `GC=F`, `CL=F`, `SI=F` | =F suffix |
| CN futures continuous | `rb0`, `al0`, `ag0` | Bare product + 0 |
| CN futures concrete | `IF2406`, `rb2410` | Product + expiry |
| Crypto | `BTC-USDT`, `ETH-USDT` | **Hyphen canonical** (slash = CCXT vendor only) |
| Forex | `EURUSD` | 6-char base |

### Vendor Translation Contracts

| Market | Vendor | Vendor Symbol | Notes |
|--------|--------|-------------|-------|
| CN_STOCK | AKSHARE | `sh600036`, `sz000001` | Sina format |
| CN_STOCK | TUSHARE | `600036.SH` | ts_code with suffix |
| CN_ETF | AKSHARE | `sh518880`, `sz159915` | Sina ETF format |
| US_STOCK | YAHOO_FINANCE | `AAPL` | Strip .US |
| HK_STOCK | AKSHARE | `00700` | Five-digit, no .HK |
| HK_STOCK | YAHOO_FINANCE | `00700.HK` | .HK format |
| US_FUTURES | AKSHARE | `GC`, `CL` | Strip =F |
| US_FUTURES | DATABENTO | `GC.c.0` | Continuous format |
| US_FUTURES | YAHOO_FINANCE | `GC=F`, `ZC=F` | C→ZC mapping |
| CN_FUTURES | TQSDK | `KQ.m@SHFE.rb` | Main continuous |
| CN_FUTURES | TQSDK | `SHFE.rb2410` | Concrete contract |
| CN_FUTURES | AKSHARE | `RB0`, `AL0` | Uppercase continuous |
| CRYPTO | OKX | `BTC-USDT` | Hyphen passthrough |
| CRYPTO | CCXT | `BTC/USDT` | Slash vendor |
| FOREX | AKSHARE | `EURUSD` | Direct pass-through |

### Explicitly Unsupported Combinations

| Market | Vendor | Reason |
|--------|--------|--------|
| CN_FUTURES | TUSHARE | Tushare has no CN futures endpoint; stock daily() returns garbage |
| US_STOCK | TQSDK | TqSdk is CN futures only |
| US_FUTURES | TQSDK | TqSdk is CN futures only |
| HK_STOCK | TQSDK | TqSdk is CN futures only |
| Crypto | TUSHARE | Tushare has no crypto endpoint |

## Artifacts Created/Modified

| File | Change | Commit |
|------|--------|--------|
| `agent/src/data/symbol_translator.py` | Rewrite with canonical contract | 91feb4b |
| `agent/src/data/market.py` | Update docstring | 91feb4b |
| `agent/backtest/loaders/hybrid_fetcher.py` | Add translation boundary | 91feb4b |
| `agent/tests/test_symbol_translator_contract.py` | New contract tests (84 tests) | 79db83c |
| `agent/tests/test_hybrid_fetcher.py` | Update to Phase 11 semantics | d1958d3 |

## Verification Results

### Contract Tests
```
PYTHONPATH=agent .venv/bin/python -m pytest -q agent/tests/test_symbol_translator_contract.py
84 passed in 0.39s
```

### Full Regression Suite
```
PYTHONPATH=agent .venv/bin/python -m pytest -q \
  agent/tests/test_symbol_translator_contract.py \
  agent/tests/test_market_detection.py \
  agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration \
  agent/tests/test_hybrid_fetcher.py::TestHybridDataFetcher \
  agent/tests/test_akshare_loader.py \
  agent/tests/test_tqsdk_loader.py \
  agent/tests/test_registry.py \
  agent/tests/test_get_market_data_unresolved.py \
  agent/tests/test_okx_loader_bounded.py \
  agent/tests/test_ccxt_loader_bounded.py

211 passed, 2 warnings in 1.11s
```

## Key Decisions Made

1. **HK canonical is five-digit `.HK`**: Both `0700.HK` and `00700.HK` normalize to `00700.HK`
2. **Crypto canonical is hyphen**: `BTC-USDT` is canonical, `/USDT` is CCXT vendor only
3. **CN futures → Tushare is unsupported**: Phase 11 marks this explicit to prevent silent garbage data
4. **AKShare A-share uses Sina format**: `sh600036`, `sz000001` not `600036SH`
5. **AKShare HK strips `.HK`**: Returns `00700` not `00700.HK`

## Direct Loader Shim

Direct loaders (`akshare_loader.py`, `yfinance_loader.py`) were **not modified**. They retain their existing canonical-input compatibility shims. The translation boundary is enforced in `HybridDataFetcher.fetch()` only.

**Rationale**: Per plan D-07: "Existing direct loaders must preserve direct-use behavior with canonical inputs." The contract tests prove direct loaders still accept canonical inputs.

## Optional Live Smoke (Not Executed)

Per plan D-10, live provider smoke tests were **not executed** as a completion requirement:

- `agent/tests/_smoke_akshare_real.py` — Not run (requires live AKShare)
- yfinance HK/US equity live — Not run (proxy availability environment-dependent)

These remain available for optional manual verification.

## Threat Surface

| Flag | File | Description |
|------|------|-------------|
| N/A | — | No new threat surface introduced |

Phase 11 implements the canonical symbol contract as designed. All boundaries properly enforced.

## Deviation: Test File Cleanup

During Task 3, fixed existing `TestSymbolTranslatorIntegration` tests:
- `test_translate_symbol_for_yahoo_hk`: Changed input from bare `00700` to canonical `00700.HK`
- `test_translate_symbol_cn_futures`: Changed to assert CN_FUTURES→TUSHARE is unsupported per Phase 11

## TDD Gate Compliance

| Phase | Gate | Status |
|-------|------|--------|
| Task 1 | RED: Tests exist and fail before implementation | ✅ |
| Task 2 | GREEN: Implementation makes tests pass | ✅ |

## Commits

| Hash | Message |
|------|---------|
| `79db83c` | test(11): add failing RED-phase contract tests for canonical symbol format |
| `91feb4b` | feat(11): implement SymbolTranslator canonical contract |
| `d1958d3` | fix(11): update existing tests to Phase 11 contract semantics |

## Self-Check

- [x] Contract tests exist and pass (84)
- [x] Regression tests pass (211 total)
- [x] HK five-digit canonical enforced
- [x] AKShare Sina format enforced
- [x] HybridDataFetcher translation boundary implemented
- [x] Direct loaders unchanged (compatibility shims preserved)
- [x] CN futures → Tushare explicitly unsupported
- [x] No live provider dependency for completion
- [x] No vendor key leakage to caller outputs

---

**Status:** ✅ PLAN COMPLETE
**Files Modified:** 5 (3 source, 2 test)
**Test Coverage:** 84 contract + 127 regression = 211 total tests
