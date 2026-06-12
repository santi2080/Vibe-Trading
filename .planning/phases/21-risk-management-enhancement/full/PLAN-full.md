# Phase 21: 风控模块增强

**目标**: 基于 Spike 研究结果，为 vibe-trading 实现完整的风控模块  
**优先级**: P1  
**基于 Spike**: `spikes/risk-management-research-20260612.md`  
**预计工时**: 6-8 小时

---

## 📋 背景

### 现有能力
- ✅ ATR-Based 仓位计算 (`risk_manager.py`)
- ✅ 熔断机制 (日内损失限制)
- ✅ 多种组合优化器 (风险平价、均值方差)
- ✅ 性能指标计算 (Sharpe, Sortino, Calmar, VaR)

### 核心缺失
- ❌ 无内置止损止盈规则
- ❌ 无实时持仓限制规则
- ❌ 无动态相关性监控
- ❌ 无流动性风险评估

---

## 🎯 目标

1. **止损止盈系统** - 实现 ATR/固定百分比止损、追踪止盈
2. **持仓限制规则引擎** - 实现 vnpy 风格的可配置规则
3. **相关性监控** - 基于滚动窗口的实时相关性检查
4. **流动性风险评估** - 变现天数估算

---

## 📊 实施计划

### Wave 1: 止损止盈系统

#### Task 1.1: 止损规则
- 文件: `agent/src/analysis/risk_rules/stop_loss.py`
- 创建 `StopLossRule` 类
- 实现 ATR-based 止损计算
- 实现固定百分比止损
- 单元测试

#### Task 1.2: 止盈规则
- 文件: `agent/src/analysis/risk_rules/take_profit.py`
- 创建 `TakeProfitRule` 类
- 实现固定目标止盈
- 实现 R:R 比率止盈
- 实现追踪止盈
- 单元测试

#### Task 1.3: 括号订单
- 文件: `agent/src/analysis/risk_rules/bracket_order.py`
- 创建 `BracketOrder` 类
- 同时设置止损止盈
- 支持部分成交
- 单元测试

### Wave 2: 持仓限制规则引擎

#### Task 2.1: 规则基类
- 文件: `agent/src/analysis/risk_rules/base.py`
- 创建 `RiskRule` 抽象基类
- 定义 `RiskContext` 上下文
- 定义 `RiskResult` 返回结果
- 单元测试

#### Task 2.2: 持仓限制规则
- 文件: `agent/src/analysis/risk_rules/position_limits.py`
- 创建 `PositionLimitRule`
- 实现单币种最大仓位限制
- 实现集中度限制
- 实现最大持仓数限制
- 单元测试

#### Task 2.3: 风险规则引擎
- 文件: `agent/src/analysis/risk_rules/engine.py`
- 创建 `RiskRuleEngine` 类
- 实现规则注册和配置
- 实现规则链式检查
- 支持规则热更新
- 集成测试

### Wave 3: 高级风控功能

#### Task 3.1: 相关性监控
- 文件: `agent/src/analysis/risk_rules/correlation_monitor.py`
- 创建 `CorrelationMonitor` 类
- 实现滚动相关性计算
- 实现高相关性告警
- 单元测试

#### Task 3.2: 流动性风险
- 文件: `agent/src/analysis/risk_rules/liquidity_risk.py`
- 创建 `LiquidityRisk` 类
- 实现变现天数估算
- 实现流动性评分
- 单元测试

### Wave 4: 集成与文档

#### Task 4.1: 与现有 RiskManager 集成
- 在 `RiskManager` 中集成新规则引擎
- 更新 `can_take_trade()` 方法
- 集成测试

#### Task 4.2: 与 PortfolioTracker 集成
- 在开仓时调用风控检查
- 在持仓更新时调用风控检查
- 集成测试

#### Task 4.3: 文档与示例
- 更新 `agent/src/analysis/README.md`
- 创建使用示例

---

## 🏗️ 架构设计

```
agent/src/analysis/
├── risk_manager.py           # 已有: 基础风控
├── risk_rules/              # 新增: 风控规则模块
│   ├── __init__.py
│   ├── base.py             # RiskRule 基类
│   ├── stop_loss.py        # 止损规则
│   ├── take_profit.py      # 止盈规则
│   ├── bracket_order.py     # 括号订单
│   ├── position_limits.py   # 持仓限制
│   ├── correlation_monitor.py # 相关性监控
│   ├── liquidity_risk.py    # 流动性风险
│   └── engine.py           # 规则引擎
└── portfolio_tracker.py     # 已有: 组合追踪
```

---

## 📁 新增文件清单

| 文件 | 描述 | 行数估算 |
|------|------|---------|
| `risk_rules/__init__.py` | 模块初始化 | 30 |
| `risk_rules/base.py` | 规则基类 | 100 |
| `risk_rules/stop_loss.py` | 止损规则 | 150 |
| `risk_rules/take_profit.py` | 止盈规则 | 150 |
| `risk_rules/bracket_order.py` | 括号订单 | 120 |
| `risk_rules/position_limits.py` | 持仓限制 | 150 |
| `risk_rules/correlation_monitor.py` | 相关性监控 | 120 |
| `risk_rules/liquidity_risk.py` | 流动性风险 | 100 |
| `risk_rules/engine.py` | 规则引擎 | 200 |
| `tests/test_risk_rules.py` | 测试 | 300 |

**总计**: ~1400 行代码

---

## ✅ 验收标准

### 功能验收
- [ ] 止损规则正确计算止损价格
- [ ] 止盈规则正确计算止盈价格
- [ ] 规则引擎正确拦截违规订单
- [ ] 相关性监控正确检测高相关性
- [ ] 流动性风险正确估算变现天数

### 测试验收
- [ ] 所有新模块单元测试通过
- [ ] 集成测试通过
- [ ] 覆盖率 > 80%

---

## 🔧 技术要点

### 1. 规则检查流程
```python
def check_order(self, order_request: OrderRequest) -> RiskResult:
    for rule in self.rules:
        if not rule.active:
            continue
        result = rule.check(order_request)
        if not result.passed:
            return result
    return RiskResult(passed=True)
```

### 2. 止损计算
```python
# ATR-Based
stop_distance = atr * atr_multiplier
stop_price = entry_price - stop_distance  # 做多

# 固定百分比
stop_price = entry_price * (1 - fixed_pct)
```

---

## 🚀 快速开始

```python
from agent.src.analysis.risk_rules import (
    RiskRuleEngine,
    StopLossRule,
    TakeProfitRule,
    PositionLimitRule,
)

# 创建规则引擎
engine = RiskRuleEngine()

# 添加规则
engine.add_rule(StopLossRule(method="atr", atr_multiplier=2.0))
engine.add_rule(TakeProfitRule(method="rr", reward_risk=2.0))
engine.add_rule(PositionLimitRule(max_position_size=0.1))

# 检查订单
result = engine.check_order(order_request)
if not result.passed:
    print(f"Order rejected: {result.reason}")
```

---

## 📝 更新日志

| 日期 | 描述 |
|------|------|
| 2026-06-12 | 创建 Phase 21 计划 |

---

**Plan 状态**: ✅ 完成  
**Planned by**: Claude Sonnet  
**Date**: 2026-06-12
