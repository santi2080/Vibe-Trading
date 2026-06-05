# Phase 08: Establish Composite Strategy Signal Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 08-establish-composite-strategy-signal-layer
**Areas discussed:** 信号合同

---

## 信号合同

### Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| 信号合同 | 定义 TradingSignal / EntryResult 的字段、方向、置信度、risk hints、metadata 和与现有 TrendResult 的关系。 | ✓ |
| 组合规则 | 决定多策略如何合成：加权投票、gate-first、leader/follower、confluence score，及默认权重。 | |
| 冲突处理 | 当 MTES v2/v3、SuperTrend、entry timing 给出相反或弱信号时，应该 BLOCK、WAIT、降级还是保留 explain-only。 | |
| 接入口径 | 决定 CompositeStrategy 输出给谁消费：backtest、watchlist analysis、signal execution、MCP/tool；以及是否先做 Python API 而非 CLI/UI。 | |

**User's choice:** 信号合同
**Notes:** 用户只选择了信号合同作为本轮讨论范围。

### Direction semantics

| Option | Description | Selected |
|--------|-------------|----------|
| LONG/SHORT/WAIT | 交易信号直接面向执行层，使用 LONG、SHORT、WAIT；同时保留 trend_direction=BULL/BEAR/NEUTRAL 用于解释。 | |
| BULL/BEAR/NEUTRAL | 沿用 TrendResult 方向语义，信号层不直接表达交易动作；执行层再转换为 LONG/SHORT/WAIT。 | ✓ |
| BUY/SELL/HOLD | 更接近传统交易术语，但容易混淆开仓、平仓、调仓，后续需要额外字段区分。 | |
| 由 Claude 决定 | 由 Claude 按现有代码和后续可扩展性选择默认合同。 | |

**User's choice:** BULL/BEAR/NEUTRAL
**Notes:** TradingSignal 的核心方向字段锁定为 `BULL / BEAR / NEUTRAL`，不直接表达下单动作。

### Readiness / status

| Option | Description | Selected |
|--------|-------------|----------|
| 需要 readiness | 保留 direction=BULL/BEAR/NEUTRAL，同时用 readiness=READY/WAIT/BLOCKED/EXHAUSTED 表示能否进入执行层。 | |
| 只用 status | 用 status=VALID/NO_SIGNAL/FILTERED/INVALID 表示信号是否可消费，不额外区分 ready/wait/block。 | |
| 只用 confidence | 不设 readiness/status，由 confidence 和 score 阈值让下游自行判断。 | |
| 由 Claude 决定 | 由 Claude 按现有 TrendResult.readiness/status 设计最贴合的信号合同。 | ✓ |

**User's choice:** 由 Claude 决定
**Notes:** Claude 决定保留 `status` 与 `readiness` 两层状态，因为现有 `TrendResult` 已区分技术有效性和执行准备度。

### Score fields

| Option | Description | Selected |
|--------|-------------|----------|
| score + confidence | `signal_score=-100..100` 表示方向强度，`confidence=0..1` 表示可信度；贴合现有 TrendResult.signed_score/confidence。 | |
| confluence only | 只输出 confluence_score=0..100，方向单独存；强调多策略一致性，但弱化 signed score。 | |
| 多分数并存 | 同时输出 signal_score、confidence、confluence_score、risk_score；信息完整但合同更重。 | |
| 由 Claude 决定 | 由 Claude 按最小可用合同设计，保留可扩展 metadata。 | ✓ |

**User's choice:** 由 Claude 决定
**Notes:** Claude 决定使用最小稳定顶层合同：`signal_score: -100..100`、`confidence: 0..1`、`components: dict[str, float]`。

### Explainability depth

| Option | Description | Selected |
|--------|-------------|----------|
| 标准解释 | 包含 reasons、warnings、components、source_results，让 backtest/report/MCP 都能解释信号来源。 | ✓ |
| 精简解释 | 只保留 explanation 字符串和 metadata；合同轻，但后续排查冲突和回测归因较弱。 | |
| 完整溯源 | 保存每个子策略完整原始输出；可审计性最强，但对象可能较重，报告/序列化更复杂。 | |
| 由 Claude 决定 | 由 Claude 按 Phase 8 最小可用 + 后续可扩展原则决定。 | |

**User's choice:** 标准解释
**Notes:** TradingSignal 应包含 `reasons`、`warnings`、`components`、`source_results`、`metadata`。

### Completion gate

| Option | Description | Selected |
|--------|-------------|----------|
| 写入 Context | 当前决策已经足够支持 Phase 8 规划，先生成 CONTEXT.md，后续细节交给 plan-phase 拆解。 | ✓ |
| 继续细化 | 继续讨论字段命名、EntryResult 是否存在、source_results 序列化粒度等细节。 | |
| 讨论其他区域 | 返回灰区选择，继续讨论组合规则、冲突处理或接入口径。 | |

**User's choice:** 写入 Context
**Notes:** 用户确认当前信号合同决策足够，写入 Phase 8 CONTEXT。

---

## Claude's Discretion

- 是否同时保留 `status` 和 `readiness`：Claude 决定保留两者。
- 分数字段组织：Claude 决定使用 `signal_score + confidence + components` 的最小稳定合同。

## Deferred Ideas

- 组合规则、冲突处理、接入口径未在本轮深入讨论。
- `LONG / SHORT / WAIT`、`BUY / SELL / HOLD` 和订单执行语义推迟到执行适配层或后续阶段。
