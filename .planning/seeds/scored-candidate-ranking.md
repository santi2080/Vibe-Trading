---
title: Scored candidate ranking
developed_from: daily-scan-report-direction
trigger_condition: Daily Scan Report 使用一段时间后，需要在候选分组内进一步排序或自动挑选 Top candidates
planted_date: 2026-06-07
---

# Scored Candidate Ranking Seed

## 想法

未来可以为 Daily Scan Report 增加候选评分或排序系统，将信号一致性、风险回报、状态变化和数据健康合成一个 candidate score。

## 为什么暂缓

当前阶段刚完成 CompositeTrendStrategy 回测验证。如果立即引入强排名或 Top 10 score，容易让报告看起来比实际验证程度更精确，形成过度确定性的交易暗示。

Daily Scan Report MVP 应先采用分组式输出：

- Actionable Candidates
- Watch Candidates
- Risk / Excluded

等实际使用中发现候选数量过多、同组内难以判断优先级，或积累了足够复盘样本后，再启动评分系统。

## 触发条件

满足以下任一条件时，可以重新激活此 seed：

1. Daily Scan Report 的 actionable/watch candidates 经常过多，需要排序
2. 用户开始记录报告候选后的真实表现，需要回测/复盘评分维度
3. 需要自动生成 Top candidates 给通知系统或 Web UI
4. 需要比较不同 candidate selection heuristics 的效果

## 可能评分维度

- Composite READY 状态
- MTES / SuperTrend 方向一致性
- 最近状态变化：WAIT → READY、方向反转、趋势确认
- ATR 风险距离与潜在空间
- 数据健康完整度
- 信号冲突程度
- 历史回测表现或近期策略源表现

## 注意

评分系统必须先定义可验证目标，不应只做主观加权。推荐先用 historical replay 或 report outcome review 验证 score 是否真的提升候选质量。
