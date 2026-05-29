# Phase 01: Major Trend Evaluation System - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 11 planned new/modified files
**Analogs found:** 10 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agent/src/analysis/major_trend_evaluator.py` | service / model / utility | transform | `agent/src/analysis/major_trend_evaluator.py` draft + `agent/src/analysis/watchlist_analyzer.py` indicator helpers | exact draft |
| `agent/src/analysis/__init__.py` | config / export | request-response / import registry | `agent/src/analysis/__init__.py` | exact |
| `agent/backtest/strategies/major_trend.py` | strategy / service | batch transform | `agent/backtest/strategies/trend.py` | exact role-match |
| `agent/backtest/strategies/registry.py` | config / registry | import registration | `agent/backtest/strategies/registry.py` | exact |
| `agent/backtest/strategies/__init__.py` | config / registry / base | import registration | `agent/backtest/strategies/__init__.py` | exact |
| `agent/src/analysis/watchlist_analyzer.py` | adapter / service | batch request-response + file-I/O | `agent/src/analysis/watchlist_analyzer.py` | exact |
| `agent/src/analysis/report_generator.py` | adapter / utility | transform + file-I/O | `agent/src/analysis/report_generator.py` | exact |
| `agent/src/tools/watchlist_tool.py` | tool / controller | request-response | `agent/src/tools/watchlist_tool.py` | exact |
| `agent/tests/test_major_trend_evaluator.py` | test | batch transform / request-response | `agent/tests/test_major_trend_evaluator.py` | exact draft |
| `agent/tests/test_mtes_strategy.py` or `agent/tests/backtest/...` | test | batch transform | `agent/tests/test_strategy_watchlist_tools.py` + `agent/tests/test_major_trend_evaluator.py` | role-match |
| `docs/MTES_BACKTEST_VALIDATION_PLAN.md` | documentation / validation artifact | batch validation plan | `docs/MTES_BACKTEST_VALIDATION_PLAN.md` draft + `agent/backtest/strategies/comparison.py` report shape | partial |

## Pattern Assignments

### `agent/src/analysis/major_trend_evaluator.py` (service/model/utility, transform)

**Analog:** `agent/src/analysis/major_trend_evaluator.py` existing draft. Treat as a seed to refactor, not final, because research says it conflicts with locked Base+Override weights and strict long-window insufficiency.

**Imports and constants pattern** (lines 0-18):
```python
"""Major Trend Evaluation System scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

DIMENSIONS = (
    "direction",
    "strength",
    "structure",
    "momentum",
    "volatility_regime",
    "mtf",
)
```

**Result schema and `to_dict()` pattern** (lines 110-141):
```python
@dataclass(frozen=True)
class MajorTrendResult:
    asset_class: str
    trend_score: float
    trend_state: str
    direction: str
    confidence: float
    regime: str
    sub_scores: dict[str, float]
    raw_scores: dict[str, float]
    weights: dict[str, float]
    top_drivers: list[dict[str, Any]]
    regime_flags: list[str]
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "trend_score": self.trend_score,
            "trend_state": self.trend_state,
            "direction": self.direction,
            "confidence": self.confidence,
            "regime": self.regime,
            "sub_scores": self.sub_scores,
            "raw_scores": self.raw_scores,
            "weights": self.weights,
            "top_drivers": self.top_drivers,
            "regime_flags": self.regime_flags,
            "explanation": self.explanation,
            "metadata": self.metadata,
        }
```

**Core evaluator orchestration pattern** (lines 151-219):
```python
def evaluate(
    self,
    df: pd.DataFrame,
    asset_class: str | None = None,
    higher_timeframe: pd.DataFrame | None = None,
    base_timeframe: str = "1d",
    higher_timeframe_name: str = "1w",
) -> MajorTrendResult:
    data = normalize_ohlcv(df)
    resolved_asset_class = resolve_asset_class(asset_class or self.config.asset_class)
    weights = get_weight_profile(resolved_asset_class)

    if len(data) < self.config.intermediate_window:
        return insufficient_data_result(resolved_asset_class, weights, len(data), self.config.intermediate_window)

    direction_score, direction, direction_meta = self.score_direction(data)
    strength_score, strength_meta = self.score_strength(data, direction)
    structure_score, structure_meta = self.score_structure(data, direction)
    momentum_score, momentum_meta = self.score_momentum(data, direction)
    regime_score, regime, regime_flags, regime_meta = self.score_volatility_regime(data)
    mtf_score, mtf_meta = self.score_mtf_alignment(...)

    raw_scores = {...}
    sub_scores = {
        dimension: round(raw_scores[dimension] * weights[dimension] / 100, 2)
        for dimension in DIMENSIONS
    }
    trend_score = round(sum(sub_scores.values()), 2)
    trend_state = classify_trend_state(trend_score, direction)
```

**Required deviation from analog:** Replace full per-asset weight maps at lines 20-61 with locked `BASE_WEIGHTS = {direction: 15, strength: 15, structure: 25, momentum: 15, volatility_regime: 15, mtf: 15}` plus asset-class override composition. Keep `validate_weight_profiles()` shape from lines 450-457 but validate the composed final profiles.

**Input validation / normalization pattern** (lines 416-434):
```python
def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        if "timestamp" in data.columns:
            data["timestamp"] = pd.to_datetime(data["timestamp"])
            data = data.set_index("timestamp")
        elif "datetime" in data.columns:
            data["datetime"] = pd.to_datetime(data["datetime"])
            data = data.set_index("datetime")
    required = ["open", "high", "low", "close"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"missing required OHLC columns: {', '.join(missing)}")
    if "volume" not in data.columns:
        data["volume"] = 0.0
    data = data.sort_index()
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["open", "high", "low", "close"])
```

**Classification pattern** (lines 460-475):
```python
def classify_trend_state(score: float, direction: str) -> str:
    if direction == "BULL":
        if score >= 80:
            return TrendState.BULL_STRONG.value
        if score >= 62:
            return TrendState.BULL_CONFIRMED.value
        if score >= 45:
            return TrendState.BULL_EARLY.value
    if direction == "BEAR":
        if score >= 80:
            return TrendState.BEAR_STRONG.value
        if score >= 62:
            return TrendState.BEAR_CONFIRMED.value
        if score >= 45:
            return TrendState.BEAR_EARLY.value
    return TrendState.NEUTRAL_CHOPPY.value
```

**MTF no-look-ahead pattern to preserve** (lines 383-413):
```python
from backtest.strategies.mtf import MTFAligner, MTFConfig

htf = normalize_ohlcv(higher_timeframe)
htf = htf.copy()
htf["major_direction"] = htf["close"].ewm(span=min(20, len(htf)), adjust=False).mean()
aligned = MTFAligner(MTFConfig(lag_bars=1)).align_htf_to_ltf(
    htf_data=htf[["major_direction"]],
    ltf_data=df[["close"]],
    htf_timeframe=higher_timeframe_name,
    ltf_timeframe=base_timeframe,
    htf_columns=["major_direction"],
)
aligned_data = aligned.data.dropna(subset=["htf_major_direction"])
```

**Error/no-score pattern** (lines 478-495):
```python
def insufficient_data_result(asset_class: str, weights: dict[str, float], bars: int, required: int) -> MajorTrendResult:
    sub_scores = {dimension: 0.0 for dimension in DIMENSIONS}
    raw_scores = {dimension: 0.0 for dimension in DIMENSIONS}
    return MajorTrendResult(
        asset_class=asset_class,
        trend_score=0.0,
        trend_state=TrendState.NEUTRAL_CHOPPY.value,
        direction="NEUTRAL",
        confidence=0.0,
        regime="insufficient",
        sub_scores=sub_scores,
        raw_scores=raw_scores,
        weights=weights,
        top_drivers=[],
        regime_flags=["insufficient_data"],
        explanation=f"Insufficient data: {bars} bars available, {required} required.",
        metadata={"bars": bars, "required_bars": required},
    )
```

---

### `agent/backtest/strategies/major_trend.py` (strategy/service, batch transform)

**Analog:** `agent/backtest/strategies/trend.py`.

**Imports and base class pattern** (lines 33-42):
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import BaseStrategy, StrategyType, StrategySignal
```

**Parameter dataclass pattern** (lines 44-55):
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

**Strategy initialization metadata pattern** (lines 69-96):
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
        parameters={
            "ema_fast": params.ema_fast,
            "ema_slow": params.ema_slow,
            "adx_period": params.adx_period,
            "adx_threshold": params.adx_threshold,
        },
    )
    self.params = params
    self.tags = ["trend", "ema", "adx", "multi_timeframe"]
    self.timeframes = ["1d", "4h", "1h"]
    self.supported_markets = ["cn_futures", "us_futures", "a_stock", "us_stock", "crypto"]
```

**Core `_calculate()` pattern** (lines 97-122):
```python
def _calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Calculate EMA and ADX indicators."""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema_fast = close.ewm(span=self.params.ema_fast, adjust=False).mean()
    ema_slow = close.ewm(span=self.params.ema_slow, adjust=False).mean()

    adx = self._calculate_adx(high, low, close, self.params.adx_period)
    ...
    return {
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
    }
