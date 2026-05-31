# MTES 策略重构规格说明书

**版本**: v1.0  
**日期**: 2026-05-31  
**状态**: Draft  

---

## 1. 概述与动机

### 1.1 问题陈述

当前 MTES 的六大维度采用**等权重平均**方式计算趋势评分：
- Direction: 15%
- Strength: 15%
- Structure: 25%
- Momentum: 15%
- Volatility Regime: 15%
- MTF: 15%

**核心问题**：
1. **方向信息被稀释** — 当趋势方向明确时，其他指标的表现应该是"确认"角色，而非独立评分
2. **评分逻辑不一致** — 方向得分只能决定方向(Direction)，但不能影响整体评分
3. **指标冲突难以处理** — 当 strength=90 但 direction=NEUTRAL 时，错误的高分可能被误用

### 1.2 改进目标

重构为**方向为主、强度辅助**的评分体系：

```
新评分 = 方向信号 × (1 + 强度修正系数)

其中：
- 方向信号: -100 (强空) ~ 0 (中性) ~ +100 (强多)
- 强度修正系数: 0.0 ~ 1.0 (综合其他5个维度)
```

### 1.3 设计原则

1. **方向主导** — 评分必须首先明确方向，强度评分仅作为方向可信度的调整因子
2. **可解释性** — 每个指标对最终评分的贡献必须清晰可追溯
3. **向后兼容** — 保持 API 兼容，现有调用方无需修改
4. **可配置** — 保留资产类别权重配置能力

---

## 2. 新评分体系设计

### 2.1 核心公式

```
趋势评分 = 方向信号值 × 方向可信度权重 + 综合强度分 × 强度权重

其中：
- 方向信号值: -100 ~ +100 (BULL 为正，BEAR 为负，NEUTRAL 为 0)
- 方向可信度权重: 0.5 ~ 0.8 (取决于方向信号的确定性)
- 综合强度分: 0 ~ 100 (其他5个维度的加权平均)
- 强度权重: 0.2 ~ 0.5

最终输出:
- trend_score: -100 ~ +100 (带符号的趋势强度)
- trend_state: 7种状态分类
- confidence: 0.0 ~ 1.0 (评分可信度)
```

### 2.2 维度重新分组

| 组别 | 维度 | 角色 | 说明 |
|------|------|------|------|
| **方向组** | direction | 主要信号 | 直接决定趋势方向 |
| **强度组** | strength | 趋势确认 | ADX/DI 确认趋势强度 |
| | structure | 位置确认 | 价格在区间中的位置 |
| | momentum | 动量确认 | 3/6/12月动量方向 |
| | volatility_regime | 环境确认 | 趋势友好度 |
| | mtf | 框架确认 | 多时间框架一致性 |

### 2.3 方向信号计算

```python
def calculate_direction_signal(df, asset_class) -> tuple[float, str, float]:
    """
    返回: (signal_value, direction, confidence)
    
    signal_value: -100 ~ +100
    direction: "BULL" / "BEAR" / "NEUTRAL"
    confidence: 0.0 ~ 1.0 (方向可信度)
    """
    # 4个方向信号
    signals = {
        "price_vs_long_ma": compare_sign(current, long_ma, tolerance=0.005),  # -1/0/1
        "intermediate_vs_long_ma": compare_sign(intermediate, long_ma, tolerance=0.0025),
        "long_ma_slope": compare_sign(long_slope, 0.0, tolerance=0.001),
        "long_horizon_return": compare_sign(long_return, 0.0, tolerance=0.01),
    }
    
    net = sum(signals.values())  # -4 ~ +4
    agreement = abs(net) / 4.0  # 0.0 ~ 1.0
    
    # 方向判定
    if net >= 2:
        direction = "BULL"
        signal_value = 50 + agreement * 50  # 50 ~ 100
    elif net <= -2:
        direction = "BEAR"
        signal_value = -50 - agreement * 50  # -50 ~ -100
    else:
        direction = "NEUTRAL"
        signal_value = 0.0
    
    # 方向可信度
    confidence = agreement  # 0.0 ~ 1.0
    
    return signal_value, direction, confidence
```

