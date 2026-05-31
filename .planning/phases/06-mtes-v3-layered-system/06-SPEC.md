# MTES v3 分层递进趋势系统 - 规格说明书

## 阶段信息

| 字段 | 内容 |
|------|------|
| **阶段编号** | 06 |
| **阶段名称** | MTES v3 - 分层递进趋势系统 |
| **状态** | planned |
| **创建日期** | 2026-06-01 |

## 目标概述

将当前 MTES 6 维度加权评分架构重构为**三层递进趋势系统**，消除 SMA 滞后问题，引入 SMC 市场结构分析和 Elder 三重滤网。

## 架构设计

### 分层结构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: 预处理层 (Preprocessor)                          │
│  - ADX 预过滤 (< 20 剔除)                                 │
│  - 数据质量验证                                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 大周期趋势锁定 (MTF Trend Lock)                 │
│  - SMC 市场结构分析 (HH/HL, BOS, MSS)                     │
│  - Elder 三重滤网第一滤 (MACD 柱状图)                      │
│  - Ichimoku 云图                                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 趋势强度确认 (Strength Confirmation)            │
│  - ADX 门槛过滤 (≥ 25)                                    │
│  - 动量背离检测 (MACD)                                    │
│  - 波动率 Regime 适配                                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 入场时机 (Entry Timing)                        │
│  - FVG 回踩检测                                            │
│  - Elder 第二/三滤网 (RSI 极值 + Buy Stop)               │
│  - Range Filter 信号                                       │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Preprocessor (预处理层)

```python
@dataclass
class PreprocessorConfig:
    adx_threshold: float = 20.0  # ADX < 20 → 剔除
    min_data_points: int = 200      # 最少数据点
    min_volume: float = 0.0        # 最小成交量

class Preprocessor:
    def filter(self, df: pd.DataFrame, config: PreprocessorConfig) -> bool:
        """返回 True 表示品种通过预过滤"""
        adx = calculate_adx(df)
        if adx < config.adx_threshold:
            return False
        if len(df) < config.min_data_points:
            return False
        return True
```

### 2. SMCAnalyzer (市场结构分析)

```python
@dataclass
class Swing:
    index: int
    high: float
    low: float
    swing_type: Literal["HH", "HL", "LH", "LL"]

@dataclass
class MarketStructureResult:
    trend: Literal["BULL", "BEAR", "NEUTRAL"]
    swings: List[Swing]
    bos_confirmed: bool
    mss_confirmed: bool
    last_liquidity_sweep: Optional[dict]

class SMCAnalyzer:
    def find_swings(self, df: pd.DataFrame, threshold: float = 0.005) -> List[Swing]:
        """识别波段高低点"""
        
    def detect_bos(self, swings: List[Swing], current_trend: str) -> bool:
        """结构破坏检测 (Break of Structure)"""
        
    def detect_mss(self, swings: List[Swing], current_trend: str) -> bool:
        """市场结构转变 (Market Structure Shift)"""
        
    def detect_liquidity_sweep(self, df: pd.DataFrame, swings: List[Swing]) -> Optional[dict]:
        """流动性扫掠检测"""
```

### 3. ElderTripleScreen (三重滤网)

```python
@dataclass
class ElderSignal:
    layer1_trend: Literal["BULL", "BEAR", "NEUTRAL"]
    layer2_pullback: bool
    layer3_trigger: Literal["READY", "WAIT"]
    macd_histogram_slope: float
    rsi_value: float

class ElderTripleScreen:
    def layer1_mtf_trend(self, df: pd.DataFrame) -> str:
        """第一滤网: MACD 柱状图斜率 + EMA 位置"""
        macd_hist = calculate_macd_histogram(df)
        return "BULL" if macd_hist.slope > 0 else "BEAR"
    
    def layer2_pullback_extremity(self, df: pd.DataFrame, mtf_trend: str) -> bool:
        """第二滤网: RSI/Stochastic 超卖检测"""
        rsi = calculate_rsi(df)
        if mtf_trend == "BULL" and rsi < 30:
            return True
        return False
    
    def layer3_trigger(self, df: pd.DataFrame, entry_zone: float) -> str:
        """第三滤网: Buy Stop 突破执行"""
        pass
```

### 4. TrendStrengthFilter (趋势强度)

```python
class TrendStrengthFilter:
    def filter(self, df: pd.DataFrame, mtf_bias: str) -> StrengthRating:
        """趋势强度评级"""
        # STRONG: ADX≥30, 无背离, Regime 匹配
        # READY: ADX≥25, 无背离
        # WEAK: ADX≥20
        # EXHAUSTED: ADX<20
```

### 5. EntryTiming (入场时机)

```python
class EntryTiming:
    def find_entry(self, df: pd.DataFrame, mtf_bias: str, strength: StrengthRating) -> EntrySignal:
        """寻找入场时机"""
        # FVG 回踩 + RSI 极值 + Range Filter 同向
```

## 输出数据结构

```python
@dataclass
class MTESv3Result:
    # 预过滤
    passed_prefilter: bool
    
    # Layer 1: 大周期趋势
    mtf_trend: Literal["BULL", "BEAR", "NEUTRAL"]
    smc_structure: dict
    elder_trend: str
    ichimoku_trend: str
    layer1_confidence: float  # 0-1
    
    # Layer 2: 趋势强度
    strength: Literal["STRONG", "READY", "WEAK", "EXHAUSTED"]
    adx_value: float
    divergence_detected: bool
    
    # Layer 3: 入场信号
    entry_signal: Literal["LONG", "SHORT", "WAIT"]
    entry_zone: Optional[float]
    stop_loss: Optional[float]
    
    # 综合评分
    final_score: float  # -100 ~ +100
    final_confidence: float  # 0-1
```

## 与现有 MTES v2 兼容

```python
class MTESv3Adapter:
    """兼容 MTES v2 输出的适配器"""
    
    def to_v2_format(self, v3_result: MTESv3Result) -> dict:
        """转换为 MTES v2 格式"""
        return {
            "trend_score": v3_result.final_score,
            "direction": v3_result.mtf_trend,
            "confidence": v3_result.final_confidence,
            "regime": "TRENDING" if v3_result.strength != "EXHAUSTED" else "CHOPPY"
        }
```

## 验收标准

| 标准 | 描述 | 验证方法 |
|------|------|---------|
| V1 | 批量扫描 100 品种 < 5 秒 | 性能测试 |
| V2 | Layer 1 与原 MTES 方向一致率 > 80% | 对比测试 |
| V3 | ADX ≥ 25 与 STRONG/READY 匹配率 > 90% | 逻辑验证 |
| V4 | 所有组件单元测试覆盖 > 80% | pytest --cov |
| V5 | 向后兼容 MTES v2 输出格式 | 适配器测试 |

## 实施阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| Phase 01 | Layer 0 + Layer 1 SMC | P1 |
| Phase 02 | Layer 1 Elder + Ichimoku | P1 |
| Phase 03 | Layer 2 ADX + 背离 | P2 |
| Phase 04 | Layer 3 FVG + RSI | P2 |
| Phase 05 | 整合测试 + 适配器 | P3 |

---

*文档版本: v1.0*
*创建者: Claude Code*