```

**Signal generation pattern** (lines 184-203):
```python
def _generate_signals(
    self, df: pd.DataFrame, indicators: Dict[str, pd.Series]
) -> pd.Series:
    """Generate trend signals based on EMA and ADX."""
    ema_fast = indicators["ema_fast"]
    ema_slow = indicators["ema_slow"]
    adx = indicators["adx"]

    signals = pd.Series(0, index=df.index)

    strong_uptrend = (ema_fast > ema_slow) & (adx > self.params.adx_threshold)
    strong_downtrend = (ema_fast < ema_slow) & (adx > self.params.adx_threshold)

    signals[strong_uptrend] = 1
    signals[strong_downtrend] = -1

    return signals
```

**How to adapt:** `MajorTrendEvaluationStrategy._calculate()` should call `MajorTrendEvaluator` or compute MTES output series, add columns such as `mtes_score`, `mtes_state`, `mtes_direction`, and `_generate_signals()` should map `BULL_CONFIRMED` / `BULL_STRONG` to `1`, `BEAR_CONFIRMED` / `BEAR_STRONG` to `-1`, otherwise `0`. Keep evaluation-only boundary: no sizing/order execution.

---

### `agent/backtest/strategies/__init__.py` (base/config/registry, import registration)

**Analog:** `agent/backtest/strategies/__init__.py`.

**Strategy type and metadata pattern** (lines 28-48):
```python
class StrategyType(Enum):
    """Strategy classification by purpose."""

    TREND = "trend"
    PULLBACK = "pullback"
    ENTRY = "entry"


