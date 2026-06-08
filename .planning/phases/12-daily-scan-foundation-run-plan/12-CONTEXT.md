# Phase 12: Daily Scan Foundation & Run Plan - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 12 只交付 v2.2 daily scan 的“启动骨架 + run plan”。本阶段要让用户能运行一个 local-data-first 的 daily scan 命令，完成 watchlist 输入验证、路径安全检查、Parquet engine 依赖确认，以及 normalized scan plan 输出。

本阶段 **不** 实现远程 refresh、data-health gate 执行语义、Composite strategy 扫描、最终 Markdown 报告或完整 artifact writer；这些分别属于 Phase 13-16。

Phase 12 依赖 Phase 11 的 Canonical Symbol Format 与数据源格式映射合同；watchlist/run plan 中的 symbol 必须使用 Phase 11 定义的 canonical format。

</domain>

<decisions>
## Implementation Decisions

### 命令形态

- **D-01:** Phase 12 采用 Claude 推荐方案：先实现 repo-level command/script 作为 daily scan 的稳定入口，推荐路径为 `scripts/daily_scan_report.py`，后续 phase 再接入 `agent/cli/_legacy.py` / MCP tool wrapper。
- **D-02:** 命令参数先固定为后续 pipeline 可复用的最小集合：`--watchlist`, `--data-dir`, `--output-dir`, `--now`, `--format json|text`，并支持 `--plan-only` 或等价 dry-run 模式来只生成/展示 scan plan。
- **D-03:** Phase 12 必须保持 local-data-first：默认命令不得调用远程 provider，不实现 `--refresh`。如 planner 需要预留 refresh 扩展点，只能作为未来字段/注释，不得触发任何网络数据获取。
- **D-04:** CLI exit semantics 在 Phase 12 先覆盖输入/路径/依赖层：成功为 `0`，watchlist/config/路径验证错误为 `2`；data-health gate 和 scan runtime exit codes 留给后续 phases 扩展。

### Run Plan 输出

- **D-05:** Phase 12 的核心产物是 normalized scan plan，而不是策略结果。推荐输出 `run_plan.json`（机器可读）和 text summary（人可读）。
- **D-06:** `run_plan.json` 至少包含：`schema_version`, `run_id`, `generated_at`, `local_data_only`, resolved `watchlist_path`, `data_dir`, `output_dir`, intended artifact paths, 以及每个 symbol 的 `symbol`, `name`, `market`, `timeframes`, required timeframes, cache file paths, and validation warnings/errors。
- **D-07:** `run_id` 应可由 `--now` 确定，方便测试和重复运行。默认输出根目录为 repo-relative `reports/daily_scan/`，具体目录建议形如 `reports/daily_scan/YYYY-MM-DD/<watchlist_stem>/<run_id>/`。
- **D-08:** Phase 12 的 scan plan 只描述“将会检查/加载什么”，不读取 OHLCV 数据、不执行 health gate、不生成 candidates。

### 路径安全

- **D-09:** 默认路径均为 repo-relative：watchlist 默认在 `watchlist/` 下，data dir 默认 `data/`，output dir 默认 `reports/daily_scan/`。
- **D-10:** Phase 12 应拒绝 path traversal 和逃逸 repo/output root 的路径。若实现需要支持绝对路径，必须显式 resolve 并证明仍在允许 root 内；否则优先拒绝。
- **D-11:** 输出目录创建必须安全、确定，并避免误覆盖已有 run。Phase 12 可先只创建 run directory / run_plan，不写最终 report artifacts。

### Watchlist validation 严格度

- **D-12:** 以下问题应作为 hard failure：watchlist 不存在或不安全、缺少 required columns、空 watchlist、重复 symbol、无法解析 market、无法解析 required timeframe、无法为 symbol/timeframe 解析 cache path。
- **D-13:** 非阻断 optional metadata（如 `multiplier`, `max_lots`, `ATR`）格式问题可以记录为 warning 并使用默认值，但必须写入 run plan 的 warnings，不能静默吞掉。
- **D-14:** Validation error 输出必须结构化，JSON 模式不得混入 progress/log 文本；日志/进度走 stderr 或不输出。

### Dependency / stack

- **D-15:** Phase 12 应检查并显式声明 `pyarrow` Parquet engine（如缺失则加入 `pyproject.toml` 和/或 `agent/requirements.txt`，以项目实际依赖清单为准）。
- **D-16:** 不引入新的 CLI framework、workflow scheduler、database、Polars、market data vendor 或 dashboard stack。

### Claude's Discretion

