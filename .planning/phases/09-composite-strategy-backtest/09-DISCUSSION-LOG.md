# Phase 09: composite-strategy-backtest - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-06
**Phase:** 09-composite-strategy-backtest
**Areas discussed:** 信号映射逻辑, 非信号处理, 配置模式, 信号输出

---

## 信号映射逻辑

| Option | Description | Selected |
|--------|-------------|----------|
| 方向 + 就绪即开仓 | BULL + READY → 开多仓；BEAR + READY → 开空仓；其他情况空仓。简单直接，符合信号语义。 | ✓ |
| BULL/BEAR 才开仓，NEUTRAL 平仓 | BULL → 多仓；BEAR → 空仓；NEUTRAL → 平仓（不论 readiness）。只读方向。 | |
| 双门控：方向确认 + 就绪验证 | 先检查方向（BULL/BEAR），再验证 readiness == READY 才开仓，WAIT/BLOCKED 跳过。 | |

**User's choice:** 方向 + 就绪即开仓
**Notes:** —

---

## 非信号处理

| Option | Description | Selected |
|--------|-------------|----------|
| NEUTRAL 平仓，其他就绪状态跳过 | NEUTRAL → 平仓（任何方向的多空都平）；WAIT/BLOCKED/EXHAUSTED/UNKNOWN → 跳过，保持当前仓位。 | |
| readiness 决定一切 | NEUTRAL 时检查 readiness：READY → 平仓（明确中性）；非 READY → 跳过。逻辑统一。 | |
| 保持仓位不过早平仓 | NEUTRAL 不平仓（可能短期震荡），只有信号反向才平仓。WAIT/BLOCKED 等继续持有。 | |

**User's choice:** 使用默认退出策略：距入场后最高（做多）或最低（做空）2倍ATR退出
**Notes:** trailing stop 逻辑：做多时以入场以来的最高价减去2倍ATR作为止损，做空时以入场以来的最低价加上2倍ATR作为止损。

---

## 配置模式

| Option | Description | Selected |
|--------|-------------|----------|
| YAML 配置文件 | 独立配置文件定义组合：MTESv3 + SuperTrend，权重，就绪条件。时间周期、数据源也在其中。 | |
| Python 代码内联 | 在回测脚本中直接实例化 CompositeTrendStrategy，传入各策略对象和权重。灵活但耦合。 | |
| JSON + 注册表 | JSON 配置 + 策略注册表（已有 registry.py），回测脚本引用策略名称自动组装。 | |

**User's choice:** 我不懂，你来选
**Notes:** 用户选择让 Claude 推荐，推荐 YAML + 注册表模式，复用现有 registry.py。

---

## 信号输出

| Option | Description | Selected |
|--------|-------------|----------|
| 仅组合信号 | 回测只输出最终的组合 TradingSignal（direction/score/readiness），各子策略的独立结果在 metadata 里。最小输出。 | |
| 独立信号 + 组合信号 | 每个 bar 输出：子策略A/B/C 的独立方向 + 置信度 + 组合信号。满足 BKST-03。 | |
| 关键节点信号 | 仅在信号状态变化（方向切换/就绪状态变化）时输出，节省存储。正常 bar 无信号变化则跳过。 | ✓ |

**User's choice:** 关键节点信号
**Notes:** —

---

## Claude's Discretion

配置模式由 Claude 决定：采用 YAML + 注册表模式，复用 `backtest/strategies/registry.py`。

## Deferred Ideas

无