@dataclass
class StrategyMetadata:
    """Metadata for a strategy."""

    name: str
    type: StrategyType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    market: str = "all"
    tags: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=list)
    supported_markets: List[str] = field(default_factory=list)
```

**Base validation/generate pattern** (lines 114-178):
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

**Registry API pattern** (lines 193-239):
```python
class StrategyRegistry:
    """Registry for managing and accessing strategies."""

    _strategies: Dict[str, BaseStrategy] = {}

    @classmethod
    def register(cls, strategy: BaseStrategy) -> None:
        cls._strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")

    @classmethod
    def get(cls, name: str) -> Optional[BaseStrategy]:
        return cls._strategies.get(name)

    @classmethod
    def list_strategies(
        cls, strategy_type: Optional[StrategyType] = None
    ) -> List[str]:
        if strategy_type is None:
            return list(cls._strategies.keys())

        return [
            name
            for name, s in cls._strategies.items()
            if s.strategy_type == strategy_type
        ]
```

**Export pattern** (lines 368-370):
```python
# Import composer for convenience
from .composer import StrategyComposer, ComposerState, CompositeSignal
from .mtf import MTFAligner, MTFComposer, MTFConfig, Timeframe, AlignmentResult
```

**How to adapt:** Add `MajorTrendEvaluationStrategy` import/export without changing the `BaseStrategy.generate()` contract.

---

### `agent/backtest/strategies/registry.py` (registry/config, import registration)

**Analog:** `agent/backtest/strategies/registry.py`.

**Auto-import and registration pattern** (lines 5-22, 28-52):
```python
from .trend import (
    TrendEmaAdxStrategy,
    TrendMacdStrategy,
    TrendDualEmaStrategy,
)
...

# Auto-register all strategies
def _register_strategies():
    """Register all strategy instances."""
    strategies = [
        # Trend strategies
        TrendEmaAdxStrategy(),
        TrendMacdStrategy(),
        TrendDualEmaStrategy(),
        # Pullback strategies
        PullbackRsiStrategy(),
        ...
    ]

    for strategy in strategies:
        StrategyRegistry.register(strategy)

# Register on import
_register_strategies()
```

**`__all__` pattern** (lines 54-85):
```python
__all__ = [
    # Base classes
    "BaseStrategy",
    "StrategyType",
    "StrategyRegistry",
    "StrategySignal",
    "StrategyMetadata",
    ...
    # Trend strategies
    "TrendEmaAdxStrategy",
    "TrendMacdStrategy",
    "TrendDualEmaStrategy",
    ...
]
```

**How to adapt:** Import `MajorTrendEvaluationStrategy`, add an instance to the trend strategy block, and add it to `__all__`.

---

### `agent/src/analysis/watchlist_analyzer.py` (adapter/service, batch request-response + file-I/O)

**Analog:** `agent/src/analysis/watchlist_analyzer.py`.

**Result dataclass extension pattern** (lines 18-37):
```python
@dataclass
class AnalysisResult:
    """单个品种的分析结果"""

    symbol: str
    name: str
    market: str
    trend: str = "-"
    ...
    confidence: float = 0.0
    error: Optional[str] = None
    mtes: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Machine-readable merge pattern** (lines 39-55):
