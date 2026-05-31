# Phase 02-01 Summary

---
phase: 02-trend-indicator-backtest
plan: 01
status: completed
summary_type: execution
completed_tasks: 5
files:
  - scripts/backtest_trend_indicators.py
  - reports/trend_indicator_comparison_20260530_204518.csv
  - reports/trend_indicator_report_20260530_204518.md
  - reports/trend_indicator_comparison_20260530_204526.csv
  - reports/trend_indicator_report_20260530_204526.md
  - .planning/phases/02-trend-indicator-backtest/02-01-SUMMARY.md
---

# Phase 02 Plan 01: 趋势指标回测系统执行摘要

Phase 02 已完成趋势指标回测系统执行与验证。系统可对跨资产趋势指标进行统一回测、评分、排名，并生成 CSV 与 Markdown 报告。

## Completed Work

### Task 1: 数据准备
- 使用现有本地 Parquet 数据，未重复下载外部数据。
- 可用数据覆盖 25 个品种，包括：
  - 美国期货：`GC=F`, `SI=F`, `CL=F`, `ES=F`, `NQ=F`, `ZC=F`
  - ETF / 行业 ETF：`TLT`, `IAU`, `XLK`, `XLF`, `XLV`, `XLY`, `XLP`, `XLE`, `XLI`, `XLB`, `XLRE`, `XLU`, `XLC`, `SOXX`
  - A 股 ETF：`510300.SS`, `510500.SS`, `512760.SS`, `515790.SS`, `512170.SS`
- Fresh verification 统计：`data` 下可用 parquet/csv 数据文件共 109 个。

### Task 2: 创建回测框架
- `scripts/backtest_trend_indicators.py` 已实现趋势指标回测 CLI。
- 支持：
  - 单品种回测：`--symbol`
  - 全品种回测：`--all`
  - 市场过滤：`--market-filter`
  - 时间周期：`--timeframe 1d|1W`
  - 输出目录：`--output`
- 报告输出包括 CSV 对比表和 Markdown 报告。

### Task 3: 实现趋势指标与评估指标
- 已实现 7 个趋势指标：
  - `SuperTrend`
  - `TrendFusion`
  - `EMACross`
  - `SMASlope`
  - `ADX`
  - `RangeFilter`
  - `MTES`
- 已实现 3 个评分维度：
  - 方向准确性（信号方向与未来收益方向一致率）
  - 信号领先性（信号与未来收益相关性归一化评分）
  - 噪音过滤（趋势切换稳定性）
- 综合得分公式：`direction_score * 0.4 + lead_score * 0.3 + noise_score * 0.3`。

### Task 4: 运行回测
- Fresh verification 已运行：
  - 单品种验证：`.venv/bin/python3 scripts/backtest_trend_indicators.py --symbol GC=F --compare --output reports`
  - 全品种日线：`.venv/bin/python3 scripts/backtest_trend_indicators.py --all --timeframe 1d --output reports`
  - 全品种周线：`.venv/bin/python3 scripts/backtest_trend_indicators.py --all --timeframe 1W --output reports`
- 最新核心输出：
  - 日线 CSV：`reports/trend_indicator_comparison_20260530_204518.csv`
  - 日线报告：`reports/trend_indicator_report_20260530_204518.md`
  - 周线 CSV：`reports/trend_indicator_comparison_20260530_204526.csv`
  - 周线报告：`reports/trend_indicator_report_20260530_204526.md`

### Task 5: 分析与总结

#### 日线（1D）平均排名

| 排名 | 指标 | 方向准确性 | 信号领先性 | 噪音过滤 | 综合得分 |
|:----:|------|:----------:|:----------:|:--------:|:--------:|
| 1 | **RangeFilter** | 52.6% | 50.0% | 99.9% | **66.0** |
| 2 | SuperTrend | 48.7% | 49.2% | 99.6% | **64.1** |
| 3 | EMACross | 50.3% | 49.5% | 96.6% | **63.9** |
| 4 | TrendFusion | 50.3% | 49.9% | 93.3% | **63.1** |
| 5 | ADX | 39.2% | 50.3% | 90.0% | **57.8** |
| 6 | MTES | 36.0% | 49.1% | 95.5% | **57.8** |
| 7 | SMASlope | 34.9% | 49.8% | 91.7% | **56.4** |

日线最佳指标分布：
- `RangeFilter`: 21 个品种
- `SuperTrend`: 2 个品种
- `EMACross`: 2 个品种

#### 周线（1W）平均排名

| 排名 | 指标 | 方向准确性 | 信号领先性 | 噪音过滤 | 综合得分 |
|:----:|------|:----------:|:----------:|:--------:|:--------:|
| 1 | **RangeFilter** | 55.0% | 50.0% | 99.5% | **66.8** |
| 2 | SuperTrend | 53.7% | 50.0% | 99.4% | **66.3** |
| 3 | EMACross | 53.2% | 49.1% | 96.2% | **64.9** |
| 4 | TrendFusion | 52.6% | 48.8% | 93.9% | **63.8** |
| 5 | MTES | 45.9% | 50.9% | 96.5% | **62.6** |
| 6 | ADX | 42.3% | 49.5% | 90.3% | **58.9** |
| 7 | SMASlope | 40.2% | 49.7% | 92.2% | **58.7** |

周线最佳指标分布：
- `SuperTrend`: 17 个品种
- `RangeFilter`: 6 个品种
- `EMACross`: 1 个品种
- `ADX`: 1 个品种

## Recommendation

1. **日线趋势判断首选 `RangeFilter`**：综合得分最高，且在 25 个品种中有 21 个品种排名第一。
2. **周线趋势判断优先 `RangeFilter + SuperTrend` 双确认**：平均分 `RangeFilter` 略高，但单品种最佳数量 `SuperTrend` 更高。
3. **`EMACross` 可作为低复杂度备选**：在 1D 与 1W 均排名第三，表现稳定。
4. **`MTES` 当前更适合作为综合解释层，而非单独趋势指标冠军**：噪音过滤较强，但方向准确性在该评分框架下落后。

## Verification

Fresh verification passed:

```bash
.venv/bin/python3 scripts/backtest_trend_indicators.py --symbol GC=F --compare --output reports
.venv/bin/python3 scripts/backtest_trend_indicators.py --all --timeframe 1d --output reports
.venv/bin/python3 scripts/backtest_trend_indicators.py --all --timeframe 1W --output reports
```

All commands completed successfully and generated CSV + Markdown reports.

## Deviations from Plan

### Controlled expansion
- 原计划列出 8 个核心品种；实际回测扩展到 25 个本地已有数据品种。
- 原计划提到 6 个指标；实际验证覆盖 7 个指标，包含 `MTES`。
- 扩展原因：脚本已支持完整 `SYMBOLS_CONFIG`，使用本地数据无需额外 API 下载，能提供更稳健的跨市场结论。

## Known Notes

- 该回测是指标比较工具，不等同于完整交易策略回测；未包含交易成本、仓位管理、止损止盈和组合约束。
- `RangeFilter` 与 `SuperTrend` 在噪音过滤维度得分接近满分，说明当前评分框架较偏好低切换频率指标。
- 后续若用于交易决策，应补充收益、回撤、换手率、交易成本敏感性和 walk-forward 验证。

## Self-Check

PASSED
