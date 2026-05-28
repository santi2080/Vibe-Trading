# MTES Backtest Validation Plan

**Phase:** 01-major-trend-evaluation-system  
**Created:** 2026-05-28

## Objective

Validate whether the Major Trend Evaluation System (MTES) improves major-trend classification robustness versus single-indicator trend baselines across stocks, ETFs, futures, crypto, and FX.

## Asset Universes

| Universe | Examples | Data source |
|---|---|---|
| US futures | GC=F, SI=F, HG=F, CL=F, ZC=F, ZS=F, ES=F, NQ=F | local `data/us_futures` cache |
| CN futures | al0, rb0, ru0, ta0 | local `data/cn_futures` cache |
| ETFs | broad index, sector, bond, commodity ETFs | local `data/etf` cache |
| Stocks | US / HK / A-stock liquid names | existing local loaders/cache |
| Crypto / FX | liquid symbols with daily and intraday history | existing ccxt/fx-compatible loaders |

## Time Splits

- **Training / calibration:** first 40% of available history for threshold sanity only.
- **Validation:** middle 30% for parameter perturbation and implementation checks.
- **Out-of-sample test:** final 30% for primary results.
- **Walk-forward check:** rolling 12-month evaluation windows with 3-month step where sufficient history exists.

## Baseline Strategies

At minimum compare MTES against these single-indicator or narrow baselines:

1. **SMA 200 direction:** price above/below 200-day SMA.
2. **Dual EMA crossover:** EMA 50 vs EMA 200.
3. **EMA + ADX:** existing `TrendEmaAdxStrategy` style confirmation.
4. **Donchian breakout:** close above/below 55-day high/low channel.
5. **Range Filter direction:** Range Filter up/down state.
6. **12-month momentum:** trailing 252-bar return sign and rank.
7. **MACD trend:** MACD line vs signal and zero line.

## MTES Signal Construction

- Long trend-active when `trend_state in {BULL_CONFIRMED, BULL_STRONG}`.
- Short trend-active when `trend_state in {BEAR_CONFIRMED, BEAR_STRONG}`.
- Neutral / no-position when `NEUTRAL_CHOPPY`, `BULL_EARLY`, or `BEAR_EARLY` unless testing early-entry variants.
- Use one-bar delay after signal generation to prevent same-bar look-ahead execution.
- MTF variants must use the existing lagged higher-timeframe alignment rule.

## Cost and Slippage Assumptions

| Asset class | Default cost model |
|---|---|
| Stocks / ETFs | 2–10 bps one-way, tested across low/base/high assumptions |
| Futures | contract-specific tick/slippage where available; otherwise 1–3 ticks one-way |
| Crypto | 5–20 bps one-way depending on venue tier |
| FX | spread proxy in bps; low/base/high sensitivity |

## Metrics

Primary metrics:

1. CAGR / annualized return.
2. Maximum drawdown.
3. Sharpe ratio.
4. Calmar ratio.
5. Turnover.
6. Whipsaw / false-signal rate.
7. Win rate and average win/loss.
8. Exposure percentage.
9. Signal delay sensitivity.
10. Cross-asset hit rate by universe.

## Robustness Checks

### Parameter perturbation

Pass if MTES remains within an acceptable degradation band when key windows shift by ±20%:

- Long window: 160 / 200 / 240.
- Intermediate window: 40 / 50 / 60.
- Structure window: 44 / 55 / 66.
- Momentum windows: ±20% rounded to trading bars.

### Signal delay

Pass if delayed signals do not collapse relative performance:

- Execute at next bar, +2 bars, +5 bars.
- Record return, drawdown, turnover, and whipsaw changes.

### Asset-class weights

- Compare default asset-class profile vs equal weights.
- Pass if default profile improves either whipsaw rate or drawdown without materially reducing return.

### Choppy market filter

- Identify periods with low trend efficiency or high whipsaw baseline behavior.
- Pass if MTES `NEUTRAL_CHOPPY` reduces false trend exposure vs at least three baselines.

### MTF no-look-ahead

- Verify every lower-timeframe decision uses only completed higher-timeframe bars.
- Deliberately shift higher-timeframe data forward in a negative-control test; verification must detect inflated or invalid results.

## Pass / Fail Guidance

MTES should be considered validated for a universe only if:

- It beats at least four of seven baselines on whipsaw-adjusted return or drawdown-adjusted return.
- It does not materially underperform the best baseline on maximum drawdown.
- It remains stable under ±20% parameter perturbation.
- It remains usable with +1 and +2 bar signal delay.
- It produces fewer false trend exposures in choppy regimes than the majority of baselines.

## Required Artifacts

- Per-universe metrics table.
- Baseline comparison table.
- Robustness summary table.
- Parameter sensitivity report.
- Signal-delay report.
- Examples of top MTES drivers for winners and failures.