用户明确表示“我看不懂，都按你推荐方案实施”。因此 planner/researcher 可按上述推荐默认方案继续，不需要再向用户询问 Phase 12 内部技术取舍。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning scope

- `.planning/PROJECT.md` — v2.2 project context, validated capabilities, and out-of-scope boundaries.
- `.planning/REQUIREMENTS.md` — Phase 12 requirement mapping: STK-01, CLI-01, CLI-02, WLS-01, WLS-02.
- `.planning/ROADMAP.md` — Phase 12 goal and success criteria.
- `.planning/STATE.md` — current GSD state and next-step routing.
- `.planning/phases/11-symbol-format-mapping-contract-data-source-translation-optimization/11-PLAN.md` — upstream canonical symbol contract prerequisite once Phase 11 is planned/executed.

### v2.2 research

- `.planning/research/SUMMARY.md` — synthesized MVP scope, architecture direction, watch-outs, and build order.
- `.planning/research/ARCHITECTURE.md` — proposed `agent/src/scan/` package, data flow, dependency direction, and build order.
- `.planning/research/FEATURES.md` — table stakes, anti-features, and MVP cut.
- `.planning/research/PITFALLS.md` — failure modes to avoid, especially data-health bypass, markdown-only output, and unsafe paths.
- `.planning/research/STACK.md` — stack additions, especially explicit `pyarrow` dependency and “what not to add”.

### Existing code references

- `agent/src/data/watchlist.py` — `WatchlistReader`, `load_raw()`, `get_timeframes()`, and current parsing defaults.
- `agent/src/data/watchlist_data_health.py` — timeframe normalization, market dir resolution, cache path resolution, gate report schema. Phase 12 should reuse normalization/path ideas but not run gate semantics yet.
- `agent/src/data/symbol_translator.py` — canonical symbol contract and vendor translation once Phase 11 lands.
- `scripts/analyze_watchlist.py` — existing legacy script shape; useful as cautionary reference because it mixes progress stdout and legacy analyzer/report behavior.
- `agent/cli/_legacy.py` — existing argparse/exit code patterns and CLI constants.
- `.planning/codebase/STACK.md` — current stack and dependency map.
- `.planning/codebase/INTEGRATIONS.md` — market data provider and local cache integration context.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `WatchlistReader.load_raw()` in `agent/src/data/watchlist.py`: can provide raw watchlist rows for Phase 12 validation/run-plan generation.
- `parse_timeframes()`, `normalize_timeframe()`, `required_and_declared_timeframes()`, `resolve_market_dir()`, `resolve_cache_file()` in `agent/src/data/watchlist_data_health.py`: reusable normalization/path logic for scan plan cache paths.
- `agent/cli/_legacy.py`: existing argparse-style CLI patterns and exit code constants (`EXIT_SUCCESS`, `EXIT_RUN_FAILED`, `EXIT_USAGE_ERROR`).

### Established Patterns

- Current watchlist tools already favor JSON-safe serialization and path safety; Phase 12 should follow that style.
- Existing `scripts/analyze_watchlist.py` prints progress to stdout and uses legacy `WatchlistAnalyzer`; Phase 12 should not copy that behavior for JSON mode.
- v2.2 research recommends `agent/src/scan/` as the future orchestration layer, but Phase 12 can start with script + models/helpers and leave later scan/report phases to expand it.

### Integration Points

- New command/script should be callable without remote provider credentials.
- Later phases will connect Phase 12 run plan into `check_watchlist_data`, `CompositeTrendStrategy`, artifact writer, Markdown renderer, and MCP/tool wrappers.
- Phase 12 should establish schemas/names that later phases can extend instead of replacing.

</code_context>

<specifics>
## Specific Ideas

- User delegated Phase 12 gray-area decisions to Claude’s recommended plan.
- The chosen direction is conservative and incremental: script/command + validation + run plan first, strategy/reporting later.
- Keep report/trading language out of Phase 12; this phase is about run intent and safety.

</specifics>

<deferred>
## Deferred Ideas

- Remote refresh modes — future requirement `REF-01`.
- Exchange-calendar/session-aware freshness — future requirement `CAL-01`.
- Daily delta/history — future requirements `DELTA-01`, `HIST-01`.
- Ranking/dashboard/notifications/trading UX — future requirements or out-of-scope items.
- Full data-health gate behavior — Phase 13.
- Composite signal bucket scan — Phase 14.
- Markdown report and full deterministic artifacts — Phase 15.
- Verification closure — Phase 16.

</deferred>

---

*Phase: 12-Daily Scan Foundation & Run Plan*
*Context gathered: 2026-06-08; shifted from original Phase 11 after symbol-format prerequisite insertion*
