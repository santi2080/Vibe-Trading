# Phase 03: SuperTrend Enhancement Strategy - Pattern Map

**Mapped:** 2026-05-30  
**Files analyzed:** 11 inferred new/modified files  
**Analogs found:** 11 / 11  
**Context inputs:** Updated after `CONTEXT.md` and `03-RESEARCH.md` were created. Scope now reflects Phase 03 planned files and plan-checker feedback.

## Planned File Analog Addendum

| Planned File | Role | Closest Analog | Planner Usage |
|---|---|---|---|
| `agent/src/analysis/supertrend.py` | canonical indicator utility | `agent/src/analysis/major_trend_evaluator.py`; `scripts/analyze_trend_accuracy.py` | Use for corrected SuperTrend final-band implementation and completed-week alignment helpers. |
| `agent/src/analysis/supertrend_metrics.py` | trade metric/diagnostic utility | `agent/backtest/metrics.py`; `agent/tests/test_metrics.py`; `scripts/diagnose_mtes_vs_supertrend.py` | Use existing metrics where possible and add Phase 03 exposure/whipsaw/regime diagnostics. |
| `agent/src/analysis/supertrend_enhancement.py` | strategy feature/signal utility | `agent/backtest/strategies/trend.py`; `agent/src/analysis/major_trend_evaluator.py` | Build weekly ST anchor, RF confirmation, regime filters, entry families, MTES conflict filter. |
| `agent/tests/test_supertrend_calculation.py` | indicator tests | `agent/tests/test_major_trend_evaluator.py` | Deterministic fixtures for bands, warmup, no future data, weekly/daily no-lookahead. |
| `agent/tests/test_supertrend_enhancement_metrics.py` | metrics tests | `agent/tests/test_metrics.py` | Verify trade metrics, exposure, whipsaw, regime split serialization. |
| `agent/tests/test_supertrend_enhancement_strategy.py` | feature/signal tests | `agent/tests/test_mtes_strategy.py`; `agent/tests/backtest/strategies/test_strategies.py` | Verify anchor/confirmation/regime/entry/conflict/trading-mode behavior. |
| `agent/tests/test_supertrend_validation_plan.py` | document contract tests | `agent/tests/test_mtes_validation_plan.py` | Protect validation plan content. |
| `agent/tests/test_supertrend_enhancement_runner.py` | runner/report tests | `scripts/compare_mtes_strategies.py`; `agent/tests/test_validation.py` | Validate CLI/report rows and bounded matrix behavior. |
| `docs/SUPERTREND_ENHANCEMENT_VALIDATION_PLAN.md` | stable validation doc | `docs/MTES_BACKTEST_VALIDATION_PLAN.md` | Document baselines, metrics, costs, no-lookahead, parameter robustness. |
| `scripts/backtest_supertrend_enhancement.py` | experiment runner | `scripts/compare_mtes_strategies.py`; `scripts/backtest_trend_indicators.py` | Run baselines and enhanced combinations; write reports. |

## File Classification (Historical Reference — Not Current Execution Scope)

> 注意：本节是初始 pattern mapper 在 `CONTEXT.md` / `03-RESEARCH.md` 完成前推断的较宽文件集合，保留作历史参考。当前执行范围以本文件上方 `Planned File Analog Addendum` 和 `03-01` 至 `03-05` PLAN 为准。

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|
| `agent/src/analysis/supertrend.py` | utility / indicator | transform | `agent/src/analysis/major_trend_evaluator.py` + `scripts/analyze_trend_accuracy.py` | role-match |
| `agent/backtest/strategies/supertrend.py` | strategy | request-response / transform | `agent/backtest/strategies/trend.py` + `scripts/compare_mtes_strategies.py` | exact |
| `agent/backtest/strategies/__init__.py` | registry / package export | event-driven registration | `agent/backtest/strategies/__init__.py` | exact |
| `agent/backtest/strategies/registry.py` | registry | event-driven registration | `agent/backtest/strategies/registry.py` | exact |
| `agent/tests/test_supertrend_indicator.py` | test | transform validation | `agent/tests/test_major_trend_evaluator.py` | role-match |
| `agent/tests/test_supertrend_strategy.py` | test | strategy contract validation | `agent/tests/test_mtes_strategy.py` | exact |
| `agent/tests/test_supertrend_validation_plan.py` | test | document contract validation | `agent/tests/test_mtes_validation_plan.py` | exact |
| `docs/SUPERTREND_ENHANCEMENT_VALIDATION_PLAN.md` | docs / validation plan | batch / reporting | `docs/MTES_BACKTEST_VALIDATION_PLAN.md` | exact |
| `scripts/compare_supertrend_enhancement.py` | script | batch / file-I/O / reporting | `scripts/compare_mtes_strategies.py` | exact |
| `scripts/backtest_trend_indicators.py` | script modification | batch / file-I/O / reporting | existing same file | exact |
| `scripts/diagnose_mtes_vs_supertrend.py` or `scripts/diagnose_supertrend_variants.py` | script modification / diagnostic | batch / reporting | existing `scripts/diagnose_mtes_vs_supertrend.py` | exact |

## Current Trend Indicator Backtest Script Structure and Reusable Points