```python
def to_dict(self) -> Dict[str, Any]:
    result = {
        "symbol": self.symbol,
        "name": self.name,
        "market": self.market,
        "trend": self.trend,
        ...
        "error": self.error or "-",
    }
    if self.mtes:
        result.update(self.mtes)
    return result
```

**Default dependency loading pattern** (lines 91-110):
```python
if self.data_client is None:
    try:
        from backtest.loaders.client import DataClient

        self.data_client = DataClient()
        logger.info("DataClient initialized")
    except Exception as e:
        logger.warning(f"DataClient not available: {e}")

if self.strategy_registry is None:
    try:
        from backtest.strategies import StrategyRegistry, StrategyType

        self.strategy_registry = StrategyRegistry
        self._load_default_strategies()
    except Exception as e:
        logger.warning(f"StrategyRegistry not available: {e}")
```

**MTES adapter and failure fallback pattern** (lines 431-449):
```python
try:
    from src.analysis.major_trend_evaluator import MajorTrendEvaluator, resolve_asset_class

    asset_class = resolve_asset_class(market)
    mtes_payload = MajorTrendEvaluator().evaluate(df, asset_class=asset_class).to_dict()
except Exception as exc:
    logger.warning("MTES evaluation failed for %s: %s", symbol, exc)
    mtes_payload = {
        "asset_class": "unknown",
        "trend_score": 0.0,
        "trend_state": "NEUTRAL_CHOPPY",
        "direction": "NEUTRAL",
        "confidence": 0.0,
        "regime": "unavailable",
        "sub_scores": {},
        "top_drivers": [],
        "regime_flags": ["mtes_unavailable"],
        "explanation": str(exc),
    }
```

**Batch timeframe extraction pattern** (lines 570-599):
```python
reader = WatchlistReader(self.watchlist_path)
raw_items = reader.load_raw()

results = []
for item in raw_items:
    symbol = item["symbol"]
    market = item["market"]
    primary_tf, secondary_tf = reader.get_timeframes(symbol)

    if market_filter and market.upper() != market_filter.upper():
        continue

    if symbol.lower() in ("symbol", "code", "name"):
        continue

    atr = item.get("atr", 0.0) if item.get("atr", 0.0) > 0 else None
    result = self.analyze_single(
        symbol=symbol,
        market=market,
        primary_tf=primary_tf,
        secondary_tf=secondary_tf,
        atr_override=atr,
    )
```

**How to adapt:** Keep `WatchlistAnalyzer` as a thin adapter. It should pass watchlist-provided base/higher timeframe names and available higher-timeframe data to `MajorTrendEvaluator.evaluate()`; do not duplicate scoring internals here.

---

### `agent/src/analysis/report_generator.py` (adapter/utility, transform + file-I/O)

**Analog:** `agent/src/analysis/report_generator.py`.

**Config/dataclass pattern** (lines 17-26):
```python
@dataclass
class ReportConfig:
    """报告配置"""

    title: str = "Watchlist 分析报告"
    include_summary: bool = True
    include_details: bool = True
    include_charts: bool = False
    format_version: str = "1.0"
```

**Summary aggregation pattern** (lines 42-82):
```python
def generate_summary(self, results: List[AnalysisResult]) -> dict:
    total = len(results)
    errors = sum(1 for r in results if r.error)
    success = total - errors

    trends = {"UP": 0, "DOWN": 0, "SIDEWAYS": 0, "-": 0}
    for r in results:
        if r.error:
            continue
        trends[r.trend] = trends.get(r.trend, 0) + 1

    signals = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0, "-": 0}
    ...
    return {...}
```

**Table extension pattern for MTES fields** (lines 84-122):
```python
def generate_table(self, results: List[AnalysisResult]) -> str:
    if not results:
        return "| 代码 | 名称 | 趋势 | MTES | 状态 | 回调 | 信号 | 信号价 | 信号日 | 止损价 | 1N |\n|---|---|---|---|---|---|---|---|---|---|---|"

    header = "| 代码 | 名称 | 趋势 | MTES | 状态 | 回调 | 信号 | 信号价 | 信号日 | 止损价 | 1N |"
    separator = "|---|---|---|---|---|---|---|---|---|---|---|"
    ...
    mtes_score = r.mtes.get("trend_score", "-") if r.mtes else "-"
    trend_state = r.mtes.get("trend_state", "-") if r.mtes else "-"
    if isinstance(mtes_score, (int, float)):
        mtes_score = f"{mtes_score:.1f}"
```

