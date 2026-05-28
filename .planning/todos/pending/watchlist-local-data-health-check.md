---
title: Implement watchlist local data health check
date: 2026-05-27
priority: high
---

# Implement watchlist local data health check

## Goal

Add a pre-backtest data health check for watchlists. When a user asks to query local data information for a watchlist, the system should inspect local cached data and report whether the watchlist is safe to use for strategy backtesting.

## Scope

- Add a command or script such as `scripts/check_watchlist_data.py`.
- Read existing watchlist CSV files via the existing watchlist reader where practical.
- Inspect standard local parquet cache files under `data/{market}/{symbol}/{timeframe}.parquet`.
- Treat `1d` and `1h` as blocking timeframes by default.
- Treat `4h` and other derived/auxiliary timeframes as warnings unless explicitly required later.
- Output both a readable table and JSON.

## Required table fields

- watchlist
- market
- symbol
- name
- timeframe
- required
- cache_file
- exists
- start
- end
- rows
- age
- max_gap
- missing_recent
- gap_warning
- status: `PASS` / `WARN` / `FAIL`
- reason

## Gate rules

- Missing `1d` or `1h` file: `FAIL`.
- Empty `1d` or `1h` data: `FAIL`.
- Missing required OHLCV fields on `1d` or `1h`: `FAIL`.
- Latest `1d` data older than 2 days: `FAIL`.
- Latest `1h` data older than 6 hours: `FAIL`.
- Latest `4h` data older than 12 hours: `WARN`.
- Large internal gaps should warn in the first version rather than block, unless they affect a required timeframe severely.

## Suggested implementation checks

- Reuse `agent/src/data/watchlist.py` for watchlist parsing.
- Reuse quality logic from `agent/backtest/loaders/cache/quality_checker.py` or align with it.
- Use standard data files as the source of truth; treat `data/cache/vibe` hash cache and metadata as supplemental diagnostics only.

## Verification

- Run the command against `watchlist/us_futures_watchlist.csv`.
- Confirm table and JSON include every symbol and checked timeframe.
- Confirm missing/empty/stale `1d` or `1h` produces a non-zero gate result.
- Confirm only auxiliary `4h` issues produce warnings without blocking backtest.

## Data update attempt — 2026-05-28

Updated local cache files before rerunning the gate:

- US futures `1d`: updated via yfinance period mode for `GC=F`, `SI=F`, `HG=F`, `CL=F`, `ZC=F`, `ZS=F`, `ES=F`, `NQ=F`; latest bar `2026-05-27`.
- US futures `1h`: updated via yfinance period mode for all watchlist symbols; latest available bar `2026-05-27 22:00`.
- CN futures `1d`: updated via AKShare for `al0`, `rb0`, `ru0`, `ta0`; latest bar `2026-05-27`.
- CN futures `1h`: not updated. TqSdk is installed but requires a 快期/TqSdk account (`TQSDK_ACCOUNT`/`TQSDK_PASSWORD` or equivalent auth). Without credentials, the API refuses historical kline requests.

Post-update gate results:

- `watchlist/us_futures_watchlist.csv`: still `FAIL` because v1 strict `1h > 6h` threshold flags data latest at `2026-05-27 22:00` as ~13h old when checked on `2026-05-28` morning. Data is updated to the latest yfinance provided; the fixed 6h threshold may be too strict for daily pre-market checks.
- `watchlist/cn_futures_watchlist.csv`: still `FAIL` because `1h` data remains stale without TqSdk credentials; `1d` data is updated but AKShare historical daily data includes a few old OHLC anomalies for `al0`, `ru0`, and `ta0`.

Recommended follow-ups:

1. Decide whether US futures `1h` staleness should remain at 6h or be loosened for overnight/weekend/pre-market checks. **Decision:** loosened to 24h for `us_futures:1h` only; other markets keep default `1h=6h`.
2. Configure TqSdk credentials before attempting CN futures `1h` updates.
3. Decide whether tiny historical OHLC anomalies in old CN daily data should block backtests or be downgraded when outside the active backtest window.

Follow-up result after threshold adjustment:

- `watchlist/us_futures_watchlist.csv`: gate changed from `FAIL` to `WARN` with `0 blocking issue(s)` after applying `us_futures:1h = 24h` and updating local `1d/1h` data.
- `watchlist/cn_futures_watchlist.csv`: still `FAIL`; blockers are stale `1h` data requiring TqSdk credentials and old OHLC anomalies in AKShare daily history.