### `scripts/backtest_trend_indicators.py` (script, batch + file-I/O + reporting)

**Purpose:** monolithic exploratory script that defines indicators, loads local parquet OHLCV, evaluates direction/lead/noise metrics, and writes timestamped CSV/Markdown reports.

**Imports/path pattern** (lines 12-25):
```python
from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import warnings

import pandas as pd
import numpy as np
```

**Project path insertion** (lines 32-34):
```python
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))
```

**Result dataclass pattern** (lines 121-145):
```python
@dataclass
class IndicatorResult:
    """单个指标结果"""
    name: str
    direction_score: float = 0.0
    lead_score: float = 0.0
    noise_score: float = 0.0
    overall_score: float = 0.0
    bullish_rate: float = 0.0
    signal_count: int = 0
    trend_changes: int = 0

@dataclass
class SymbolResult:
    """单个品种结果"""
    symbol: str
    name: str
    market: str
    timeframe: str
    data_points: int = 0
    period: str = ""
    indicators: Dict[str, IndicatorResult] = field(default_factory=dict)
    best_indicator: str = ""
    best_score: float = 0.0
```

**Indicator interface pattern** (lines 152-167):
```python
class TrendIndicatorBase:
    """趋势指标基类"""

    name: str = "Base"

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算指标"""
        raise NotImplementedError

    def get_signal(self, df: pd.DataFrame) -> pd.Series:
        """获取信号: 1=多头, -1=空头, 0=震荡"""
        raise NotImplementedError

    def get_score(self, df: pd.DataFrame) -> pd.Series:
        """获取趋势评分: -100 到 +100"""
        raise NotImplementedError
```

**Reusable but risky current SuperTrend implementation** (lines 170-229):
```python
class SuperTrendIndicator(TrendIndicatorBase):
    """SuperTrend 指标"""
    name = "SuperTrend"

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.period).mean()
```

**Use this for:** script API shape and metric/report plumbing.  
**Do not blindly copy:** its SuperTrend band update is simplified and differs from `scripts/analyze_trend_accuracy.py` and `scripts/compare_mtes_strategies.py`.

**Metrics helper pattern** (lines 517-575, 578-601):
```python
def evaluate_direction_accuracy(signal: pd.Series, future_returns: pd.Series, lookback: int = 5) -> float:
    """评估方向准确性

    计算信号方向与未来 N 日收益的一致率
    """
    valid_idx = signal.index.intersection(future_returns.index)
    if len(valid_idx) == 0:
        return 50.0
    ...
    correct = (signal * future_returns) > 0
    accuracy = correct.sum() / len(correct) * 100

    return accuracy
```

**Data loading pattern** (lines 621-640):
```python
def load_data(symbol: str, market: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    """加载数据"""
    data_dir = PROJECT_ROOT / "data" / MARKET_DIR.get(market, market) / symbol
    data_path = data_dir / f"{timeframe}.parquet"

    if not data_path.exists():
        print(f"  ⚠️ 数据文件不存在: {data_path}")
        return None

    df = pd.read_parquet(data_path)
    col_map = {
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close',
        'Volume': 'volume', 'Adj Close': 'adj_close'
    }
    df.columns = [col_map.get(c, c.lower()) for c in df.columns]
    df.columns = [c.lower() for c in df.columns]

    return df
```

**Single-symbol evaluation loop** (lines 643-717):
```python
def backtest_symbol(symbol: str, name: str, market: str, timeframe: str = "1d") -> SymbolResult:
    """回测单个品种"""
    print(f"\n📊 回测 {symbol} ({name}) - {timeframe}")

    df = load_data(symbol, market, timeframe)
    if df is None or len(df) < 100:
        print(f"  ❌ 数据不足")
        return None
    ...
    for indicator in indicators:
        try:
            df_ind = indicator.calculate(df.copy())
            signal = indicator.get_signal(df_ind)
            direction_acc = evaluate_direction_accuracy(signal, df_ind['future_returns'])
            lead_score = evaluate_signal_lead(signal, df_ind['returns'])
            noise_score = evaluate_noise_filter(signal, df_ind['close'])
            overall = (direction_acc * 0.4 + lead_score * 0.3 + noise_score * 0.3)
            ...
        except Exception as e:
            print(f"  ❌ {indicator.name}: {e}")
```

**Report writer pattern** (lines 720-821): timestamped CSV and Markdown under `reports/`; use this for exploratory artifacts, not stable docs.

### `scripts/analyze_trend_accuracy.py` (script, transform + diagnostic reporting)

**Reusable:** clearer trend-indicator interface and accuracy/lag analysis.

**Imports + project path + evaluator dependency** (lines 12-25):
```python
import argparse
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from src.analysis.major_trend_evaluator import MajorTrendEvaluator, TrendState
```

**Indicator interface** (lines 32-42):
```python
class TrendIndicator:
    """趋势指标基类"""
    name: str

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """返回: 1=上涨, -1=下跌, 0=震荡"""
        raise NotImplementedError

    def strength(self, df: pd.DataFrame) -> pd.Series:
        """返回趋势强度 0-100"""
        raise NotImplementedError
```

