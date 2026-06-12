# Phase 21: 风控模块增强（简化版）

**目标**: 增强回测场景下的风控计算功能  
**优先级**: P1  
**基于 Spike**: `spikes/risk-management-research-20260612.md`  
**预计工时**: 2-3 小时  
**版本**: v1.0（实盘功能另开 Phase）

---

## 📋 背景

### 设计原则
1. **回测优先** - 当前不用于实盘，只实现回测所需的风控计算
2. **接口统一** - 与现有 `risk_manager.py` 风格一致
3. **模块独立** - 风控模块独立，策略模块调用
4. **可扩展** - 未来可平滑增加实盘风控规则

### 现有能力
- ✅ 仓位计算 (`calculate_position_size`)
- ✅ 熔断机制 (`apply_circuit_breaker`)
- ✅ Kelly Criterion (`calculate_kelly_criterion`)
- ✅ 风险收益比 (`calculate_risk_reward_ratio`)

### 本次新增
- ⭐ 止损价计算 (`calculate_stop_loss`)
- ⭐ 止盈价计算 (`calculate_take_profit`)
- ⭐ 风险参数综合计算 (`calculate_risk_params`)

---

## 🎯 目标

为 `risk_manager.py` 增强以下功能：

1. **止损价计算** - 基于 ATR 或固定百分比
2. **止盈价计算** - 基于 R:R 比率或固定目标
3. **综合风险参数** - 返回完整的入场参数（止损、止盈、仓位）

---

## 📊 实施计划

### Task 1: 增强 RiskConfig

**文件**: `agent/src/analysis/risk_manager.py`

**新增配置项**:
```python
@dataclass
class RiskConfig:
    # 已有...
    
    # 新增：止损止盈配置
    stop_loss_method: str = "atr"      # "atr" | "fixed_pct"
    stop_loss_pct: float = 0.02        # 固定百分比止损 (2%)
    take_profit_method: str = "rr"     # "rr" | "fixed" | "atr_mult"
    take_profit_rr: float = 2.0        # R:R 比率 (2:1)
    trailing_stop: bool = False         # 是否启用追踪止损
    trailing_pct: float = 0.01          # 追踪止损百分比
```

### Task 2: 实现止损价计算

**函数**: `calculate_stop_loss(entry_price, atr, direction, config)`

**方法**:

| 方法 | 公式 | 适用场景 |
|------|------|---------|
| `atr` | `止损价 = 入场价 - ATR × 倍数` | 波动性市场 |
| `fixed_pct` | `止损价 = 入场价 × (1 - 百分比)` | 稳定市场 |

**输入**:
```python
entry_price: float    # 入场价格
atr: float           # ATR 值
direction: TradeDirection  # LONG = 1, SHORT = -1
config: RiskConfig   # 配置
```

**输出**:
```python
@dataclass
class StopLossResult:
    stop_price: float       # 止损价格
    method: str             # 使用的方法
    risk_amount: float     # 风险金额
    risk_pct: float        # 风险百分比
```

### Task 3: 实现止盈价计算

**函数**: `calculate_take_profit(entry_price, stop_loss, direction, config)`

**方法**:

| 方法 | 公式 | 适用场景 |
|------|------|---------|
| `rr` | `止盈价 = 入场价 + (入场价-止损价) × R:R` | 标准 R:R 交易 |
| `fixed` | `止盈价 = 入场价 × (1 + 目标%)` | 固定目标 |
| `atr_mult` | `止盈价 = 入场价 + ATR × 倍数` | ATR 比例止盈 |

**输入**:
```python
entry_price: float    # 入场价格
stop_loss: float      # 止损价格
direction: TradeDirection  # LONG = 1, SHORT = -1
config: RiskConfig   # 配置
```

**输出**:
```python
@dataclass
class TakeProfitResult:
    tp_price: float         # 止盈价格
    method: str             # 使用的方法
    reward_amount: float    # 潜在收益金额
    reward_risk_ratio: float  # 实际 R:R 比率
```

### Task 4: 实现综合风险参数计算

