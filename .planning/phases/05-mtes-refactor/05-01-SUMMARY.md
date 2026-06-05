# Phase 05-01 Summary: MTES v2 Direction-Primary Scoring

## 完成状态

- **计划**: 05-01
- **状态**: ✅ 完成
- **日期**: 2026-06-05
- **阶段**: Phase 05 — MTES v2 Direction-Primary Scoring

## 实现内容

### 1. MTES v2 数据契约与兼容配置

`agent/src/analysis/major_trend_evaluator.py` 已提供 v1/v2 兼容的主配置与结果契约：

- `MajorTrendConfig.use_v2_scoring` 默认启用 v2 scoring
- `MajorTrendResult` 暴露 v2 字段：
  - `direction_signal` (`-100 ~ +100`)
  - `direction_confidence` (`0.0 ~ 1.0`)
  - `strength_score` (`0 ~ 100`)
  - `strength_components`
  - `use_v2_scoring`
- `to_dict()` 输出包含 v2 字段，保持机器可读合同
- `to_v1_dict()` 提供旧格式转换，保留兼容路径

### 2. 方向主导评分流程

`MajorTrendEvaluator.evaluate()` 已集成 v2 评分流程：

1. 计算六维原始分：`direction / strength / structure / momentum / volatility_regime / mtf`
2. `calculate_direction_signal()` 生成带符号方向信号和方向可信度
3. `calculate_strength_score()` 聚合 5 个强度确认维度
4. `calculate_final_score_v2()` 输出带符号 `trend_score`
5. `classify_trend_state_v2()` 输出 7 类趋势状态

### 3. STRONG 状态强度确认修正

本次补齐 Phase 05 artifact 时发现 `scripts/validate_mtes_v2.py` 的弱上涨验证场景失败：

- 失败前：`weak_bull` 被分类为 `BULL_STRONG`
- 原因：v2 分类仅用 signed score 阈值判断 STRONG，未要求强度组确认
- 修正：`classify_trend_state_v2(score, direction, strength_score)` 在判定 `BULL_STRONG` / `BEAR_STRONG` 时要求 `strength_score >= 50.0`

新增覆盖：

- `test_v2_strong_state_requires_strength_confirmation()`
- 验证 BULL/BEAR 两个方向的 STRONG 降级与确认边界

### 4. 验证脚本弱上涨 fixture 校准

`validate_mtes_v2.py` 的 `weak_bull` fixture 已调整为弱上涨场景：

- 总涨幅约 `1.2%`
- 方向应为 `BULL`
- 强度不应达到 STRONG 确认
- 预期分类：`BULL_CONFIRMED` 或 `BULL_EARLY`

## 关键设计决策

1. **方向仍然主导最终 signed score**
   - `direction_signal` 决定正负方向
   - `strength_score` 不反转方向，只参与确认和可信度

2. **STRONG 需要双重确认**
   - signed score 达到阈值不足以进入 STRONG
   - 还需要强度组达到确认阈值，避免“弱趋势但方向一致”被夸大为强趋势

3. **保持 v1/v2 兼容**
   - `use_v2_scoring=False` 仍可走旧评分路径
   - v2 字段为新增字段，不破坏现有 result 基础字段

## 验证

```bash
.venv/bin/python -m pytest agent/tests/test_major_trend_evaluator.py -q
```

结果：

- ✅ `15 passed in 0.35s`

```bash
.venv/bin/python scripts/validate_mtes_v2.py
```

结果：

- ✅ `7/7` 验证通过
- ✅ 评分范围、方向独立性、趋势状态分类、v2 新字段、v1 向后兼容、资产类别权重、强度组权重全部通过

## 产出文件

- `agent/src/analysis/major_trend_evaluator.py`
- `agent/tests/test_major_trend_evaluator.py`
- `scripts/validate_mtes_v2.py`
- `.planning/phases/05-mtes-refactor/05-01-SUMMARY.md`
- `.planning/phases/05-mtes-refactor/05-VALIDATION.md`

## 完成结论

Phase 05-01 已完成并补齐 GSD 工件：

- MTES v2 direction-primary signed scoring 已存在并通过验证
- STRONG 状态现在要求强度确认，避免弱趋势误判为强趋势
- Phase 05 的 PLAN/SUMMARY artifact 已配平，可解除 GSD 进度中 `22 plans / 21 summaries` 的不一致