**Best existing script-level standard SuperTrend implementation** (lines 110-158):
```python
class SuperTrendIndicator(TrendIndicator):
    """SuperTrend 趋势指标"""
    name = "SuperTrend"

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)
        ...
        for i in range(self.period + 1, n):
            if basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]:
                final_ub[i] = basic_ub[i]
            else:
                final_ub[i] = final_ub[i-1]

            if basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]:
                final_lb[i] = basic_lb[i]
            else:
                final_lb[i] = final_lb[i-1]

            if direction[i-1] == 1:
                direction[i] = -1 if close[i] < final_ub[i] else 1
            else:
                direction[i] = 1 if close[i] > final_lb[i] else -1

        return pd.Series(direction, index=df.index)
```

**Ground truth trend pattern** (lines 289-310):
```python
def get_actual_trend(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """计算实际趋势：使用价格变化的移动平均"""
    close = df["close"]
    returns = close.pct_change(lookback)
    returns_smooth = returns.rolling(5).mean()

    signal = np.zeros(len(df))
    signal[returns_smooth > 0.01] = 1
    signal[returns_smooth < -0.01] = -1

    return pd.Series(signal, index=df.index)
```

### `scripts/compare_mtes_strategies.py` (script, strategy comparison + simple backtest)

**Best analog for Phase 03 comparison script.** It defines local baseline strategies, MTES wrapper, simple backtest, metrics, loader, strategy builder, CLI.

**Backtest/strategy imports** (lines 34-39):
```python
from backtest.models import TradeRecord
from backtest.metrics import win_rate_and_stats, calc_bars_per_year
from backtest.strategies import BaseStrategy, StrategySignal, StrategyType
from backtest.strategies.major_trend import MajorTrendEvaluationStrategy
from src.analysis.major_trend_evaluator import MajorTrendEvaluator, calculate_adx
```

**Script-local strategy shape differs from canonical package contract** (lines 45-78):
```python
class EMAGoldenCrossStrategy(BaseStrategy):
    """EMA(50/200) 黄金交叉 — 多头: fast_ema > slow_ema."""

    def __init__(self, fast: int = 50, slow: int = 200):
        super().__init__(
            name="ema_golden_cross",
            strategy_type=StrategyType.TREND,
            parameters={"fast": fast, "slow": slow},
        )
        self.fast = fast
        self.slow = slow

    def _calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow, adjust=False).mean()
        return df

    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate(df)
        df["signal"] = 0
        ...
        return df
```

**Important:** script-local classes override `_generate_signals(self, df) -> DataFrame`; canonical package strategies must implement `_calculate(self, df) -> Dict[str, pd.Series]` and `_generate_signals(self, df, indicators) -> pd.Series`.

**Script SuperTrendStrategy implementation** (lines 155-223): use as comparison analog only after standardizing algorithm.

**Strategy builder extension point** (lines 632-642):
```python
def build_strategies(asset_class: str, mtes_warmup: int = 252) -> list[tuple[str, BaseStrategy]]:
    """构建所有对比策略."""
    return [
        ("A1. MTES(BULL_CONFIRMED)", MTESBacktestWrapper(asset_class=asset_class, min_state="BULL_CONFIRMED", warmup=mtes_warmup)),
        ("A2. MTES(BULL_EARLY)", MTESBacktestWrapper(asset_class=asset_class, min_state="BULL_EARLY", warmup=mtes_warmup)),
        ("B. SuperTrend(10,3)", SuperTrendStrategy(period=10, multiplier=3.0)),
        ("C. EMA(50/200)", EMAGoldenCrossStrategy(fast=50, slow=200)),
        ("D. ADX(14)>25", ADXTrendStrategy(period=14, threshold=25.0)),
        ("E. MACD(12/26/9)", MACDZeroCrossStrategy(fast=12, slow=26, signal=9)),
        ("F. Donchian(55)", DonchianBreakoutStrategy(period=55)),
    ]
```

**CLI pattern** (lines 739-797): `argparse`, default symbols, date window, `--mtes-warmup`, `--debug`, loop symbols, `load_data`, `build_strategies`, `run_backtest`, print table.

### `scripts/diagnose_mtes_vs_supertrend.py` (script, diagnostic)

**Use for:** Phase 03 diagnostic metrics around direction accuracy, false-signal rate, average return per signal.

**Function-style SuperTrend** (lines 36-91):
```python
def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """计算 SuperTrend 信号"""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)
    ...
    for i in range(period + 1, n):
        if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i - 1]
        ...
    return pd.Series(direction, index=df.index)
```

**Diagnostic result + helper** (lines 138-158):
```python
@dataclass
class DiagnosticMetrics:
    """诊断指标"""
    indicator: str
    symbol: str
    total_signals: int
    correct_direction: int
    direction_accuracy: float
    avg_lead_bars: float
    avg_holding_bars: float
    false_signal_rate: float
    avg_return_per_signal: float


def diagnose_indicator(
    df: pd.DataFrame,
    direction: pd.Series,
    indicator: str,
    symbol: str,
    holding_window: int = 20
) -> DiagnosticMetrics:
```

### `scripts/test_mtes_trend_indicator.py` (script, MTES trend validation)

**Use for:** directional consistency, lead/lag, noise filtering, intensity correlation report shape.