**函数**: `calculate_risk_params(entry_price, atr, equity, direction, config)`

**输入**:
```python
entry_price: float    # 入场价格
atr: float           # ATR 值
equity: float        # 当前权益
direction: TradeDirection  # LONG = 1, SHORT = -1
config: RiskConfig   # 配置
```

**输出**:
```python
@dataclass
class RiskParams:
    """完整的风险参数"""
    entry_price: float
    stop_loss: StopLossResult
    take_profit: TakeProfitResult
    position_size: float       # 仓位大小
    risk_amount: float          # 风险金额
    reward_amount: float        # 潜在收益
    risk_reward_ratio: float    # R:R 比率
    stop_loss_pct: float       # 止损百分比
    take_profit_pct: float     # 止盈百分比
```

### Task 5: 单元测试

**文件**: `agent/tests/test_risk_manager.py`

**测试用例**:
- [ ] ATR 止损计算（多头、空头）
- [ ] 固定百分比止损计算
- [ ] R:R 止盈计算
- [ ] 固定目标止盈计算
- [ ] 综合风险参数计算
- [ ] 边界情况处理

---

## 🏗️ 接口设计

### 统一输入格式

```python
from agent.src.analysis.signal_executor import TradeDirection

# 所有函数接受统一参数
def calculate_xxx(
    entry_price: float,        # 入场价（必需）
    atr: Optional[float],     # ATR（可选，用于 ATR 方法）
    direction: TradeDirection, # 交易方向（必需）
    config: RiskConfig,        # 配置（必需）
):
    ...
```

### 统一输出格式

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class XxxResult:
    """统一使用 frozen dataclass 作为返回类型"""
    value: float
    method: str
    details: dict
```

### 与现有代码集成

```python
# 1. RiskConfig 增强
from agent.src.analysis.risk_manager import RiskConfig

config = RiskConfig(
    max_risk_per_trade=0.02,
    atr_multiplier=2.0,
    stop_loss_method="atr",
    take_profit_rr=2.0,
)

# 2. 风控计算
from agent.src.analysis.risk_manager import (
    calculate_stop_loss,
    calculate_take_profit,
    calculate_risk_params,
)

# 3. 策略使用
params = calculate_risk_params(entry_price=100, atr=2.0, equity=10000, direction=TradeDirection.LONG, config=config)

# 返回完整参数
print(f"止损: {params.stop_loss.stop_price}")
print(f"止盈: {params.take_profit.tp_price}")
print(f"仓位: {params.position_size}")
```

---

## 📁 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/src/analysis/risk_manager.py` | 修改 | 增强 RiskConfig，新增计算函数 |
| `agent/tests/test_risk_manager.py` | 修改 | 新增测试用例 |

---

## ✅ 验收标准

### 功能验收
- [ ] ATR 方法止损计算正确
- [ ] 固定百分比止损计算正确
- [ ] R:R 止盈计算正确
- [ ] 综合参数返回完整
- [ ] 多空方向处理正确

### 测试验收
- [ ] 新增测试全部通过
- [ ] 回归测试全部通过
- [ ] 覆盖率 > 80%

### 接口验收
- [ ] 返回类型一致（frozen dataclass）
- [ ] 参数命名统一
- [ ] 与现有代码风格一致

---

## 🔄 未来扩展（Full 版）

| 功能 | 说明 | 触发条件 |
|------|------|---------|
| 规则引擎 | 订单拦截、规则检查 | 实盘部署 |
| 持仓限制 | 集中度、最大持仓数 | 组合管理 |
| 相关性监控 | 高相关性告警 | 多策略组合 |
| 流动性评估 | 变现天数估算 | 数字资产 |

---

## 📝 更新日志

| 日期 | 描述 |
|------|------|
| 2026-06-12 | 创建简化版计划 v1.0 |
| 2026-06-12 | 保存原计划到 full/PLAN-full.md |

---

**Plan 状态**: ✅ 完成  
**版本**: simplified v1.0  
**Planned by**: Claude Sonnet  
**Date**: 2026-06-12
