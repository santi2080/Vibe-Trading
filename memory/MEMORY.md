# Vibe-Trading 记忆索引

## 项目信息

- **路径**: `/Users/iagent/projects/vibe-trading`
- **Stars**: 8,200+
- **技术栈**: FastAPI + React 19 + LLM Multi-Agent + MCP
- **虚拟环境**: `.venv`
- **当前分支**: `main` (已合并 feature/strategy-taxonomy-optimization)

## 策略层架构（已完成）

### 内置策略 (`agent/backtest/strategies/`)

| 类型 | 策略 | 标签 |
|------|------|------|
| Trend | `trend_ema_adx`, `trend_macd`, `trend_dual_ema` | `trend`, `ema`, `adx` |
| Pullback | `pullback_rsi`, `pullback_bollinger`, `pullback_stochastic`, `pullback_fibonacci` | `pullback`, `rsi` |
| Entry | `entry_breakout`, `entry_volume_spike`, `entry_vwap`, `entry_confluence` | `entry`, `breakout`, `volume` |

### 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **StrategyRegistry** | `__init__.py` | 策略注册、过滤、元数据 |
| **StrategyComposer** | `composer.py` | Trend+Pullback+Entry 串联 |
| **MTFAligner** | `mtf.py` | 多周期对齐（防前视偏差） |
| **generate_standard_report** | `comparison.py` | 标准绩效对比报告 |
| **strategy_tools** | `agent/src/agent/strategy_tools.py` | Agent 策略工具 |

### 使用示例

```python
# 策略过滤
StrategyRegistry.list_by_tags(['ema'])
StrategyRegistry.filter(type=TREND, tags=['ema'])

# 策略组合
composer = StrategyComposer()
composer.set_trend('trend_ema_adx')
result = composer.generate(df)

# MTF 对齐
aligner = MTFAligner()
aligner.align_htf_to_ltf(htf_data=d1, ltf_data=h1)

# 标准报告
generate_standard_report(strategies, symbol='GC=F')
```

## 数据层架构

### HybridDataFetcher

| 组件 | 功能 |
|------|------|
| SymbolRouter | 自动识别 9 种市场类型 |
| SourcePool | 多数据源管理、健康跟踪 |
| DataFusion | 多源智能选择、数据验证 |

## Git 提交

```
8ac688a feat(agent): add strategy tools for Agent context integration
1e317cf feat(strategy): add standard report format
99b3074 feat(strategy): enhance strategy layer with registry, composer, and MTF
9fd80cb feat(strategy): add taxonomy system with SKILL metadata
```

## 会话记录

- [2026-05-25 策略层优化完成](session_compact_20260525_155000.md)