**File output pattern** (lines 224-243):
```python
def save_report(
    self, results: List[AnalysisResult], output_path: str, watchlist_name: str = ""
) -> str:
    report = self.generate_markdown(results, watchlist_name)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info(f"报告已保存: {output_path}")
    return output_path
```

**How to adapt:** Human markdown may include display-only icons, but JSON/machine fields should remain plain strings/numbers.

---

### `agent/src/tools/watchlist_tool.py` (tool/controller, request-response)

**Analog:** `agent/src/tools/watchlist_tool.py`.

**Path safety pattern** (lines 16-31):
```python
def _resolve_watchlist_path(watchlist_path: str) -> Path:
    raw_path = Path(watchlist_path).expanduser()
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    elif raw_path.parts and raw_path.parts[0] == "watchlist":
        candidate = (_REPO_DIR / raw_path).resolve()
    else:
        candidate = (_WATCHLIST_DIR / raw_path).resolve()

    watchlist_root = _WATCHLIST_DIR.resolve()
    try:
        candidate.relative_to(watchlist_root)
    except ValueError as exc:
        raise ValueError(f"Watchlist path {watchlist_path!r} escapes the watchlist directory") from exc

    return candidate
```

**Tool class metadata pattern** (lines 34-50):
```python
class ListWatchlistTool(BaseTool):
    """List configured securities from a watchlist CSV."""

    name = "list_watchlist"
    description = "List securities in a watchlist CSV with symbol, market, exchange, sector, timeframes, and ATR metadata."
    parameters = {
        "type": "object",
        "properties": {
            "watchlist_path": {
                "type": "string",
                "description": "Path to watchlist CSV, defaults to watchlist/us_futures_watchlist.csv.",
            },
        },
        "required": [],
    }
    repeatable = True
```

**JSON error response pattern** (lines 55-67):
```python
try:
    path = _resolve_watchlist_path(watchlist_path)
except ValueError as exc:
    return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
if not path.exists():
    return json.dumps({"status": "error", "error": f"Watchlist not found: {watchlist_path}"}, ensure_ascii=False)

items = WatchlistReader(str(path)).load_raw()
return json.dumps(
    {"status": "ok", "watchlist": str(path), "count": len(items), "securities": items},
    ensure_ascii=False,
    indent=2,
)
```

**MTES summary output pattern** (lines 164-192):
```python
mtes_results = [
    {
        "symbol": r.symbol,
        "asset_class": r.mtes.get("asset_class") if r.mtes else None,
        "trend_score": r.mtes.get("trend_score") if r.mtes else None,
        "trend_state": r.mtes.get("trend_state") if r.mtes else None,
        "direction": r.mtes.get("direction") if r.mtes else None,
        "confidence": r.mtes.get("confidence") if r.mtes else None,
        "regime": r.mtes.get("regime") if r.mtes else None,
        "sub_scores": r.mtes.get("sub_scores") if r.mtes else {},
        "top_drivers": r.mtes.get("top_drivers") if r.mtes else [],
    }
    for r in results
    if not r.error
]
return json.dumps(
    {
        "status": "ok",
        "watchlist": str(path),
        "total": summary["total"],
        "success": summary["success"],
        "trends": summary["trends"],
        "signals": summary["signals"],
        "valid_signals": valid_signals,
        "mtes": mtes_results,
    },
    ensure_ascii=False,
    indent=2,
)
```

---

### `agent/src/data/watchlist.py` (existing dependency for timeframe adapter)

**Analog:** `agent/src/data/watchlist.py`.

**Raw row parser pattern** (lines 118-159):
```python
def load_raw(self) -> List[dict]:
    items = []

    if not self.watchlist_path.exists():
        logger.warning(f"Watchlist not found: {self.watchlist_path}")
        return items

    with open(self.watchlist_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "," in stripped:
            if stripped.lower().startswith("symbol,") or stripped.lower().startswith("code,"):
                continue
            parts = [p.strip() for p in stripped.split(",")]
            if len(parts) >= 2:
                item = {
                    "symbol": parts[0],
                    "name": parts[1] if len(parts) > 1 else parts[0],
                    "market": parts[2] if len(parts) > 2 else "us_futures",
                    ...
                    "timeframes": parts[5] if len(parts) > 5 else "1D-1H",
                }
                items.append(item)

    return items
```

**Watchlist timeframe pattern** (lines 190-208):
```python
def get_timeframes(self, symbol: str) -> tuple:
    raw_items = self.load_raw()
    for item in raw_items:
        if item["symbol"] == symbol:
            timeframes = item.get("timeframes", "1D-1H")
            parts = timeframes.split("-")
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()
            return "1D", "1H"
    return "1D", "1H"
```

