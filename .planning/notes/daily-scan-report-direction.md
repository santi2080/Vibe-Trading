---
title: Daily Scan Report productization direction
date: 2026-06-07
context: GSD explore session after v2.1 composite-strategy-backtest completion
---

# Daily Scan Report 产品化方向

## 背景

v2.0 已完成复合策略信号层，v2.1 / Phase 09 已完成 CompositeTrendStrategy 回测验证与 UAT。下一步不优先继续堆策略，也不直接进入实盘执行，而是把已有策略、信号、回测与数据健康能力收敛成日常可用的产品化闭环。

项目核心价值仍然是：**Your Personal Trading Agent — one command to empower your agent with comprehensive trading capabilities**。

## 决策

下一阶段优先探索并规划 **Daily Scan Report Loop**：一条命令基于 watchlist 生成每日扫描 Markdown 报告。

第一版报告偏向人读，不做 JSON/API/通知，也不做自动交易。

## 报告结构

建议报告采用“先概览后候选”的结构：

1. **Overview**
   - watchlist 覆盖率
   - 数据健康摘要
   - 多空分布
   - READY / WAIT / CONFLICT 数量

2. **Actionable Candidates**
   - Composite READY
   - MTES + SuperTrend 方向一致
   - 数据健康通过
   - 给出方向、理由与风险提示

3. **Watch Candidates**
   - 接近 READY
   - 状态刚发生变化
   - 单策略强但 composite 未确认
   - 需要继续观察

4. **Risk / Excluded**
   - 数据不健康
   - 信号冲突
   - 波动异常
   - 缺失关键指标

## 重要取舍

暂不做强排序或 Top 10 score。当前阶段更适合做 **分组式候选报告**，避免制造“精确但未验证”的排名错觉。

如需同组内展示顺序，可使用朴素规则：

- 状态刚变化的排前面
- Composite READY 优先于单策略 READY
- 数据质量更完整的排前面
- 同方向信号更多的排前面

## 后续路线

1. 先用 Markdown 报告验证日常使用价值
2. 使用一段时间后，再考虑 JSON artifact、通知、Web/API
3. 等真实使用反馈积累后，再设计 candidate scoring / ranking
