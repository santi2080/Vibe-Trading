# 策略技能分类

本目录包含按功能分类的策略技能。

## 目录结构

```
skills/
├── strategy-generate/      # 策略生成（核心工作流）
├── trend/                 # 趋势判断策略
├── entry/                 # 入场信号策略
├── pullback/             # 回调入场策略
├── risk/                  # 风险管理策略
├── alpha-zoo/            # Alpha 因子库
└── [other]/             # 其他专业策略
```

## 分类说明

### trend/ - 趋势判断

判断市场整体方向，过滤逆势交易。

| 技能 | 说明 | 推荐周期 |
|------|------|---------|
| `ema_trend` | EMA 双均线趋势判断 | 1d, 4h |
| `adx_trend` | ADX 趋势强度 | 1d, 4h |

### entry/ - 入场信号

生成具体买卖点信号。

| 技能 | 说明 | 推荐周期 |
|------|------|---------|
| `range_filter` | 区间过滤入场 | 1h, 4h |

### pullback/ - 回调入场

在趋势中寻找回撤买入/反弹卖出的机会。

| 技能 | 说明 | 推荐周期 |
|------|------|---------|
| `atr-pullback` | ATR 回调检测 | 1d, 4h |
| `fib-pullback` | 斐波那契回撤 | 1d, 4h |

### risk/ - 风险管理

仓位管理、止损止盈、风险控制。

| 技能 | 说明 |
|------|------|
| `atr-position` | ATR 仓位计算 |
| `trailing-stop` | 追踪止损 |

## 标签系统

每个技能使用以下标签维度：

### 功能标签（必须）

- `trend` - 趋势判断
- `entry` - 入场信号
- `pullback` - 回调入场
- `exit` - 出场信号
- `risk` - 风险管理

### 市场标签

- `cn_futures` - 中国期货
- `us_futures` - 美国期货
- `a_stock` - A股
- `us_stock` - 美股
- `crypto` - 加密货币

### 技术标签

- `ema` - EMA/MA 体系
- `macd` - MACD 体系
- `ict` - ICT/SMC 体系
- `ichimoku` - 一目均衡表

### 复杂度标签

- `simple` - 1-3 参数
- `medium` - 4-10 参数
- `advanced` - 10+ 参数

## SKILL.yaml 规范

每个技能必须包含 `SKILL.yaml` 文件：

```yaml
name: strategy-name
description: 策略说明
category: trend|entry|pullback|exit|risk
tags:
  - trend          # 功能标签
  - cn_futures    # 市场标签
  - simple         # 复杂度标签
timeframes: [1d, 4h, 1h]
markets: [cn_futures, us_futures]
parameters:
  period: 14
  threshold: 0.5
```

## 添加新技能

1. 在对应分类目录创建技能文件夹
2. 添加 `SKILL.yaml` 文件
3. 添加代码实现文件
4. 更新本目录 README.md

---

**最后更新**: 2026-05-25