**Signal container dataclass** (lines 150-162):
```python
@dataclass
class IndicatorSignals:
    dates: np.ndarray
    close: np.ndarray
    mtes_dir: np.ndarray
    mtes_score: np.ndarray
    mtes_state: np.ndarray
    ema_dir: np.ndarray
    adx_dir: np.ndarray
    adx_val: np.ndarray
    macd_dir: np.ndarray
    atr_pct: np.ndarray
```

**Analysis functions** (lines 211-327): copy function-per-metric organization for Phase 03: `direction_consistency`, `signal_lead_lag`, `noise_filter_analysis`, `intensity_correlation`.

## Existing Backtest Strategy Interface, Registry, and Validation Helper

### Canonical strategy contract: `agent/backtest/strategies/__init__.py`

**BaseStrategy contract** (lines 61-112):
```python
class BaseStrategy(ABC):
    """Abstract base class for all strategies."""
    ...
    @abstractmethod
    def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        pass

    @abstractmethod
    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        pass
```

**Validation and generate pattern** (lines 114-178):
```python
    def validate(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        required_cols = ["open", "high", "low", "close"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            return False, f"Missing columns: {missing}"

        if len(df) < 20:
            return False, "Insufficient data (need at least 20 bars)"

        return True, None

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        valid, error = self.validate(df)
        if not valid:
            raise ValueError(f"Invalid data: {error}")

        indicators = self._calculate(df)
        self._indicators = indicators
        signals = self._generate_signals(df, indicators)

        result = df.copy()
        result["signal"] = signals
        result["signal_name"] = self.name

        for name, series in indicators.items():
            result[name] = series

        return result
```

### Strategy registry

**Registry API** (`agent/backtest/strategies/__init__.py` lines 193-239):
```python
class StrategyRegistry:
    _strategies: Dict[str, BaseStrategy] = {}

    @classmethod
    def register(cls, strategy: BaseStrategy) -> None:
        cls._strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")

    @classmethod
    def get(cls, name: str) -> Optional[BaseStrategy]:
        return cls._strategies.get(name)
```

**Auto-registration pattern** (`agent/backtest/strategies/registry.py` lines 29-54):
```python
def _register_strategies():
    """Register all strategy instances."""
    strategies = [
        TrendEmaAdxStrategy(),
        TrendMacdStrategy(),
        TrendDualEmaStrategy(),
        MajorTrendEvaluationStrategy(),
        ...
    ]

    for strategy in strategies:
        StrategyRegistry.register(strategy)

_register_strategies()
```

**Phase 03 implication:** if adding `SuperTrendEnhancedStrategy`, add import/export in `__init__.py`, import + instance in `registry.py`, and registry contract tests.

### Existing MTES wrapper analog: `agent/backtest/strategies/major_trend.py`

**Constructor pattern** (lines 29-63):
```python
    def __init__(self, parameters: Dict[str, Any] | None = None):
        params = parameters.copy() if parameters else {}
        asset_class = str(params.get("asset_class", "stock"))
        params.setdefault("asset_class", asset_class)
        params.setdefault("market", "all")
        params.setdefault("base_timeframe", "1d")
        params.setdefault("higher_timeframe_name", "1w")

        super().__init__(
            name="major_trend_evaluation",
            strategy_type=StrategyType.TREND,
            parameters=params,
        )
        self.asset_class = asset_class
        self.base_timeframe = str(params["base_timeframe"])
        self.higher_timeframe_name = str(params["higher_timeframe_name"])
        self.evaluator = MajorTrendEvaluator()
        self.tags = ["trend", "mtes", "evaluation_only", "multi_timeframe"]
        self.timeframes = ["1d", "4h", "1h"]
        self.supported_markets = ["stock", "etf", "futures", "crypto", "fx", ...]
```

**Signal mapping pattern** (lines 80-91):
```python
    def _generate_signals(
        self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        state = indicators["mtes_state"]
        mapping = {
            TrendState.BULL_STRONG.value: 1,
            TrendState.BULL_CONFIRMED.value: 1,
            TrendState.BEAR_STRONG.value: -1,
            TrendState.BEAR_CONFIRMED.value: -1,
        }
        return state.map(mapping).fillna(0).astype(int)
```

### Existing trend strategy analog: `agent/backtest/strategies/trend.py`

**Parameters dataclass pattern** (lines 44-55):
```python
@dataclass
class TrendParameters:
    """Parameters for trend strategies."""
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    adx_period: int = 14
    adx_threshold: float = 25.0
    ema_fast: int = 20
    ema_slow: int = 50
```

**Strategy init + metadata pattern** (lines 69-96):
```python
    def __init__(self, parameters: Optional[TrendParameters | Dict] = None):
        if parameters is None:
            params = TrendParameters()
        elif isinstance(parameters, dict):
            params = TrendParameters(**parameters)
        else:
            params = parameters

        super().__init__(
            name="trend_ema_adx",
            strategy_type=StrategyType.TREND,
            parameters={...},
        )
        self.params = params
        self.tags = ["trend", "ema", "adx", "multi_timeframe"]
        self.timeframes = ["1d", "4h", "1h"]
        self.supported_markets = ["cn_futures", "us_futures", "a_stock", "us_stock", "crypto"]
```

