# Phase 01: Major Trend Evaluation System - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 01-major-trend-evaluation-system
**Areas discussed:** weight model, direction definition, signal families, multi-timeframe alignment, integration shape, reviewed todo handling

---

## Weight Model

| Option | Description | Selected |
|--------|-------------|----------|
| Base+Override | Define one generic six-dimension base profile, then apply small asset-class overrides for stock/etf/futures/crypto/fx. | ✓ |
| 独立表 | Each asset class has a completely independent six-dimension weight table. | |
| 模板化 | Define a few templates and map asset classes to templates. | |

**User's choice:** Base+Override
**Notes:** This decision favors maintainability and consistent cross-asset comparison.

| Option | Description | Selected |
|--------|-------------|----------|
| 加权+惩罚 | Weighted sum plus limited penalties for noise/regime, MTF conflicts, and insufficient data. | ✓ |
| 纯加权 | Only sum weighted six-dimension sub-scores. | |
| 门控加权 | Low key dimensions cap the final score. | |

**User's choice:** 加权+惩罚
**Notes:** Avoids over-ranking noisy or conflicting trends while preserving weighted scoring.

| Option | Description | Selected |
|--------|-------------|----------|
| 方向符号独立 | `trend_score` is trend quality/strength; direction is separate. | ✓ |
| 牛正熊负 | Score has direct bullish/bearish sign meaning. | |
| 多空双分 | Output separate bull and bear scores. | |

**User's choice:** 方向符号独立
**Notes:** Supports ranking strong bull and strong bear trends with a single 0–100 quality score.

| Option | Description | Selected |
|--------|-------------|----------|
| 均衡趋势 | direction 20, strength 20, structure 15, momentum 15, regime 15, MTF 15. | |
| 结构优先 | direction 15, strength 15, structure 25, momentum 15, regime 15, MTF 15. | ✓ |
| 动量优先 | direction 15, strength 15, structure 10, momentum 25, regime 15, MTF 20. | |

**User's choice:** 结构优先
**Notes:** Structure should be the highest weighted base dimension.

---

## Reviewed Todo Handling

| Option | Description | Selected |
|--------|-------------|----------|
| 并入前置门禁 | Fold watchlist local data health gate into this phase context. | |
| 只作依赖 | Record as an external dependency, but avoid implementation in this phase. | |
| 暂不处理 | Do not include it in the current phase. | ✓ |

**User's choice:** 暂不处理
**Notes:** `.planning/todos/pending/watchlist-local-data-health-check.md` was reviewed but not folded.

---

## Direction Definition

| Option | Description | Selected |
|--------|-------------|----------|
| MA+Slope+Return | Price vs long average, intermediate average vs long average, long-average slope, long-horizon return direction. | ✓ |
| Price Action | Structure, breakouts/breakdowns, and trend lines as primary direction. | |
| Indicator Blend | EMA/ADX/MACD/Range Filter direction vote. | |

**User's choice:** MA+Slope+Return
**Notes:** Direction should be robust and cross-asset, not an indicator pile-up.

| Option | Description | Selected |
|--------|-------------|----------|
| 默认固定 | Use fixed 50/200 or equivalent by default, with minimal overrides. | |
| 资产定制 | Asset-class-specific long/intermediate periods. | ✓ |
| 数据自适应 | Select periods based on available data length. | |

**User's choice:** 资产定制
**Notes:** Planner should propose explicit periods per asset class.

| Option | Description | Selected |
|--------|-------------|----------|
| 降级评分 | Use shorter windows with metadata and a penalty. | |
| 直接无法评分 | Return insufficient-data/no score when long lookback is missing. | ✓ |
| 忽略长期项 | Reallocate missing weight to other direction sub-items. | |

**User's choice:** 直接无法评分
**Notes:** Strict long-horizon data sufficiency is required for direction scoring.

| Option | Description | Selected |
|--------|-------------|----------|
| 固定阈值 | Fixed score thresholds for early/confirmed/strong; direction chooses bull/bear side. | ✓ |
| 资产阈值 | Thresholds differ by asset class. | |
| 分位阈值 | Thresholds derive from watchlist cross-sectional percentiles. | |