**How to adapt:** D-13 requires watchlist-specified timeframes; reuse `get_timeframes()` / `get_trade_config()` rather than inventing separate parsing.

---

### `agent/tests/test_major_trend_evaluator.py` (test, batch transform/request-response)

**Analog:** `agent/tests/test_major_trend_evaluator.py`.

**Fixture factory pattern** (lines 19-35):
```python
def make_ohlcv(length: int = 320, start: float = 100, step: float = 1.0, noise: float = 0.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="D", name="timestamp")
    trend = pd.Series([start + i * step for i in range(length)], index=index)
    if noise:
        trend = trend + pd.Series([(-1) ** i * noise for i in range(length)], index=index)
    high = trend + 1.0
    low = trend - 1.0
    return pd.DataFrame(
        {
            "open": trend - 0.2,
            "high": high,
            "low": low,
            "close": trend,
            "volume": 1000,
        },
        index=index,
    )
```

**Profile and validation tests pattern** (lines 38-45):
```python
def test_asset_profiles_total_100() -> None:
    for asset_class in ASSET_WEIGHT_PROFILES:
        assert sum(get_weight_profile(asset_class).values()) == 100


def test_unsupported_asset_class_fails_clearly() -> None:
    with pytest.raises(ValueError, match="unsupported asset class"):
        get_weight_profile("unknown")
```

**Score contract test pattern** (lines 48-63):
```python
def test_strong_bull_fixture_scores_and_classifies() -> None:
    result = MajorTrendEvaluator().evaluate(make_ohlcv(step=1.0), asset_class="futures")

    assert result.direction == "BULL"
    assert result.trend_state in {TrendState.BULL_CONFIRMED.value, TrendState.BULL_STRONG.value}
    assert 0 <= result.trend_score <= 100
    assert set(result.sub_scores) == {
        "direction",
        "strength",
        "structure",
        "momentum",
        "volatility_regime",
        "mtf",
    }
    assert round(sum(result.sub_scores.values()), 2) == result.trend_score
    assert len(result.top_drivers) >= 3
```

**Insufficient/missing data tests pattern** (lines 94-108):
```python
def test_insufficient_data_returns_warning_without_crashing() -> None:
    result = MajorTrendEvaluator().evaluate(make_ohlcv(length=20), asset_class="stock")

    assert result.trend_state == TrendState.NEUTRAL_CHOPPY.value
    assert result.regime_flags == ["insufficient_data"]
    assert result.trend_score == 0.0


def test_missing_volume_does_not_crash() -> None:
    df = make_ohlcv().drop(columns=["volume"])

    result = MajorTrendEvaluator().evaluate(df, asset_class="fx")

    assert result.asset_class == "fx"
    assert result.trend_score >= 0
```

**MTF safety test pattern** (lines 111-124):
```python
def test_mtf_alignment_uses_completed_higher_timeframe_bars() -> None:
    base = make_ohlcv(length=80, step=0.5)
    higher = make_ohlcv(length=20, step=2.0).resample("W").last().dropna()

    result = MajorTrendEvaluator().evaluate(
        base,
        asset_class="futures",
        higher_timeframe=higher,
        base_timeframe="1d",
        higher_timeframe_name="1w",
    )

    assert result.metadata["mtf"]["method"] == "backward_lag"
    assert result.raw_scores["mtf"] in {25.0, 90.0}
```

**Watchlist integration test pattern** (lines 127-147):
```python
def test_watchlist_analyzer_includes_mtes_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    watchlist = tmp_path / "watchlist.csv"
    data_file = tmp_path / "data" / "us_futures" / "GC=F" / "1d.parquet"
    data_file.parent.mkdir(parents=True)
    make_ohlcv().to_parquet(data_file)
    watchlist.write_text(..., encoding="utf-8")

    result = WatchlistAnalyzer(watchlist_path=str(watchlist)).analyze_all(verbose=False)[0]
    payload = result.to_dict()

    assert payload["symbol"] == "GC=F"
    assert payload["asset_class"] == "futures"
    assert "trend_score" in payload
    assert "trend_state" in payload
    assert "sub_scores" in payload
    assert "top_drivers" in payload
```

---

### `agent/tests/test_mtes_strategy.py` or `agent/tests/backtest/...` (test, batch transform)

**Analog:** `agent/tests/test_strategy_watchlist_tools.py` and `agent/tests/test_major_trend_evaluator.py`.