### 2.4 综合强度分计算

```python
def calculate_strength_score(df, direction, config) -> float:
    """
    综合其他5个维度计算强度分: 0 ~ 100
    """
    strength_score = score_strength(df, direction)    # ADX/DI
    structure_score = score_structure(df, direction)   # 区间位置
    momentum_score = score_momentum(df, direction)    # 动量
    regime_score = score_volatility_regime(df)        # 趋势效率
    mtf_score = score_mtf_alignment(df, direction)   # MTF对齐
    
    # 等权重平均
    scores = [strength_score, structure_score, momentum_score, regime_score, mtf_score]
    return sum(scores) / len(scores)
```

### 2.5 最终评分公式

```python
def calculate_final_score(direction_signal, direction_confidence, strength_score) -> tuple[float, float]:
    """
    direction_signal: -100 ~ +100
    direction_confidence: 0.0 ~ 1.0
    strength_score: 0 ~ 100
    
    返回: (trend_score, confidence)
    trend_score: -100 ~ +100
    confidence: 0.0 ~ 1.0
    """
    # 方向权重 = 基础方向权重 + 方向可信度加成
    direction_weight = 0.6 + direction_confidence * 0.2  # 0.6 ~ 0.8
    strength_weight = 1.0 - direction_weight            # 0.4 ~ 0.2
    
    # 方向组贡献
    direction_contribution = direction_signal * direction_weight / 100
    
    # 强度组贡献 (标准化到 -1 ~ +1)
    strength_contribution = (strength_score - 50) / 50 * strength_weight
    
    # 合成
    raw_score = direction_contribution + strength_contribution
    trend_score = clamp(raw_score * 100, -100, 100)  # -100 ~ +100
    
    # 综合可信度
    confidence = direction_confidence * 0.7 + (strength_score / 100) * 0.3
    
    return round(trend_score, 2), round(confidence, 3)
```

### 2.6 趋势状态分类

```python
def classify_trend_state(score, direction) -> str:
    """
    score: -100 ~ +100
    direction: "BULL" / "BEAR" / "NEUTRAL"
    """
    if direction == "BULL":
        if score >= 60: return "BULL_STRONG"
        if score >= 30: return "BULL_CONFIRMED"
        if score >= 0: return "BULL_EARLY"
    elif direction == "BEAR":
        if score <= -60: return "BEAR_STRONG"
        if score <= -30: return "BEAR_CONFIRMED"
        if score <= 0: return "BEAR_EARLY"
    return "NEUTRAL_CHOPPY"
```

---

## 3. 输出契约变更

### 3.1 新 MajorTrendResult

```python
@dataclass(frozen=True)
class MajorTrendResult:
    """MTES v2 评分结果"""
    
    # 核心输出 (新)
    trend_score: float          # -100 ~ +100 (带符号)
    direction: str              # "BULL" / "BEAR" / "NEUTRAL"
    confidence: float           # 0.0 ~ 1.0
    
    # 趋势状态 (保留)
    trend_state: str            # 7种状态
    
    # 资产类别 (保留)
    asset_class: str
    
    # 分项得分 (保留)
    sub_scores: dict[str, float]  # 加权后的分项得分
    raw_scores: dict[str, float]   # 原始分项得分
    
    # 方向组 (新增)
    direction_signal: float     # -100 ~ +100
    direction_confidence: float # 0.0 ~ 1.0
    
    # 综合强度 (新增)
    strength_score: float       # 0 ~ 100
    
    # 元数据 (保留)
    regime: str                 # "trend_friendly" / "mixed" / "choppy"
    regime_flags: list[str]
    top_drivers: list[dict]
    explanation: str
    metadata: dict
```

### 3.2 API 兼容性

