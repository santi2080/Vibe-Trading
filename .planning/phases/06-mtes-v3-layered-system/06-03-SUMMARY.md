# Phase 06-03 Summary: Layer 2 Strength + Layer 3 Entry

## 完成状态
- **计划**: 06-03
- **状态**: ✅ 完成
- **日期**: 2026-06-01

## 实现内容

### 1. Layer 2 - 趋势强度过滤 (layer2/)

#### ADXStrengthFilter
基于 ADX 值的趋势强度评级：

```python
class ADXStrengthFilter:
    STRONG: ADX >= 30  → 强趋势
    READY:  ADX >= 25  → 趋势形成中
    WEAK:   ADX >= 20  → 弱趋势
    EXHAUSTED: ADX < 20 → 无趋势/震荡
```

#### MomentumDivergenceDetector
动量背离检测：

```python
class MomentumDivergenceDetector:
    # 检测顶背离：价格更高但 MACD 更低 → 看跌
    # 检测底背离：价格更低但 MACD 更高 → 看涨
    
    def analyze(df) -> DivergenceResult
        detected: bool
        divergence_type: BULLISH/BEARISH/HIDDEN_BULL/HIDDEN_BEAR
        strength: 0-1
```

### 2. Layer 3 - 入场时机 (layer3/)

#### EntryTiming
入场时机检测，结合多个信号：

```python
class EntryTiming:
    # 做多条件:
    # - 趋势方向为 BULL
    # - 强度评级为 STRONG 或 READY
    # - RSI < 35 (超卖) 或 FVG 看涨信号
    
    # 做空条件:
    # - 趋势方向为 BEAR
    # - 强度评级为 STRONG 或 READY
    # - RSI > 65 (超买) 或 FVG 看跌信号
    
    def find_entry(df, trend_direction, strength_rating) -> EntrySignal
        signal: LONG/SHORT/WAIT
        entry_price: 建议入场价
        stop_loss: 建议止损
```

#### FVG 检测
Fair Value Gap (供需失衡区域)：

```python
# 看涨 FVG: 第三根 K 线与第一根 K 线之间有缺口
# 看跌 FVG: 价格跌破第一根 K 线低点
```

## 架构设计

```
Layer 2: 趋势强度确认
├── ADXStrengthFilter         → ADX 阈值判断
└── MomentumDivergenceDetector → MACD 背离检测
    └── 影响: confidence 和 final_score

Layer 3: 入场时机
├── RSI 极值检测          → 超卖/超买
├── FVG 检测             → 回踩入场
└── Range Filter          → 趋势确认
```

## 新增文件

| 文件 | 描述 |
|------|------|
| `layer2/strength_filter.py` | ADX 强度过滤器 |
| `layer2/divergence.py` | 动量背离检测 |
| `layer2/__init__.py` | 模块导出 |
| `layer3/entry_timing.py` | 入场时机检测 |
| `layer3/__init__.py` | 模块导出 |
| `tests/test_strength_filter.py` | ADX 测试 |
| `tests/test_divergence.py` | 背离测试 |
| `tests/test_entry_timing.py` | 入场时机测试 |

## MTES v3 整合

更新 `mtes_v3.py` 主入口，整合所有层：

```python
class MTESv3:
    def analyze(df) -> MTESv3Result:
        # Layer 0: 预过滤 (ADX >= 20)
        prefilter_result = self.preprocessor.analyze(df)
        
        # Layer 1: 大周期趋势 (SMC + Elder + Ichimoku)
        mtf_trend = self.layer1.analyze(df)
        
        # Layer 2: 趋势强度 (ADX + 背离)
        strength = self.strength_filter.filter(df)
        divergence = self.divergence_detector.analyze(df)
        
        # Layer 3: 入场时机 (RSI + FVG)
        entry = self.entry_timing.find_entry(df)
        
        # 综合评分
        final_score = f(direction, strength, confidence)
```

## 依赖关系

- ✅ 依赖 Phase 06-01 (base.py)
- ✅ 依赖 Phase 06-02 (layer1)
- ✅ 为 Phase 06-04 (整合测试) 提供完整系统