**Tool/registry regression pattern** (lines 9-20 of `test_strategy_watchlist_tools.py`):
```python
def test_strategy_tools_are_registered_for_agent_use() -> None:
    registry = build_registry()

    expected = {
        "list_strategies",
        "get_strategy_info",
        "get_composer_template",
        "get_mtf_template",
    }

    assert expected <= set(registry.tool_names)
```

**JSON execution test pattern** (lines 34-40 of `test_strategy_watchlist_tools.py`):
```python
def test_list_strategies_tool_executes() -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("list_strategies", {"strategy_type": "trend"}))

    assert payload["status"] == "ok"
    assert "trend_ema_adx" in payload["content"]
```

**No progress stdout pattern** (lines 62-71 of `test_strategy_watchlist_tools.py`):
```python
def test_analyze_watchlist_tool_returns_json_without_progress_stdout(capsys) -> None:
    registry = build_registry()

    payload = json.loads(registry.execute("analyze_watchlist", {"watchlist_path": "watchlist/us_futures_watchlist.csv"}))
    captured = capsys.readouterr()

    assert captured.out == ""
    assert payload["status"] == "ok"
    assert payload["total"] == 8
```

**How to adapt:** Add tests that `StrategyRegistry.get("major_trend_evaluation")` or chosen name returns the MTES wrapper, generated DataFrame includes `signal`, `signal_name`, and MTES indicator columns, and confirmed/strong states map to non-zero signals.

---

### `docs/MTES_BACKTEST_VALIDATION_PLAN.md` (documentation/validation artifact, batch validation plan)

**Analog:** Current `docs/MTES_BACKTEST_VALIDATION_PLAN.md` draft plus `agent/backtest/strategies/comparison.py` report style.

**Validation plan structure pattern** (lines 5-17):
```markdown
## Objective

Validate whether the Major Trend Evaluation System (MTES) improves major-trend classification robustness versus single-indicator trend baselines across stocks, ETFs, futures, crypto, and FX.

## Asset Universes

| Universe | Examples | Data source |
|---|---|---|
| US futures | GC=F, SI=F, HG=F, CL=F, ZC=F, ZS=F, ES=F, NQ=F | local `data/us_futures` cache |
...
```

**Baseline strategy checklist pattern** (lines 26-37):
```markdown
## Baseline Strategies

At minimum compare MTES against these single-indicator or narrow baselines:

1. **SMA 200 direction:** price above/below 200-day SMA.
2. **Dual EMA crossover:** EMA 50 vs EMA 200.
3. **EMA + ADX:** existing `TrendEmaAdxStrategy` style confirmation.
4. **Donchian breakout:** close above/below 55-day high/low channel.
5. **Range Filter direction:** Range Filter up/down state.
6. **12-month momentum:** trailing 252-bar return sign and rank.
7. **MACD trend:** MACD line vs signal and zero line.
```

**Metrics and robustness pattern** (lines 55-68, 70-102):
```markdown
## Metrics

Primary metrics:

1. CAGR / annualized return.
2. Maximum drawdown.
3. Sharpe ratio.
4. Calmar ratio.
5. Turnover.
6. Whipsaw / false-signal rate.
...

## Robustness Checks

### Parameter perturbation

Pass if MTES remains within an acceptable degradation band when key windows shift by ±20%:
...

### MTF no-look-ahead

- Verify every lower-timeframe decision uses only completed higher-timeframe bars.
- Deliberately shift higher-timeframe data forward in a negative-control test; verification must detect inflated or invalid results.
```

**Comparison report markdown pattern** from `agent/backtest/strategies/comparison.py` (lines 370-484): use headings, summary table, winners-by-metric, recommendation, generated timestamp.

---

## Shared Patterns

### 1. Deterministic dataclass result with explicit `to_dict()`

**Source:** `agent/src/analysis/major_trend_evaluator.py` lines 110-141 and `agent/backtest/strategies/comparison.py` lines 19-60.

**Apply to:** Core evaluator result schemas and any new strategy metrics/result objects.

```python
@dataclass(frozen=True)
class MajorTrendResult:
    ...
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "trend_score": self.trend_score,
            ...
        }
```

### 2. Validate inputs early, return clear insufficient status where required

**Source:** `agent/src/analysis/major_trend_evaluator.py` lines 416-434 and 478-495; `agent/backtest/strategies/__init__.py` lines 114-131.

**Apply to:** Evaluator, backtest wrapper, watchlist adapter.

```python
missing = [column for column in required if column not in data.columns]
if missing:
    raise ValueError(f"missing required OHLC columns: {', '.join(missing)}")
...
if len(data) < required_bars:
    return insufficient_data_result(...)
```

### 3. Keep watchlist adapters thin and resilient