**Canonical `_calculate` / `_generate_signals` pattern** (lines 97-122, 184-203): return indicator dict and signal Series.

### Validation helper: `agent/backtest/validation.py`

**Statistical helpers to reuse instead of inventing Phase 03 equivalents.**

**Dispatcher** (lines 238-290):
```python
def run_validation(
    config: Dict[str, Any],
    equity_curve: pd.Series,
    trades: List[TradeRecord],
    initial_capital: float,
    bars_per_year: int = 252,
) -> Dict[str, Any]:
    """Run configured validation checks.

    Reads from config["validation"]:
      - monte_carlo: {n_simulations, seed}
      - bootstrap: {n_bootstrap, confidence, seed}
      - walk_forward: {n_windows}
    """
    v_cfg = config.get("validation", {})
    results: Dict[str, Any] = {}
    ...
    return results
```

**Base engine integration** (`agent/backtest/engines/base.py` lines 406-415): validation is triggered by `config["validation"]` and writes `artifacts/validation.json`.

**Signal alignment no-lookahead pattern** (`agent/backtest/engines/base.py` lines 70-129): `_align` shifts each symbol's own-calendar signal by one bar before ffill to unified dates.

## Existing Test Patterns

### Phase 01 MTES strategy tests: `agent/tests/test_mtes_strategy.py`

**Deterministic OHLCV fixture** (lines 35-48):
```python
def make_ohlcv(length: int = 64, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    """Create deterministic OHLCV data for strategy tests."""
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    close = pd.Series([start + i * step for i in range(length)], index=index, dtype="float64")
    return pd.DataFrame(
        {"open": close - 0.2, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1000.0},
        index=index,
    )
```

**Registry contract test** (lines 104-112):
```python
def test_major_trend_evaluation_strategy_is_registered_under_stable_name() -> None:
    strategy = StrategyRegistry.get("major_trend_evaluation")

    assert isinstance(strategy, MajorTrendEvaluationStrategy)
    assert "major_trend_evaluation" in StrategyRegistry.list_strategies(StrategyType.TREND)
    assert strategy.get_metadata().name == "major_trend_evaluation"
    assert strategy.get_metadata().type is StrategyType.TREND
```

**Output columns + forbidden execution columns** (lines 143-162): use for SuperTrend to ensure indicator fields are emitted and no sizing/execution fields appear.

### Validation-plan document contract tests: `agent/tests/test_mtes_validation_plan.py`

**Path and required-set pattern** (lines 7-43):
```python
PLAN_PATH = Path(__file__).resolve().parents[2] / "docs" / "MTES_BACKTEST_VALIDATION_PLAN.md"

REQUIRED_BASELINES = {...}
REQUIRED_METRICS = {...}
REQUIRED_UNIVERSES = {...}
REQUIRED_HELPERS = {
    "run_validation",
    "monte_carlo_test",
    "bootstrap_sharpe_ci",
    "walk_forward_analysis",
}
```

**Contract assertions** (lines 46-70): assert plan exists, names objective, baselines, metrics, universes, transaction costs, parameter sensitivity, signal delay, robustness, no-lookahead, and validation helpers.

### Generic strategy tests: `agent/tests/backtest/strategies/test_strategies.py`

**Sample OHLCV factory** (lines 18-49): use for randomized but deterministic realistic OHLCV.

**Strategy validation tests** (lines 265-296): copy insufficient data and missing required columns tests.

**Signal range test** (lines 311-325): ensure signals are only `-1, 0, 1`.

### Validation helper tests: `agent/tests/test_validation.py`

**Synthetic trades/equity fixtures** (lines 29-61): use to test validation integration without external data.

**Dispatcher test** (lines 212-239): use for any Phase 03 validation helper wiring.

## Pattern Assignments

### `agent/src/analysis/supertrend.py` (utility, transform)

**Analog:** `agent/src/analysis/major_trend_evaluator.py` and `scripts/analyze_trend_accuracy.py`

**Recommended purpose:** one canonical SuperTrend implementation returning aligned `pd.Series`/indicator payload; remove duplication across scripts.

**Imports pattern:** copy `major_trend_evaluator.py` lines 7-15:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
```

**Validation/normalization pattern:** copy `normalize_ohlcv` from `major_trend_evaluator.py` lines 514-533.

**Core algorithm pattern:** start from `scripts/analyze_trend_accuracy.py` lines 118-158, not the simplified lines 170-229 in `backtest_trend_indicators.py`. Compare with `scripts/diagnose_mtes_vs_supertrend.py` lines 36-91 and `scripts/compare_mtes_strategies.py` lines 167-223 before locking expected behavior.

**Testing analog:** `agent/tests/test_major_trend_evaluator.py` lines 29-51 for deterministic OHLCV and lines 97-110 for classifier/score contract.

---

### `agent/backtest/strategies/supertrend.py` (strategy, transform)

**Analog:** `agent/backtest/strategies/trend.py`

**Imports pattern:** copy `trend.py` lines 33-41:
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import BaseStrategy, StrategyType, StrategySignal
```

