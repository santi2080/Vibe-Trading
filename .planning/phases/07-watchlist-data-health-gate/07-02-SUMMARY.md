# Phase 07-02 Summary: Data Health Gate Integration for Analysis + Backtest

## 完成状态
- **计划**: 07-02
- **状态**: ✅ 完成
- **日期**: 2026-06-02

## 实现内容

### 1. `analyze_watchlist` 增加前置 data-health gate
在 `agent/src/tools/watchlist_tool.py` 中，`AnalyzeWatchlistTool.execute()` 现在会在真正分析前执行 gate：

- 先解析并校验 watchlist 路径
- 调用已存在的 `check_watchlist_data()` 生成本地数据健康报告
- 支持按 `market_filter` 对 gate 结果做同口径过滤
- 当 `gate.can_backtest == false` 时：
  - 返回 `status="error"`
  - 返回 `error_type="data_health_gate_blocked"`
  - 返回完整 `gate / rules / items`
  - **不会**继续调用 `WatchlistAnalyzer.analyze_all()`
- 当仅有辅助周期告警时：
  - 允许继续分析
  - 在正常响应中附带 `data_health_gate`

### 2. 趋势回测脚本新增 watchlist 受保护入口
在 `scripts/backtest_trend_indicators.py` 中新增 watchlist 路径：

- 新增 CLI 参数：
  - `--watchlist`
  - `--now`
- 新增辅助函数：
  - `_serialize_gate_payload()`
  - `build_watchlist_gate_payload()`
  - `_load_watchlist_symbols()`
  - `run_watchlist_backtest()`
  - `_parse_gate_now()`
- 行为变化：
  - watchlist 回测前先执行本地 parquet data-health gate
  - gate 失败时输出机器可读 JSON，并以非零状态退出
  - gate 仅 WARN 时允许继续回测
  - 生成报告时写入 `Watchlist Data Health Gate` 摘要
- 保留原有：
  - `--symbol`
  - `--all`
  - `--market-filter`
  流程不变

### 3. 测试覆盖增强
新增确定性测试覆盖：

- `analyze_watchlist` 在 required `1d/1h` 缺失时阻断
- 阻断时 `WatchlistAnalyzer.analyze_all()` 不会被调用
- 仅 auxiliary `4h` 告警时允许继续分析
- watchlist backtest gate 在 required 数据缺失时非零退出
- watchlist backtest gate 在 warning-only 情况下继续执行
- 既有 `agent/tests/test_watchlist_data_health.py` 回归通过

## 关键设计决策

1. **分析与回测共用同一 gate 逻辑**
   - 不重复实现本地数据健康判定
   - 统一复用 `watchlist_data_health.py`

2. **阻断 required，放行 auxiliary**
   - `1d` / `1h` 失败 → block
   - 辅助周期（如 `4h`）失败 → warn only

3. **输出对机器友好**
   - 无论是 tool 还是 backtest 入口，失败时都附带完整 gate 上下文
   - 方便上层 agent / MCP / CLI 消费

4. **市场过滤与 gate 对齐**
   - `analyze_watchlist(..., market_filter=...)` 时，gate 判断只针对同一市场子集
   - 避免无关市场数据问题误阻断当前分析请求

## 验证

```bash
.venv/bin/python -m pytest agent/tests/test_strategy_watchlist_tools.py agent/tests/test_watchlist_data_health.py -q
```

结果：
- ✅ 26 passed

## 产出文件

- `agent/src/tools/watchlist_tool.py`
- `scripts/backtest_trend_indicators.py`
- `agent/tests/test_strategy_watchlist_tools.py`
- `agent/tests/test_watchlist_data_health.py`

## 完成结论

Phase 07-02 已完成：
- watchlist 分析路径现在会在分析前执行本地数据健康门禁
- 至少一个真实回测入口现在会在执行前执行同样的门禁
- required 本地数据失败会阻断执行，auxiliary 告警不会误阻断
- 整个 REQ-001 已从 deferred backlog 落地为可执行能力
