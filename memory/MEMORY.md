# Vibe-Trading 记忆索引

## 项目信息

- **路径**: `/Users/iagent/projects/vibe-trading`
- **Stars**: 8,200+
- **技术栈**: FastAPI + React 19 + LLM Multi-Agent + MCP
- **虚拟环境**: `.venv`
- **当前分支**: `main`

## 数据源配置

| 数据源 | 状态 | Token | 用途 |
|--------|------|-------|------|
| **Tushare** | ✅ 已配置 | `a5b...` | A 股数据 |
| Yahoo Finance | ✅ 内置 | 无需配置 | 美股/期货 |
| AKShare | ✅ 内置 | 无需配置 | 备用数据源 |

### 测试结果
- Tushare: 14 条数据获取成功 (600519.SH)
- 相关测试: 141 passed

## 仓库设置（个人使用）

- **远程仓库**: `santi2080/Vibe-Trading` (个人 fork)
- **不再关联**: ~~HKUDS/Vibe-Trading~~ (上游仓库)
- **使用方式**: 作为个人独立项目使用

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

## 趋势指标准确性分析（2026-05-30）

### 分析脚本
- `scripts/analyze_trend_accuracy.py` - 趋势准确性与滞后性分析
- `scripts/compare_mtes_strategies.py` - MTES vs 经典策略对比
- `scripts/diagnose_mtes_vs_supertrend.py` - MTES vs SuperTrend 诊断

### 分析结论

| 指标 | 准确率 | 平均滞后 | 排名 |
|------|--------|---------|------|
| **MTES** | 81.7% | 7.7K | 🥇 |
| **ADX(14)>25** | 76.1% | 6.3K | 🥈 |
| **EMA(50/200)** | 58.6% | 7.1K | 🥉 |
| **SuperTrend** | 42.3% | 0.5K | 4 |

### 分市场推荐

| 市场 | 推荐指标 | 准确率 |
|------|---------|--------|
| 贵金属 | MTES | 81% |
| 股指期货 | ADX(14)>25 | 73% |
| 原油 | MTES | 86% |

### 关键发现
- MTES 上涨判断 100% 准确，下跌判断偏弱
- ADX 下跌判断 90%+ 准确，适合做空信号
- SuperTrend 滞后最小(0.5K)但准确率低(~42%)

## Git 提交

```
9154de6 docs(planning): sync milestone/phase state to completed
851ea01 docs(phase-01): complete phase execution
6a7a137 docs(01): add phase verification report
825f22a docs(01-04): add execution summary
0cc330f docs(01-04): finalize MTES validation plan artifact
```

## 会话记录

- [2026-05-30 趋势指标准确性分析](session_compact_20260530_144429.md)
- [2026-05-31 Phase 03-03 增强策略实现](session_compact_20260531_114200.md)

## Phase 03 实施状态 (2026-05-31)

### 已完成模块

| 模块 | 文件 | 测试 |
|------|------|------|
| 03-01 SuperTrend计算 | `agent/src/analysis/supertrend.py` | 35 passed |
| 03-02 交易指标 | `agent/src/analysis/supertrend_metrics.py` | 28 passed |
| 03-03 增强策略 | `agent/src/analysis/supertrend_enhancement.py` | 35 passed |

### 核心API

```python
# 增强策略配置
config = EnhancementConfig(
    trading_mode="auto",  # long_only/long_short
    use_range_filter=True,
    use_regime_filter=True,
    use_mtes_conflict_filter=False,
)

# 构建特征
features = build_enhancement_features(daily_df, weekly_df, market="futures")

# 生成信号
signals = generate_enhancement_signals(features, entry_family="pullback")

# 实验矩阵
matrix = build_experiment_matrix()  # E1-E8
```