**Constructor pattern:** copy `TrendEmaAdxStrategy.__init__` from `trend.py` lines 69-96. Use `name="trend_supertrend_enhanced"`, `strategy_type=StrategyType.TREND`, parameters like `period`, `multiplier`, optional `confirmation_mode`, `use_close_cross`, `emit_continuous_signal`.

**Calculation pattern:** must return `Dict[str, pd.Series]`, as in `trend.py` lines 97-122. Recommended indicator keys: `atr`, `supertrend`, `st_direction`, `upper_band`, `lower_band`, maybe `trend_strength`.

**Signal pattern:** return `pd.Series` with `-1/0/1`, as in `trend.py` lines 184-203. Avoid script-local `_generate_signals(self, df) -> DataFrame` pattern from `scripts/compare_mtes_strategies.py`.

**Metadata pattern:** set `tags = ["trend", "supertrend", "atr", "enhanced"]`, `timeframes = ["1d", "4h", "1h"]`, `supported_markets = ["cn_futures", "us_futures", "a_stock", "us_stock", "crypto", "etf"]`.

---

### `agent/backtest/strategies/__init__.py` (package export / registry trigger)

**Analog:** same file.

**Add import near trend strategies:** follow lines 371-384 and line 385.

**Add `__all__` entry:** follow lines 404-408.

**Planner note:** avoid circular import. If `supertrend.py` imports from `. import BaseStrategy`, add `from .supertrend import SuperTrendEnhancedStrategy` before `_strategy_registry` import just like `major_trend.py`.

---

### `agent/backtest/strategies/registry.py` (auto registration)

**Analog:** same file.

**Import pattern:** follow lines 5-10.  
**Registration pattern:** follow lines 29-54.  
**Planner note:** add `SuperTrendEnhancedStrategy()` in trend section and include in `__all__`.

---

### `agent/tests/test_supertrend_indicator.py` (test, transform validation)

**Analog:** `agent/tests/test_major_trend_evaluator.py`

**Fixture pattern:** copy lines 29-51. Add fixtures for monotonic uptrend, monotonic downtrend, choppy alternating/noise, and insufficient bars.

**Contract test pattern:** copy lines 97-110 but assert SuperTrend-specific columns/series.

**Missing/invalid input pattern:** copy lines 113-133 for insufficient data / missing optional volume; for SuperTrend test missing `high/low/close` raises clear `ValueError`.

---

### `agent/tests/test_supertrend_strategy.py` (test, strategy contract)

**Analog:** `agent/tests/test_mtes_strategy.py` + `agent/tests/backtest/strategies/test_strategies.py`

**Registry test:** adapt `test_major_trend_evaluation_strategy_is_registered_under_stable_name` lines 104-112.

**Output columns + no execution columns:** adapt `EXPECTED_MTES_COLUMNS` / `FORBIDDEN_EXECUTION_COLUMNS` from `test_mtes_strategy.py` lines 13-32 and `generate` assertions lines 143-162. Expected SuperTrend columns should include at least `atr`, `supertrend`, `st_direction`, `signal`, `signal_name`.

**Signal range:** copy `test_signal_range` from `agent/tests/backtest/strategies/test_strategies.py` lines 311-325.

**Validation:** copy insufficient/missing columns tests from lines 265-296.

---

### `agent/tests/test_supertrend_validation_plan.py` (test, document contract)

**Analog:** `agent/tests/test_mtes_validation_plan.py`

**Copy pattern exactly:** lines 7-43 for `PLAN_PATH` and required sets; lines 46-70 for assertions.

**Phase 03 required content should include:** `objective`, `standard supertrend`, `enhanced supertrend`, `ATR`, `band update`, `signal-delay`, `parameter sensitivity`, `transaction cost`, `robustness`, `run_validation`, `monte_carlo_test`, `bootstrap_sharpe_ci`, `walk_forward_analysis`, and baseline comparisons to MTES/EMA/ADX/MACD/Donchian/Range Filter.

---

### `docs/SUPERTREND_ENHANCEMENT_VALIDATION_PLAN.md` (docs, batch/reporting)

**Analog:** `docs/MTES_BACKTEST_VALIDATION_PLAN.md`

**Structure to copy:** Objective lines 5-8; Evaluation wrapper lines 9-12; Asset universes lines 13-21; Time splits lines 23-28; Baselines lines 30-40; Signal construction lines 42-49; Cost assumptions lines 50-59; Validation helper reuse lines 61-70; Metrics lines 72-85; Parameter perturbation lines 87-95; Signal delay lines 96-101; Required artifacts lines 128-136.

**Validation helper excerpt** (lines 61-70):
```markdown
## Validation Helper Reuse

Reuse the existing backtest validation helpers rather than introducing a parallel statistical subsystem:

- `run_validation`
- `monte_carlo_test`
- `bootstrap_sharpe_ci`
- `walk_forward_analysis`
```

---

### `scripts/compare_supertrend_enhancement.py` (script, batch + report)

**Analog:** `scripts/compare_mtes_strategies.py`

**Imports:** copy lines 19-39, but import canonical SuperTrend strategy from package if created.

**Local baselines:** reuse script baselines from lines 45-255 if no package equivalents exist. Prefer canonical package `TrendEmaAdxStrategy`, `TrendMacdStrategy`, `TrendDualEmaStrategy` for persistent comparison when possible.

