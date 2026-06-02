# Phase 07-01 Summary: Watchlist Data Health Tool + MCP Exposure

## 完成状态
- **计划**: 07-01
- **状态**: ✅ 完成
- **日期**: 2026-06-02

## 实现内容

### 1. 新增 registry tool: `check_watchlist_data`
在 `agent/src/tools/watchlist_tool.py` 中新增 `CheckWatchlistDataTool`：

- 通过 `_resolve_watchlist_path()` 先做 watchlist 目录边界校验
- 复用 `agent/src/data/watchlist_data_health.py` 的 `check_watchlist_data()`
- 统一使用标准本地数据目录：`data/{market}/{symbol}/{timeframe}.parquet`
- 返回机器可读 JSON：
  - `status`
  - `watchlist`
  - `checked_at`
  - `data_dir`
  - `gate`
  - `rules`
  - `items`
- 支持可选 `now` ISO 时间戳用于确定性校验
- 非法 `now` 返回 `error_type="validation"`

### 2. 新增 MCP wrapper: `check_watchlist_data`
在 `agent/mcp_server.py` 中新增 MCP 同名 wrapper：

- 对外暴露 `check_watchlist_data(watchlist_path, now)`
- 通过 `_get_registry().execute("check_watchlist_data", params)` 委托执行
- 不重复实现任何 data-health 检查逻辑
- 保持 MCP 输出与 registry tool 输出完全同形

### 3. 测试覆盖增强
在 `agent/tests/test_strategy_watchlist_tools.py` 中补充：

- `check_watchlist_data` 已注册到 tool registry
- 成功/失败 JSON 合同校验
- `rules.market_overrides["us_futures:1h"] == "24h"`
- watchlist 路径逃逸拦截测试（`../pyproject.toml`）
- 非法 `now` 输入校验
- MCP wrapper 委托检查

## 关键设计决策

1. **单一真相源**
   - 所有本地数据健康逻辑继续以 `watchlist_data_health.py` 为准
   - tool / MCP 只做暴露和参数校验

2. **路径安全前置**
   - 在读取 watchlist 之前先执行 `_resolve_watchlist_path()`
   - 阻止访问 `watchlist/` 目录外部路径

3. **JSON 合同保持一致**
   - registry 与 MCP 都返回统一结构
   - 便于 agent、CLI、外部 MCP 客户端复用

## 验证

```bash
.venv/bin/python -m pytest agent/tests/test_strategy_watchlist_tools.py -q
```

结果：
- ✅ 14 passed

## 产出文件

- `agent/src/tools/watchlist_tool.py`
- `agent/mcp_server.py`
- `agent/tests/test_strategy_watchlist_tools.py`

## 完成结论

Phase 07-01 已完成：
- Agent 用户现在可以显式请求 watchlist 本地数据健康检查
- MCP 客户端可以通过同名工具拿到同一份 gate JSON
- 路径安全、时间戳校验、JSON 合同均有测试覆盖
