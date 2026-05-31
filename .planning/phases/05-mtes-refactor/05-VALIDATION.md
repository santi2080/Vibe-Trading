# MTES v2 验证计划

**版本**: v1.0  
**日期**: 2026-05-31

---

## 验证目标

验证新的"方向为主、强度辅助"评分体系：
1. 评分输出范围正确 (-100 ~ +100)
2. 方向判定独立于评分
3. 强度评分正确计算
4. 向后兼容旧 API

---

## 验证用例

### 验证 1: 强趋势场景

**输入**: 明确的上涨趋势
- 价格在 200 日均线上方
- 均线向上倾斜
- 200 日收益率 > 10%
- ADX > 30

**预期输出**:
```
direction = "BULL"
direction_signal = 80 ~ 100
strength_score = 70 ~ 90
trend_score = 60 ~ 100 (正值)
trend_state = "BULL_STRONG"
confidence = 0.7 ~ 0.9
```

### 验证 2: 弱趋势场景

**输入**: 方向明确但强度弱
- 价格在均线上方
- 均线走平
- 收益率 < 5%
- ADX < 20

**预期输出**:
```
direction = "BULL"
direction_signal = 50 ~ 70
strength_score = 30 ~ 50
trend_score = 30 ~ 60 (正值但较低)
trend_state = "BULL_CONFIRMED" 或 "BULL_EARLY"
confidence = 0.5 ~ 0.7
```

### 验证 3: 震荡场景

**输入**: 无明确方向
- 价格在均线附近波动
- 均线走平
- 收益率接近 0
- ADX < 15

**预期输出**:
```
direction = "NEUTRAL"
direction_signal = 0
strength_score = 30 ~ 50
trend_score = -20 ~ +20 (接近 0)
trend_state = "NEUTRAL_CHOPPY"
confidence = 0.3 ~ 0.5
```

### 验证 4: 强下跌场景

**输入**: 明确的下跌趋势
- 价格在均线下方
- 均线向下倾斜
- 收益率 < -10%
- ADX > 30

**预期输出**:
```
direction = "BEAR"
direction_signal = -80 ~ -100
strength_score = 70 ~ 90
trend_score = -100 ~ -60 (负值)
trend_state = "BEAR_STRONG"
confidence = 0.7 ~ 0.9
```

---

## 验证脚本

```python
# scripts/validate_mtes_v2.py
import pandas as pd
import numpy as np
from agent.src.analysis.major_trend_evaluator import MajorTrendEvaluator

def test_strong_bull():
    """验证强上涨趋势"""
    # 生成测试数据: 稳定上涨
    dates = pd.date_range('2023-01-01', periods=300, freq='D')
    close = 100 * np.exp(np.linspace(0, 0.5, 300))  # 50% 涨幅
    
    df = pd.DataFrame({
        'datetime': dates,
        'open': close * 0.99,
        'high': close * 1.02,
        'low': close * 0.98,
        'close': close,
        'volume': 1e6
    })
    
    evaluator = MajorTrendEvaluator()
    result = evaluator.evaluate(df, asset_class='stock')
    
    assert result.direction == "BULL", f"Expected BULL, got {result.direction}"
    assert result.trend_score > 0, f"Expected positive score, got {result.trend_score}"
    assert result.trend_score >= 60, f"Expected BULL_STRONG, got {result.trend_score}"
    print(f"✅ Strong Bull: direction={result.direction}, score={result.trend_score}")

def test_choppy():
    """验证震荡场景"""
    # 生成测试数据: 震荡
    dates = pd.date_range('2023-01-01', periods=300, freq='D')
    close = 100 + 10 * np.sin(np.linspace(0, 10, 300))  # 震荡
    
    df = pd.DataFrame({
        'datetime': dates,
        'open': close * 0.99,
        'high': close * 1.01,
        'low': close * 0.99,
        'close': close,
        'volume': 1e6
    })
    
    evaluator = MajorTrendEvaluator()
    result = evaluator.evaluate(df, asset_class='stock')
    
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"
    assert abs(result.trend_score) < 30, f"Expected low score, got {result.trend_score}"
    print(f"✅ Choppy: direction={result.direction}, score={result.trend_score}")

def test_score_range():
    """验证评分范围"""
    # 测试所有场景
    evaluator = MajorTrendEvaluator()
    
    # 生成多组测试数据
    test_cases = [
        ("strong_bull", generate_strong_bull_data()),
        ("weak_bull", generate_weak_bull_data()),
        ("choppy", generate_choppy_data()),
        ("weak_bear", generate_weak_bear_data()),
        ("strong_bear", generate_strong_bear_data()),
    ]
    
    for name, df in test_cases:
        result = evaluator.evaluate(df, asset_class='stock')
        assert -100 <= result.trend_score <= 100, f"{name}: score {result.trend_score} out of range"
        assert 0 <= result.confidence <= 1, f"{name}: confidence {result.confidence} out of range"
        print(f"✅ {name}: score={result.trend_score}, confidence={result.confidence}")

if __name__ == "__main__":
    test_strong_bull()
    test_choppy()
    test_score_range()
    print("\n✅ All validation tests passed!")
```

---

## 执行验证

```bash
# 运行验证脚本
cd /Users/iagent/projects/vibe-trading
python scripts/validate_mtes_v2.py

# 运行单元测试
python -m pytest agent/tests/test_major_trend_evaluator.py -v

# 对比新旧评分
python scripts/compare_mtes_v1_v2.py
```

---

## 验证检查清单

- [ ] 强上涨趋势评分 > 60
- [ ] 弱上涨趋势评分 30~60
- [ ] 震荡趋势评分接近 0
- [ ] 弱下跌趋势评分 -60~-30
- [ ] 强下跌趋势评分 < -60
- [ ] direction 与评分符号一致
- [ ] confidence 在合理范围
- [ ] 趋势状态分类正确