**User's choice:** 固定阈值
**Notes:** Initial thresholds should be testable and cross-asset consistent.

---

## Signal Families

| Option | Description | Selected |
|--------|-------------|----------|
| 突破+摆动 | Donchian/range breakout plus higher-high/higher-low or lower-low/lower-high swing structure. | ✓ |
| 只看突破 | Only N-day high/low or range location. | |
| 只看摆动 | Only swing high/low sequence. | |

**User's choice:** 突破+摆动
**Notes:** Structure combines breakout state and price-action sequence.

| Option | Description | Selected |
|--------|-------------|----------|
| 绝对+相对 | 3/6/12M absolute returns, with cross-sectional relative rank when available. | ✓ |
| 只绝对 | Only own 3/6/12M returns. | |
| 只相对 | Mainly watchlist-relative strength ranking. | |

**User's choice:** 绝对+相对
**Notes:** Single-asset analysis must still work without cross-sectional context.

| Option | Description | Selected |
|--------|-------------|----------|
| 震荡效率低 | Prioritize trend-efficiency/chop penalties; extreme ATR/HV as extra flags. | ✓ |
| 极端波动 | Prioritize extreme ATR% or HV percentile penalties. | |
| 低波动无趋势 | Prioritize low volatility / low ADX dead markets. | |

**User's choice:** 震荡效率低
**Notes:** Regime answers “is this suitable for trend-following?” more than “is volatility high?”

| Option | Description | Selected |
|--------|-------------|----------|
| 子分降级 | Calculate available sub-indicators, degrade missing sub-score, mark metadata. | ✓ |
| 整维缺失 | Any missing sub-indicator makes the whole dimension unavailable. | |
| 权重重分配 | Reallocate missing sub-indicator weight to available ones. | |

**User's choice:** 子分降级
**Notes:** Core OHLC and long-horizon direction insufficiency remain stricter than optional sub-indicator gaps.

---

## Multi-Timeframe Alignment

| Option | Description | Selected |
|--------|-------------|----------|
| 资产类默认 | Each asset class defines default base/higher timeframes. | |
| 全局固定 | All assets use one global MTF pair. | |
| watchlist 指定 | Watchlist rows define base/higher timeframes. | ✓ |

**User's choice:** watchlist 指定
**Notes:** Planner should use watchlist timeframes as the primary MTF configuration source.

| Option | Description | Selected |
|--------|-------------|----------|
| 强惩罚 | Lower MTF sub-score and flag `timeframe_conflict`; do not veto total score. | ✓ |
| 直接封顶 | Cap total score to early/neutral range. | |
| 只作备注 | Only metadata flag, no meaningful score impact. | |

**User's choice:** 强惩罚
**Notes:** Matches the weighted-plus-penalty decision.

---

## Integration Shape

| Option | Description | Selected |
|--------|-------------|----------|
| WatchlistAnalyzer | Extend existing watchlist analysis first. | |
| 独立模块 | Build standalone evaluator/CLI first. | |
| Backtest策略 | Integrate first as a backtest strategy. | ✓ |

**User's choice:** Backtest策略
**Notes:** User wants backtest strategy integration prioritized, but SPEC still requires watchlist output.

| Option | Description | Selected |
|--------|-------------|----------|
| 双入口 | Core evaluator plus backtest wrapper and WatchlistAnalyzer adapter. | ✓ |
| 先回测 | Only backtest strategy in this phase. | |
| 只评分器 | Only standalone evaluator. | |

**User's choice:** 双入口
**Notes:** This resolves the tension between user preference and SPEC acceptance criteria.

---

## Claude's Discretion

- Exact module/class names and fixture organization are left to planner/researcher discretion.
- Exact asset-class override values are left for planner/researcher proposal, with base profile locked.

## Deferred Ideas

- Watchlist local data health gate remains separate and is not folded into this MTES phase.