**BacktestResult/run_backtest:** copy lines 334-543 if the script needs self-contained backtests. If using `agent/backtest/engines/base.py`, remember engine `_align` already shifts signals by one bar (lines 70-129).

**build_strategies:** adapt lines 632-642 to compare standard SuperTrend, enhanced SuperTrend, MTES wrapper, EMA/ADX/MACD/Donchian/Range Filter baselines.

**CLI:** copy lines 739-797, add flags for `--periods`, `--multipliers`, `--variant`, `--output` if writing artifacts.

---

### `scripts/backtest_trend_indicators.py` (script modification)

**Analog:** same file.

**Change pattern:** add standardized/enhanced SuperTrend indicator to `get_indicators()` lines 608-618.

**Planner note:** First refactor script to import canonical `agent/src/analysis/supertrend.py` or `agent/backtest/strategies/supertrend.py` instead of adding a fourth duplicate implementation.

---

### `scripts/diagnose_supertrend_variants.py` or modify `scripts/diagnose_mtes_vs_supertrend.py` (script, diagnostic)

**Analog:** `scripts/diagnose_mtes_vs_supertrend.py`

**Reuse:** `DiagnosticMetrics` lines 138-150, `diagnose_indicator` lines 152-233, `run_diagnostic` lines 296-313, table printing lines 316-324, market/CLI dispatch lines 284-350.

**Planner note:** keep diagnostics read-only against local parquet and print/report only; do not write into source-controlled docs from diagnostic runs.

## Shared Patterns

### OHLCV normalization and column conventions

**Source:** `agent/src/analysis/major_trend_evaluator.py` lines 514-533 and script loaders in `scripts/backtest_trend_indicators.py` lines 621-640.

**Apply to:** `agent/src/analysis/supertrend.py`, `agent/backtest/strategies/supertrend.py`, all comparison/diagnostic scripts.

**Pattern:** lower-case `open/high/low/close/volume`, DatetimeIndex, sort index, numeric coercion, clear errors for missing required columns.

### Signals

**Source:** `agent/backtest/strategies/__init__.py` lines 51-58 and lines 149-178.

**Apply to:** all package strategies.

**Pattern:** package strategy `generate(df)` returns original OHLCV plus `signal`, `signal_name`, indicator columns. `signal` values must be `-1, 0, 1`.

### Registration

**Source:** `agent/backtest/strategies/registry.py` lines 29-54.

**Apply to:** new strategy classes.

**Pattern:** import strategy, instantiate in `_register_strategies()`, export in `__all__`, rely on `from . import registry as _strategy_registry` in package init.

### No-lookahead / next-bar execution

**Source:** `agent/backtest/engines/base.py` lines 70-129.

**Apply to:** backtest engine integration and validation plan.

**Pattern:** signals are shifted by one bar in `_align`; scripts that implement their own `run_backtest` must either shift explicitly or state that same-bar execution is exploratory only.

### Statistical validation

**Source:** `agent/backtest/validation.py` lines 25-30, 96-102, 153-158, 238-290.

**Apply to:** Phase 03 validation reports and engine-run artifacts.

**Pattern:** use `run_validation` dispatcher with config keys `monte_carlo`, `bootstrap`, `walk_forward`.

### Testing fixtures

**Source:** `agent/tests/test_mtes_strategy.py` lines 35-48 and `agent/tests/backtest/strategies/test_strategies.py` lines 18-49.

**Apply to:** all Phase 03 unit tests.

**Pattern:** deterministic OHLCV factories, no external data dependencies in unit tests.

## No Analog Found

None. Every inferred Phase 03 file has a close analog. The main gap is not lack of analogs but too many duplicate script-level SuperTrend implementations.

## Risks and Planner Warnings

| Risk | Evidence | Planner Mitigation |
|---|---|---|
| Untracked files | `git status --short` shows untracked `scripts/backtest_trend_indicators.py`, `scripts/analyze_trend_accuracy.py`, `scripts/compare_mtes_strategies.py`, `scripts/diagnose_mtes_vs_supertrend.py`, `scripts/test_mtes_trend_indicator.py`, `reports/`, and `.planning/phases/02-trend-indicator-backtest/`. | Treat scripts/reports as exploratory unless promoted with tests. Do not base critical implementation solely on untracked scripts without adding package tests. |
| Script-style implementations diverge from package strategy contract | `scripts/compare_mtes_strategies.py` local strategies use `_generate_signals(self, df) -> DataFrame`, while package `BaseStrategy` requires `_generate_signals(self, df, indicators) -> pd.Series`. | For package code, copy `agent/backtest/strategies/trend.py`, not script-local class signatures. |
| Multiple SuperTrend algorithms differ | Simplified SuperTrend in `backtest_trend_indicators.py` lines 170-229; fuller implementations in `analyze_trend_accuracy.py` lines 110-158, `diagnose_mtes_vs_supertrend.py` lines 36-91, `compare_mtes_strategies.py` lines 155-223. | First task should standardize one canonical algorithm and pin it with deterministic tests. |
| Report directory noise | `reports/` contains 22 generated trend comparison CSV/Markdown files. | Keep generated reports out of planning/source changes unless explicitly curated. Prefer `reports/` for artifacts, docs for stable plans only. |
| Root `tests/` does not exist | `/Users/iagent/projects/vibe-trading/tests` is missing; tests live under `/Users/iagent/projects/vibe-trading/agent/tests`. | Place Phase 03 tests under `agent/tests/`, not root `tests/`. Use `pytest agent/tests/...`. |
| MTES warmup and SuperTrend warmup differ | MTES scripts use warmup 200/252; SuperTrend uses period 10 with rolling ATR. | Compare only after explicit warmup trimming or common valid index alignment. |
| Existing simple scripts may use same-bar execution | `scripts/compare_mtes_strategies.py` simple `run_backtest` reads signals directly; engine `_align` shifts signals. | Use engine or add explicit next-bar shift to comparison script before making validation claims. |
| Existing MTES wrapper broadcasts one full-frame result | `MajorTrendEvaluationStrategy._calculate` evaluates full frame once and broadcasts constants. | Historical bar-by-bar MTES comparisons must use script `MTESBacktestWrapper` pattern or a new rolling wrapper; do not confuse evaluation-only wrapper with historical rolling signals. |