**Source:** `agent/src/analysis/watchlist_analyzer.py` lines 431-449.

**Apply to:** Watchlist MTES integration and tool summary.

```python
try:
    asset_class = resolve_asset_class(market)
    mtes_payload = MajorTrendEvaluator().evaluate(df, asset_class=asset_class).to_dict()
except Exception as exc:
    logger.warning("MTES evaluation failed for %s: %s", symbol, exc)
    mtes_payload = {
        "asset_class": "unknown",
        "trend_score": 0.0,
        "trend_state": "NEUTRAL_CHOPPY",
        ...
    }
```

### 4. Use `MTFAligner`; do not hand-roll higher-to-lower timeframe joins

**Source:** `agent/backtest/strategies/mtf.py` lines 142-193 and `agent/src/analysis/major_trend_evaluator.py` lines 394-400.

**Apply to:** MTF scoring dimension and tests.

```python
aligned = MTFAligner(MTFConfig(lag_bars=1)).align_htf_to_ltf(
    htf_data=htf[["major_direction"]],
    ltf_data=df[["close"]],
    htf_timeframe=higher_timeframe_name,
    ltf_timeframe=base_timeframe,
    htf_columns=["major_direction"],
)
```

### 5. Backtest strategies subclass `BaseStrategy` and emit DataFrame columns

**Source:** `agent/backtest/strategies/__init__.py` lines 149-178 and `agent/backtest/strategies/trend.py` lines 97-122, 184-203.

**Apply to:** `MajorTrendEvaluationStrategy`.

```python
result = df.copy()
result["signal"] = signals
result["signal_name"] = self.name
for name, series in indicators.items():
    result[name] = series
return result
```

### 6. Auto-register strategies in `registry.py`

**Source:** `agent/backtest/strategies/registry.py` lines 28-52 and 54-85.

**Apply to:** Strategy registry/export integration.

```python
def _register_strategies():
    strategies = [
        TrendEmaAdxStrategy(),
        TrendMacdStrategy(),
        TrendDualEmaStrategy(),
        ...
    ]

    for strategy in strategies:
        StrategyRegistry.register(strategy)
```

### 7. Machine-readable JSON tool responses use `json.dumps(..., ensure_ascii=False, indent=2)`

**Source:** `agent/src/tools/watchlist_tool.py` lines 62-67 and 179-192.

**Apply to:** Watchlist MTES output.

```python
return json.dumps(
    {"status": "ok", "watchlist": str(path), "count": len(items), "securities": items},
    ensure_ascii=False,
    indent=2,
)
```

### 8. Pytest style uses explicit fixtures, plain asserts, and `tmp_path`/`monkeypatch`

**Source:** `agent/tests/test_major_trend_evaluator.py` lines 19-35 and 127-147.

**Apply to:** Core evaluator tests, watchlist contract tests, strategy wrapper tests.

```python
def test_watchlist_analyzer_includes_mtes_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    watchlist = tmp_path / "watchlist.csv"
    data_file = tmp_path / "data" / "us_futures" / "GC=F" / "1d.parquet"
    data_file.parent.mkdir(parents=True)
    make_ohlcv().to_parquet(data_file)
    ...
    assert "trend_score" in payload
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/MTES_BACKTEST_VALIDATION_PLAN.md` | documentation / validation artifact | batch validation plan | No broader project validation-plan template was found. Use the existing draft document as the seed and borrow markdown table/report conventions from `agent/backtest/strategies/comparison.py`. |

## Metadata

**Analog search scope:**
- `agent/src/analysis/`
- `agent/backtest/strategies/`
- `agent/src/tools/`
- `agent/src/data/`
- `agent/tests/`
- `docs/`

**Files scanned:** 18 files listed/read during pattern mapping.

**Primary analogs read:**
- `agent/src/analysis/major_trend_evaluator.py`
- `agent/src/analysis/watchlist_analyzer.py`
- `agent/src/analysis/report_generator.py`
- `agent/src/analysis/__init__.py`
- `agent/backtest/strategies/trend.py`
- `agent/backtest/strategies/mtf.py`
- `agent/backtest/strategies/__init__.py`
- `agent/backtest/strategies/registry.py`
- `agent/backtest/strategies/comparison.py`
- `agent/backtest/validation.py`
- `agent/src/tools/watchlist_tool.py`
- `agent/src/data/watchlist.py`
- `agent/tests/test_major_trend_evaluator.py`
- `agent/tests/test_strategy_watchlist_tools.py`
- `docs/MTES_BACKTEST_VALIDATION_PLAN.md`

**Pattern extraction date:** 2026-05-29