```python
# 旧 API (v1) - 仍然可用
result = evaluator.evaluate(df)
old_score = result.trend_score  # 0 ~ 100 (绝对值)

# 新 API (v2) - 推荐使用
result = evaluator.evaluate(df)
new_score = result.trend_score  # -100 ~ +100 (带符号)
direction = result.direction     # 独立获取方向
confidence = result.confidence   # 新增可信度

# 向后兼容转换
if hasattr(result, 'direction_signal'):
    # v2 模式
    pass
else:
    # v1 模式 - 转换旧结果
    v2_score = (100 if result.trend_score > 50 else -100 if result.trend_score < 50 else 0)
```

---

## 4. 资产类别权重调整

### 4.1 新权重配置

```python
# 方向组权重 (主要)
DIRECTION_WEIGHTS = {
    "stock": 0.65,    # 方向占 65%
    "etf": 0.60,
    "futures": 0.70,  # 期货方向信号更可靠
    "crypto": 0.55,   # 加密货币波动大，强度辅助更重要
    "fx": 0.75,       # 外汇方向信号非常可靠
}

# 强度组权重 (辅助)
STRENGTH_WEIGHTS = {
    "stock": 0.35,
    "etf": 0.40,
    "futures": 0.30,
    "crypto": 0.45,
    "fx": 0.25,
}
```

### 4.2 强度组内部权重

```python
STRENGTH_COMPONENTS = {
    "stock": {"strength": 0.25, "structure": 0.25, "momentum": 0.20, "regime": 0.15, "mtf": 0.15},
    "futures": {"strength": 0.30, "structure": 0.25, "momentum": 0.15, "regime": 0.15, "mtf": 0.15},
    "crypto": {"strength": 0.20, "structure": 0.20, "momentum": 0.25, "regime": 0.20, "mtf": 0.15},
    "fx": {"strength": 0.20, "structure": 0.25, "momentum": 0.15, "regime": 0.20, "mtf": 0.20},
}
```

---

## 5. 验收标准

### 5.1 功能验收

- [ ] 新评分输出 trend_score 范围为 -100 ~ +100
- [ ] direction 独立于 trend_score
- [ ] confidence 反映评分可信度
- [ ] 趋势状态分类正确
- [ ] 向后兼容旧 API

### 5.2 数值验收

- [ ] 相同输入数据，新旧评分方向一致
- [ ] 强趋势品种（ADX>25）新评分绝对值 > 旧评分
- [ ] 震荡品种（ADX<20）新评分绝对值 < 旧评分
- [ ] NEUTRAL 方向时，trend_score 接近 0

### 5.3 测试验收

- [ ] 单元测试全部通过
- [ ] 与历史回测数据一致
- [ ] 边界情况（数据不足、无MTF等）处理正确

---

## 6. 实现计划

| 任务 | 描述 | 预估时间 |
|------|------|----------|
| 1 | 创建新评分函数 calculate_direction_signal | 1h |
| 2 | 创建新评分函数 calculate_strength_score | 1h |
| 3 | 重构 evaluate 方法集成新逻辑 | 2h |
| 4 | 更新 MajorTrendResult 数据类 | 0.5h |
| 5 | 更新测试用例 | 2h |
| 6 | 运行回归测试验证 | 1h |
| 7 | 更新文档和示例 | 1h |

**总预估**: 8.5h

---

## 7. 风险与备选方案

### 7.1 风险

1. **评分范围变化** — 从 0-100 变为 -100~+100，可能影响现有使用方
   - **缓解**: 保持 API 兼容，提供转换函数

2. **历史一致性** — 新评分可能与历史评分差异较大
   - **缓解**: 提供 v1 到 v2 的转换对照表

3. **边界情况** — NEUTRAL 方向的评分边界
   - **缓解**: 严格定义 NEUTRAL 判定条件

### 7.2 备选方案

如果新评分体系表现不佳，可以采用：
- **混合模式**: 保留旧评分，新增 direction_score 字段
- **可选模式**: 通过配置切换新旧评分逻辑

---

## 8. 参考

- 原始 MTES 实现: `agent/src/analysis/major_trend_evaluator.py`
- 测试用例: `agent/tests/test_major_trend_evaluator.py`
- 现有回测脚本: `scripts/backtest_trend_indicators.py`