## Recommended Planner Task Slicing (Historical Reference — Superseded by 03-01 to 03-05 Plans)

> 注意：本节保留为初始模式映射参考。当前 planner 已根据 plan-checker 反馈拆分为 `03-01` 至 `03-05`，实际执行范围以这些 PLAN 文件为准。

### Slice 1: Standardize SuperTrend algorithm first

**Goal:** one canonical implementation with deterministic tests.

**Files:**
- Add `agent/src/analysis/supertrend.py`
- Add `agent/tests/test_supertrend_indicator.py`

**Analog:** `agent/src/analysis/major_trend_evaluator.py`, `agent/tests/test_major_trend_evaluator.py`, and SuperTrend code from `scripts/analyze_trend_accuracy.py` lines 110-158.

**Acceptance:** deterministic up/down/choppy fixtures pass; missing columns fail clearly; output aligns to input index; no duplicate algorithm added in scripts.

### Slice 2: Add canonical SuperTrend strategy + registry

**Goal:** package strategy discoverable via `StrategyRegistry` and compatible with `BaseStrategy.generate`.

**Files:**
- Add `agent/backtest/strategies/supertrend.py`
- Modify `agent/backtest/strategies/__init__.py`
- Modify `agent/backtest/strategies/registry.py`
- Add `agent/tests/test_supertrend_strategy.py`

**Analog:** `agent/backtest/strategies/trend.py`, `agent/backtest/strategies/major_trend.py`, `agent/tests/test_mtes_strategy.py`.

**Acceptance:** registry returns strategy by stable name; generate emits expected columns; signals are `-1/0/1`; no position sizing/execution columns.

### Slice 3: Extend strategy evaluation and validation plan

**Goal:** formal Phase 03 validation criteria and helper reuse.

**Files:**
- Add `docs/SUPERTREND_ENHANCEMENT_VALIDATION_PLAN.md`
- Add `agent/tests/test_supertrend_validation_plan.py`

**Analog:** `docs/MTES_BACKTEST_VALIDATION_PLAN.md`, `agent/tests/test_mtes_validation_plan.py`.

**Acceptance:** doc contract requires standard/enhanced SuperTrend, baseline comparisons, transaction cost, parameter sensitivity, signal delay, robustness, and validation helper reuse.

### Slice 4: Add comparison/diagnostic script after package strategy is tested

**Goal:** compare standard vs enhanced SuperTrend vs MTES/baselines without duplicating algorithm.

**Files:**
- Add `scripts/compare_supertrend_enhancement.py` or modify `scripts/compare_mtes_strategies.py`
- Optionally add `scripts/diagnose_supertrend_variants.py` or modify `scripts/diagnose_mtes_vs_supertrend.py`

**Analog:** `scripts/compare_mtes_strategies.py`, `scripts/diagnose_mtes_vs_supertrend.py`, `scripts/test_mtes_trend_indicator.py`.

**Acceptance:** script imports canonical implementation, uses explicit next-bar semantics or states exploratory mode, supports local parquet data, writes outputs under `reports/`, and prints comparison tables.

### Slice 5: Integrate into existing trend indicator backtest script

**Goal:** reuse Phase 03 canonical implementation in existing exploratory trend indicator backtest.

**Files:**
- Modify `scripts/backtest_trend_indicators.py`

**Analog:** same file lines 608-618 (`get_indicators`) and lines 720-821 (`generate_report`).

**Acceptance:** no new duplicate SuperTrend class; existing reports still generated; enhanced SuperTrend appears in comparison table.

## Metadata

**Analog search scope:** `/Users/iagent/projects/vibe-trading/scripts`, `/Users/iagent/projects/vibe-trading/agent/backtest`, `/Users/iagent/projects/vibe-trading/agent/src/analysis`, `/Users/iagent/projects/vibe-trading/agent/tests`, `/Users/iagent/projects/vibe-trading/docs`  
**Files scanned:** 120 keyword-relevant files listed by local scan  
**Strong analogs read:** 14  
**Pattern extraction date:** 2026-05-30

## Completion Marker

Pattern mapping complete for Phase 03 `SuperTrend Enhancement Strategy`.
