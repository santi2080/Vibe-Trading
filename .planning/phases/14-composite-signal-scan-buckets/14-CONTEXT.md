# Phase 14: Composite Signal Scan Buckets — Context

**Phase:** 14 | **Milestone:** v2.2 daily-scan-report-loop  
**Created:** 2026-06-10  
**Goal:** User can see every watchlist symbol classified through CompositeTrendStrategy / TradingSignal semantics.

---

## Domain

Signal scan bucket 分类：将 watchlist 中的每个 symbol 通过 `CompositeTrendStrategy` 分析后，按趋势方向分类为 bull/bear/neutral bucket。

---

## Decisions

### 输出格式
- **JSON + 表格双输出**
- JSON 文件包含完整数据（用于程序处理）
- 表格用于快速浏览（人类可读）
- SIG-02 要求 5 种分类：Actionable, Watch, Risk/Excluded, Skipped, Failed

### Bucket 阈值
- **基于趋势方向**
  - Bull: 上行趋势信号
  - Bear: 下行趋势信号
  - Neutral: 无趋势或不确定

### 异常处理
- **记录但继续（Graceful Degradation）**
- 单个 symbol 分析失败不影响其他 symbol
- 失败 symbol 记录到 `scan_results.json` 的 `failed` bucket
- 继续处理剩余 symbols

---

## Requirements

- **SIG-01**: Eligible symbols are scanned through `CompositeTrendStrategy` / `TradingSignal` semantics
- **SIG-02**: Every watchlist symbol is assigned to exactly one bucket or reason code

---

## Canonical Refs

- `agent/src/signals/trading_signal.py` — TradingSignal dataclass
- `agent/src/strategies/composite_trend_strategy.py` — CompositeTrendStrategy
- `agent/src/cli/commands/scan.py` — Phase 13 scan CLI
- `.planning/REQUIREMENTS.md` — SIG-01, SIG-02 requirements

---

## Deferred Ideas

(None for Phase 14)
