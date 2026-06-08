# Phase 12: Daily Scan Foundation & Run Plan - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 12-Daily Scan Foundation & Run Plan
**Areas discussed:** Recommended defaults delegated to Claude

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| 命令形态 | daily scan 入口叫法、flags 形态、是否先脚本再接入正式 CLI。现有 `scripts/analyze_watchlist.py` 和 `agent/cli/_legacy.py` 可参考。 | |
| Run Plan | scan plan 要输出哪些字段、JSON 文件名、是否在分析前可单独预览。关系到 WLS-02。 | |
| 路径安全 | watchlist/data/output 路径默认值、是否限制在 repo 内、输出目录是否按日期/run_id 固定。 | |
| 验证严格度 | watchlist validation 对重复 symbol、unsupported timeframe、缺少字段等是直接失败还是 warning。 | |
| Claude recommended defaults | 用户表示看不懂具体灰区选择，并要求“都按你推荐方案实施”。 | ✓ |

**User's choice:** “我看不懂，都按你推荐方案实施”

**Notes:** Claude therefore locked the recommended defaults in `12-CONTEXT.md`: repo-level script first, local-data-first, minimal stable flags, normalized `run_plan.json`, safe deterministic output directory, strict required validation, optional metadata warnings, explicit `pyarrow`, no new frameworks/stacks.

---

## Phase Shift Note

This phase was originally Phase 11. On 2026-06-08, user requested a prerequisite “数据源格式映射功能优化” phase. Claude inserted `Phase 11: Symbol Format Mapping Contract & Data Source Translation Optimization`, shifting this phase to Phase 12.

---

## Claude's Discretion

- Command shape and run-plan schema may be designed by Claude/planner within the constraints captured in `12-CONTEXT.md`.
- Planner should avoid re-asking user about Phase 12 implementation choices unless a real blocker appears.

## Deferred Ideas

- Remote refresh
- Exchange calendar freshness
- Daily delta/history
- Ranking/dashboard/notifications/trading UX
- Full data-health gate, signal scan, Markdown report, and verification closure are later v2.2 phases.
