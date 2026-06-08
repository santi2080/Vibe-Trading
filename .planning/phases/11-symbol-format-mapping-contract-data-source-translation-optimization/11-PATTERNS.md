# Phase 11: Symbol Format Mapping Contract & Data Source Translation Optimization - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 19 source/test/planning files
**Analogs found:** 14 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agent/src/data/symbol_translator.py` | utility | transform | `agent/src/data/symbol_translator.py` | exact |
| `agent/src/data/market.py` | model/config | transform | `agent/src/data/market.py` | exact |
| `agent/backtest/loaders/hybrid_fetcher.py` | service/loader boundary | request-response + batch transform | `agent/backtest/loaders/hybrid_fetcher.py` | exact |
| `agent/backtest/loaders/akshare_loader.py` | loader/service | request-response + transform | `agent/backtest/loaders/akshare_loader.py` | exact |
| `agent/backtest/loaders/yfinance_loader.py` | loader/service | request-response + transform | `agent/backtest/loaders/yfinance_loader.py` | exact |
| `agent/backtest/loaders/tqsdk_loader.py` | loader/service | request-response + transform | `agent/backtest/loaders/tqsdk_loader.py` | exact |
| `agent/backtest/loaders/okx.py` | loader/service | request-response + transform | `agent/backtest/loaders/okx.py` | role-match |
| `agent/backtest/loaders/ccxt_loader.py` | loader/service | request-response + transform | `agent/backtest/loaders/ccxt_loader.py` | role-match |
| `agent/backtest/loaders/futu.py` | loader/service | request-response + transform | `agent/backtest/loaders/futu.py` | role-match |
| `agent/backtest/runner.py` | route/orchestrator | batch request-response | `agent/backtest/runner.py` | exact |
| `agent/tests/test_symbol_translator_contract.py` | test | transform contract | `agent/tests/test_market_detection.py` + `agent/tests/test_akshare_loader.py` | exact pattern |
| `agent/tests/test_hybrid_fetcher.py` | test | mocked request-response | `agent/tests/test_hybrid_fetcher.py` | exact |
| `agent/tests/test_akshare_loader.py` | test | mocked endpoint routing | `agent/tests/test_akshare_loader.py` | exact |
| `agent/tests/test_tqsdk_loader.py` | test | mocked vendor conversion | `agent/tests/test_tqsdk_loader.py` | exact |
| `agent/tests/test_market_detection.py` | test | transform classification | `agent/tests/test_market_detection.py` | exact |
| `agent/tests/test_get_market_data_unresolved.py` | test | unresolved request-response | `agent/tests/test_get_market_data_unresolved.py` | role-match |
| `agent/tests/test_registry.py` | test | fallback routing | `agent/tests/test_registry.py` | role-match |

## Files to Edit

### Required source edits

1. `agent/src/data/symbol_translator.py`
   - Make this the documented canonical-to-vendor contract.
   - Update stale top docstring so canonical examples match Phase 11 decisions: `600036.SH`, `000001.SZ`, `0700.HK`/`00700.HK`, `AAPL.US`, `GC=F`, `rb0`, `IF2406`, `BTC-USDT`, `EURUSD`.
   - Fix AKShare mappings to match endpoint expectations: A-share/ETF `600036.SH -> sh600036`, `159915.SZ -> sz159915`; HK `00700.HK -> 00700`; US futures `GC=F -> GC`; CN futures `rb0 -> RB0`; crypto/forex pass through or explicit unsupported per vendor.
   - Add explicit unsupported handling for impossible market/vendor pairs rather than silent suffix stripping.
   - Preserve `SymbolTranslator.to_vendor_format(symbol, vendor, market) -> str` compatibility unless the implementation plan intentionally introduces an additive result helper.

2. `agent/backtest/loaders/hybrid_fetcher.py`
   - Preserve `SymbolRouter.translate_symbol()` as the adapter from `DataSource` to `DataVendor`.
   - Fix `HybridDataFetcher.fetch()` so vendor calls receive translated symbols and returned data is re-keyed to canonical symbols.
   - Preserve caller-facing canonical keys in `FetchResult.symbol`, `all_results`, validation reports, freshness reports, and returned dict.
   - Preserve fallback behavior when a source returns empty or unavailable.

3. `agent/backtest/loaders/akshare_loader.py`
   - Either delegate endpoint-specific conversion helpers to `SymbolTranslator` or keep them as compatibility shims with contract tests.
   - Preserve direct-use canonical inputs (`600519.SH`, `518880.SH`, `00700.HK`, `GC=F`, `rb0`, `EURUSD`).
   - Preserve mocked endpoint routing patterns in tests; no live AKShare call required.

4. `agent/backtest/loaders/yfinance_loader.py`
   - Either delegate `_to_yfinance_symbol()` to `SymbolTranslator` or keep as tested shim.
   - Preserve direct-use canonical inputs and original-key result mapping.

5. `agent/backtest/loaders/tqsdk_loader.py`
   - Preserve `_to_tqsdk_symbol()` as current `SymbolTranslator` delegation pattern.
   - Keep direct input keys (`rb0`, `if2406`) in returned results.

6. `agent/backtest/loaders/okx.py` and `agent/backtest/loaders/ccxt_loader.py`
   - Preserve direct crypto compatibility: OKX uses hyphen (`BTC-USDT`), CCXT converts to slash internally (`BTC/USDT`) while returning original request keys.
   - If `DataVendor.OKX` / `DataVendor.CCXT` are added, wire them as explicit pass-through/transform contracts.

7. `agent/backtest/runner.py`
   - Preserve shared `_detect_market`, `_detect_source`, `_group_codes_by_market`, `_group_codes_by_source` semantics.
   - If auto-mode source normalization is touched, preserve canonical external config keys and `_unresolved`/fallback expectations.

### Required test additions/updates

1. Add `agent/tests/test_symbol_translator_contract.py`
   - Use pytest parametrize style from `test_market_detection.py`.
   - Cover canonical-to-vendor contracts for Tushare, AKShare, yfinance, TqSdk, OKX, CCXT, Databento where supported.
   - Cover unsupported vendor/market combinations explicitly.
   - Cover deterministic HK normalization (`0700.HK` vs `00700.HK`) per final implementation contract.

2. Update `agent/tests/test_hybrid_fetcher.py::TestSymbolTranslatorIntegration`
   - Replace shallow assertions with exact contract assertions.
   - Add mocked `HybridDataFetcher.fetch()` tests verifying `pool.fetch()` receives vendor symbols and final results are canonical-keyed.
   - Include fallback or empty-result behavior with canonical keys preserved.

3. Update `agent/tests/test_akshare_loader.py`
   - Keep endpoint-routing mocks.
   - Add exact vendor-symbol assertions for stocks, ETFs, HK, US futures, CN futures, forex where needed.

4. Update `agent/tests/test_tqsdk_loader.py`
   - Preserve current exact TqSdk expectations if the central translator changes internals.

5. Update `agent/tests/test_market_detection.py`
   - Add missing Phase 11 canonical examples: `GC=F`, `CL=F`, `SI=F`, `rb0`, `al0`, `IF2406`, `rb2410`, `BTC-USDT`, `EURUSD` if not already fully covered.

6. Preserve `agent/tests/test_get_market_data_unresolved.py` and `agent/tests/test_registry.py`
   - Run as regression checks if hybrid fetch/routing changes touch fallback or unresolved behavior.

## Pattern Assignments

### `agent/src/data/symbol_translator.py` (utility, transform)

**Analog:** `agent/src/data/symbol_translator.py`

**Imports and enum pattern** (lines 14-18, 23-35):
```python
import logging
from enum import Enum
from typing import Dict, Optional

from .market import Market

logger = logging.getLogger(__name__)


class DataVendor(Enum):
    """数据供应商枚举"""

    YAHOO_FINANCE = "yahoo"
    TWELVEDATA = "twelvedata"
    AKSHARE = "akshare"
    ITICK = "itick"
    TUSHARE = "tushare"
    QUANDL = "quandl"
    ALPHAVANTAGE = "alphavantage"
    TQSDK = "tqsdk"
    DATABENTO = "databento"
```

**Core dispatch pattern** (lines 90-135):
```python
@classmethod
def to_vendor_format(cls, symbol: str, vendor: DataVendor, market: Market) -> str:
    """将标准格式转换为特定数据源的格式

    Args:
        symbol: 标准格式代码
        vendor: 目标数据源
        market: 市场类型

    Returns:
        数据源特定格式的代码
    """
    # 美国期货 - Yahoo Finance 需要 CBOT 农产品符号映射
    if market == Market.US_FUTURES and vendor == DataVendor.YAHOO_FINANCE:
        return cls._to_yahoo_finance_format(symbol)

    # 美国期货 - Databento 需要连续合约格式
    if market == Market.US_FUTURES and vendor == DataVendor.DATABENTO:
        return cls._to_databento_format(symbol)

    # 中国期货 - TqSdk 格式
    if market == Market.CN_FUTURES and vendor == DataVendor.TQSDK:
        return cls.to_tqsdk_format(symbol, market)

    # 中国期货 - Tushare 格式
    if market == Market.CN_FUTURES and vendor == DataVendor.TUSHARE:
        return symbol

    # A股 - Akshare 只需要纯数字
    if market == Market.CN_STOCK and vendor == DataVendor.AKSHARE:
        return symbol.replace(".", "")

    # A股 - Tushare 需要交易所后缀
    if market == Market.CN_STOCK and vendor == DataVendor.TUSHARE:
        return symbol  # 调用者需要添加交易所

    # 港股 - Yahoo Finance 需要 .HK 后缀
    if market == Market.HK_STOCK and vendor == DataVendor.YAHOO_FINANCE:
        return f"{symbol}.HK" if not symbol.endswith(".HK") else symbol

    # 港股 - Akshare 需要 5 位数字
    if market == Market.HK_STOCK and vendor == DataVendor.AKSHARE:
        return symbol.zfill(5)

    # 默认返回原始符号
    return symbol
```

**TqSdk-specific transform pattern** (lines 161-187):
```python
@classmethod
def to_tqsdk_format(cls, symbol: str, market: Market) -> str:
    """转换为 TqSdk 格式

    Args:
        symbol: 标准格式代码（如 ag0, rb0, TA0）
        market: 市场类型

    Returns:
        TqSdk 格式（如 KQ.m@SHFE.ag）
    """
    if market != Market.CN_FUTURES:
        return symbol

    # 提取基础代码
    base = "".join(filter(str.isalpha, symbol))
    exchange = cls.TQSDK_EXCHANGE_MAP.get(base.upper(), cls.TQSDK_EXCHANGE_MAP.get(base.lower(), "SHFE"))

    # 主连合约
    if symbol.endswith("0"):
        if exchange in {"CFFEX", "CZCE"}:
            return f"KQ.m@{exchange}.{base.upper()}"
        return f"KQ.m@{exchange}.{base.lower()}"

    # 具体合约
    if exchange in {"CFFEX", "CZCE"}:
        return f"{exchange}.{symbol.upper()}"
    return f"{exchange}.{symbol.lower()}"
```

**Implementation guidance:** Keep dispatch table readable and explicit. Prefer small private helpers per vendor/market rather than putting endpoint-specific string manipulation inline. Do not keep the current AKShare A-share behavior (`600519.SH -> 600519SH`) because `akshare_loader.py` proves AKShare’s stock endpoint uses `sh600519` / `sz000001`.

---

### `agent/src/data/market.py` (model/config, transform)

**Analog:** `agent/src/data/market.py`

**Enum and alias pattern** (lines 8-23, 52-73):
```python
class Market(Enum):
    """市场枚举"""

    US_STOCK = auto()  # 美股
    US_FUTURES = auto()  # 美国期货
    US_ETF = auto()  # 美国ETF
    CN_STOCK = auto()  # A股
    CN_FUTURES = auto()  # 中国期货
    CN_ETF = auto()  # 中国ETF
    HK_STOCK = auto()  # 港股
    HK_FUTURES = auto()  # 港期

    # 虚拟市场类型（用于数据源路由）
    US_FUTURES_INTRADAY = auto()  # 美国期货日内数据（H4/H1）
    US_FUTURES_DAILY = auto()  # 美国期货日线数据（D1/W1）


# 字符串到枚举的转换
MARKET_STR_TO_ENUM = {
    "us_stock": Market.US_STOCK,
    "us_futures": Market.US_FUTURES,
    "us_etf": Market.US_ETF,
    "cn_stock": Market.CN_STOCK,
    "cn_stocks": Market.CN_STOCK,
    "cn_futures": Market.CN_FUTURES,
    "cn_etf": Market.CN_ETF,
    "hk_stock": Market.HK_STOCK,
    "hk_futures": Market.HK_FUTURES,
```

**Validation pattern** (lines 90-104):
```python
def parse_market(market_str: str) -> Market:
    """解析市场字符串到枚举"""
    key = market_str.lower().strip()
    if key not in MARKET_STR_TO_ENUM:
        raise ValueError(f"Unknown market: {market_str}")
    return MARKET_STR_TO_ENUM[key]


def parse_timeframe(tf_str: str) -> Timeframe:
    """解析时间周期字符串"""
    key = tf_str.lower().strip()
    if key not in TIMEFRAME_STR_TO_ENUM:
        raise ValueError(f"Unknown timeframe: {tf_str}")
    return TIMEFRAME_STR_TO_ENUM[key]
```

**Implementation guidance:** If Phase 11 adds market aliases, follow this explicit alias-map pattern and keep errors explicit. Avoid silently coercing unsupported strings into a plausible market.

---

### `agent/backtest/loaders/hybrid_fetcher.py` (service/loader boundary, batch request-response)

**Analog:** `agent/backtest/loaders/hybrid_fetcher.py`

**Imports and central dependency pattern** (lines 31-39):
```python
from agent.backtest.loaders.registry import (
    LOADER_REGISTRY,
    FALLBACK_CHAINS,
    _ensure_registered,
)
from agent.src.data.quality import DataQualityMonitor, QualityReport
from agent.src.data.freshness import DataFreshnessChecker
from agent.src.data.symbol_translator import SymbolTranslator, DataVendor as SrcDataVendor
```

**Source-to-vendor map pattern** (lines 172-180):
```python
# Mapping from hybrid_fetcher DataSource to symbol_translator DataVendor
# Used for symbol format translation
SOURCE_TO_VENDOR = {
    DataSource.AKSHARE: SrcDataVendor.AKSHARE,
    DataSource.YFINANCE: SrcDataVendor.YAHOO_FINANCE,
    DataSource.TUSHARE: SrcDataVendor.TUSHARE,
    DataSource.TQSDK: SrcDataVendor.TQSDK,
    DataSource.DATABENTO: SrcDataVendor.DATABENTO,
}
```

**Translator adapter pattern** (lines 243-282):
```python
def translate_symbol(
    self,
    symbol: str,
    market: MarketType,
    source: DataSource,
) -> str:
    """Translate symbol to the vendor-specific format.

    Args:
        symbol: Original symbol
        market: Detected market type
        source: Target data source

    Returns:
        Symbol in vendor-specific format
    """
    from agent.src.data.market import Market

    # Map MarketType to Market enum
    market_map = {
        MarketType.A_SHARE: Market.CN_STOCK,
        MarketType.US_EQUITY: Market.US_STOCK,
        MarketType.HK_EQUITY: Market.HK_STOCK,
        MarketType.CN_FUTURES: Market.CN_FUTURES,
        MarketType.US_FUTURES: Market.US_FUTURES,
        MarketType.CRYPTO: Market.US_STOCK,  # Crypto uses equity market
        MarketType.FUND: Market.CN_ETF,
        MarketType.FOREX: Market.US_STOCK,  # Forex uses equity market
        MarketType.MACRO: Market.US_STOCK,
    }

    mapped_market = market_map.get(market, Market.US_STOCK)

    # Get vendor enum
    vendor = self.SOURCE_TO_VENDOR.get(source)
    if vendor is None:
        return symbol

    return SymbolTranslator.to_vendor_format(symbol, vendor, mapped_market)
```

**Current fetch pattern that must be fixed** (lines 562-622):
```python
# Group symbols by market
by_market: Dict[MarketType, List[str]] = {}
for symbol in symbols:
    market, _ = self.router.route_symbol(symbol)
    by_market.setdefault(market, []).append(symbol)

# Fetch each market
all_results: Dict[str, Dict[DataSource, FetchResult]] = {}
stats = FetchStats(total=len(symbols))

for market, market_symbols in by_market.items():
    # Determine sources to try
    if source_preference:
        sources_to_try = source_preference
    else:
        sources_to_try = self._get_sources_for_market(market)

    # Fetch from each source
    for source in sources_to_try[:self.max_sources_per_symbol]:
        fetch_start = time.time()
        try:
            raw = self.pool.fetch(source, market_symbols, start_date, end_date, interval)
            latency_ms = (time.time() - fetch_start) * 1000

            for symbol in market_symbols:
                df = raw.get(symbol)
                result = FetchResult(
                    symbol=symbol,
                    df=df,
                    source=source.value if df is not None and not df.empty else None,
                    latency_ms=latency_ms,
                )
```

**Implementation guidance:** Insert translation between `market_symbols` and `pool.fetch()` and keep a reverse map such as `{vendor_symbol: canonical_symbol}`. When processing `raw`, look up both `raw.get(vendor_symbol)` and compatibility `raw.get(canonical_symbol)` if loaders still return canonical keys. Store all `FetchResult` entries under canonical `symbol` and return canonical keys only.

---

### `agent/backtest/loaders/akshare_loader.py` (loader/service, endpoint transform)

**Analog:** `agent/backtest/loaders/akshare_loader.py`

**Market predicate pattern** (lines 25-39, 87-123):
```python
def _is_a_share(code: str) -> bool:
    return code.upper().endswith((".SZ", ".SH", ".BJ"))


def _is_hk(code: str) -> bool:
    return code.upper().endswith(".HK")


def _is_us(code: str) -> bool:
    return code.upper().endswith(".US")


def _is_crypto(code: str) -> bool:
    return "-USDT" in code.upper() or "/USDT" in code.upper()


def _is_etf_listed(code: str) -> bool:
    """Detect exchange-listed ETF / LOF symbols (e.g. 518880.SH, 159915.SZ)."""
    upper = code.upper()
    if not upper.endswith((".SH", ".SZ")):
        return False
    digits = upper.split(".")[0]
    if len(digits) != 6 or not digits.isdigit():
        return False
    return digits[:2] in _ETF_PREFIXES
```

**Endpoint dispatch pattern** (lines 184-202):
```python
# Check for CN futures first (before US futures)
if _is_cn_futures(code):
    return self._fetch_cn_futures(ak, code, start_date, end_date, interval)
# Check for US futures
if _is_us_futures(code):
    return self._fetch_us_futures(ak, code, start_date, end_date, interval)
# ETF check must precede A-share — 518880.SH ends with .SH but is an ETF.
if _is_etf_listed(code):
    return self._fetch_etf(ak, code, start_date, end_date)
if _is_a_share(code):
    return self._fetch_a_share(ak, code, start_date, end_date, interval)
if _is_us(code):
    return self._fetch_us(ak, code, start_date, end_date)
if _is_hk(code):
    return self._fetch_hk(ak, code, start_date, end_date)
if _is_forex(code):
    return self._fetch_forex(ak, code, start_date, end_date)
# Default: try A-share
return self._fetch_a_share(ak, code, start_date, end_date, interval)
```

**A-share vendor symbol pattern** (lines 212-230):
```python
parts = code.upper().split(".")
symbol_raw = parts[0]
suffix = parts[1] if len(parts) > 1 else ""

# Convert to Sina format: 600519.SH -> sh600519, 000001.SZ -> sz000001
if suffix == "SH":
    symbol = f"sh{symbol_raw}"
elif suffix == "SZ":
    symbol = f"sz{symbol_raw}"
else:
    # Fallback: assume Shanghai
    symbol = f"sh{symbol_raw}"

df = ak.stock_zh_a_daily(
    symbol=symbol,
    start_date=start_date.replace("-", ""),
    end_date=end_date.replace("-", ""),
    adjust="qfq",  # forward-adjusted prices
)
```

**ETF / HK / futures vendor symbol patterns** (lines 261-263, 299-303, 322-326, 363-374):
```python
digits, _, suffix = code.upper().partition(".")
symbol = f"{suffix.lower()}{digits}"
df = ak.fund_etf_hist_sina(symbol=symbol)
```

```python
symbol = code.replace(".HK", "").zfill(5)
df = ak.stock_hk_hist(
    symbol=symbol,
    period="daily",
```

```python
# Convert GC=F to GC
symbol = code.upper().replace("=F", "").replace("=P", "")

try:
    df = ak.futures_foreign_hist(symbol=symbol)
```

```python
# Convert al0 -> AL0, rb0 -> RB0
code_lower = code.lower()
if code_lower in _CN_FUTURES_MAP:
    symbol = _CN_FUTURES_MAP[code_lower]
else:
    # Try uppercase without 0
    symbol = code.upper().rstrip("0")
    if not symbol:
        symbol = code.upper()
```

**Error handling pattern** (lines 168-176):
```python
result: Dict[str, pd.DataFrame] = {}
for code in codes:
    try:
        df = self._fetch_one(code, start_date, end_date, interval)
        if df is not None and not df.empty:
            result[code] = df
    except Exception as exc:
        logger.debug("akshare failed for %s: %s", code, exc)
return result
```

**Implementation guidance:** The translator should copy these exact endpoint symbol conversions for AKShare. If direct loader logic remains, tests must pin that compatibility behavior. Preserve result keys as input `code` in `fetch()`.

---

### `agent/backtest/loaders/yfinance_loader.py` (loader/service, endpoint transform)

**Analog:** `agent/backtest/loaders/yfinance_loader.py`

**Symbol conversion pattern** (lines 39-56):
```python
def _to_yfinance_symbol(code: str) -> str:
    """Convert project symbols into yfinance symbols.

    Args:
        code: Project symbol, for example ``AAPL.US``, ``700.HK``, or ``GC=F``.

    Returns:
        yfinance-compatible symbol.
    """
    upper = code.strip().upper()
    if upper.endswith(".US"):
        return upper[:-3]
    if upper.endswith(".HK"):
        digits = upper[:-3]
        width = max(4, len(digits))
        return f"{digits.zfill(width)}.HK"
    # US futures symbols (e.g., GC=F, CL=F) pass through unchanged
    return upper
```

**Bulk grouping while preserving original keys** (lines 285-320):
```python
symbol_groups: Dict[str, List[str]] = defaultdict(list)
for code in codes:
    symbol_groups[_to_yfinance_symbol(code)].append(code)

unique_symbols = list(symbol_groups.keys())
results: Dict[str, pd.DataFrame] = {}

try:
    bulk_data = _download_history(
        unique_symbols, start_date, end_date, yf_interval, self.proxy_manager
    )
```

```python
for original_code in symbol_groups[symbol]:
    results[original_code] = normalized.copy()
```

**Implementation guidance:** This is the closest analog for `HybridDataFetcher.fetch()` re-keying. Translate to vendor symbols for the provider call, group canonical symbols behind each vendor symbol, and return original canonical keys.

---

### `agent/backtest/loaders/tqsdk_loader.py` (loader/service, central translator integration)

**Analog:** `agent/backtest/loaders/tqsdk_loader.py`

**Central translator delegation pattern** (lines 32-36, 95-98):
```python
from agent.src.data.market import Market
from agent.src.data.symbol_translator import DataVendor, SymbolTranslator


def _to_tqsdk_symbol(code: str) -> str:
    """Convert project symbol to TqSdk format."""
    return SymbolTranslator.to_vendor_format(code.strip(), DataVendor.TQSDK, Market.CN_FUTURES)
```

**Fetch calls vendor with translated symbol but returns input key** (lines 352-376):
```python
try:
    with self._pool.get_connection() as api:
        for code in codes:
            tqsdk_code = _to_tqsdk_symbol(code)

            try:
                # Get kline data
                df = api.get_kline_serial(
                    tqsdk_code,
                    duration_seconds=int(duration),
                    data_length=10000,
                )

                # Filter by date range
                if not df.empty:
                    df = df.copy()
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    start_dt = pd.Timestamp(start_date)
                    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)

                    df = df[df["datetime"] >= start_dt]
                    df = df[df["datetime"] < end_dt]

                    results[code] = _normalize_frame(df)
                    logger.debug(f"Fetched {len(results[code])} bars for {code}")
```

**Implementation guidance:** Copy this pattern for any loader-local conversion that should delegate to the central translator. Always return `results[code]`, not `results[tqsdk_code]`.

---

### `agent/backtest/loaders/okx.py` and `agent/backtest/loaders/ccxt_loader.py` (crypto loader transform)

**Analogs:** `agent/backtest/loaders/okx.py`, `agent/backtest/loaders/ccxt_loader.py`

**OKX direct hyphen canonical pattern** (`okx.py` lines 77-90):
```python
codes = [c.replace("/", "-").upper() for c in codes]

start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
end_ts = int((pd.Timestamp(end_date) + pd.Timedelta(days=1)).timestamp() * 1000)

max_pages = 200 if interval in ("1m", "5m") else 50 if interval in ("15m", "30m") else 20

result: Dict[str, pd.DataFrame] = {}
for symbol in codes:
    try:
        df = self._fetch_candles(symbol, start_ts, end_ts, interval, max_pages)
        if df is not None and not df.empty:
            result[symbol] = df
```

**CCXT slash vendor conversion with original-key return** (`ccxt_loader.py` lines 96-105):
```python
result: Dict[str, pd.DataFrame] = {}
for code in codes:
    try:
        ccxt_symbol = code.replace("-", "/").upper()
        df = self._fetch_one(exchange, ccxt_symbol, timeframe, since_ms, end_ms)
        if df is not None and not df.empty:
            result[code] = df
    except Exception as exc:
        logger.warning("CCXT failed for %s: %s", code, exc)
return result
```

**Implementation guidance:** `BTC-USDT` is already the project canonical crypto example. OKX can be pass-through/uppercase-hyphen; CCXT must use slash at boundary but return canonical keys.

---

### `agent/backtest/loaders/futu.py` (loader/service, vendor prefix transform)

**Analog:** `agent/backtest/loaders/futu.py`

**Futu vendor transform pattern** (lines 26-42):
```python
def _to_futu_symbol(code: str) -> str:
    """Convert project symbol to Futu OpenAPI format.

    Examples:
        700.HK    -> HK.00700
        5.HK      -> HK.00005
        000001.SZ -> SZ.000001
        600519.SH -> SH.600519
    """
    upper = code.strip().upper()
    if upper.endswith(".HK"):
        return f"HK.{upper[:-3].zfill(5)}"
    if upper.endswith(".SZ"):
        return f"SZ.{upper[:-3].zfill(6)}"
    if upper.endswith(".SH"):
        return f"SH.{upper[:-3].zfill(6)}"
    return upper
```

**Fetch vendor symbol while returning input key** (lines 144-159):
```python
results: Dict[str, pd.DataFrame] = {}
try:
    for code in codes:
        futu_code = _to_futu_symbol(code)
        ret, data = ctx.request_history_kline(
            futu_code,
            start=start_date,
            end=end_date,
            ktype=ktype,
            max_count=10_000,
        )
        if ret != futu.RET_OK:
            logger.warning("Futu returned error for %s: %s", futu_code, data)
            continue
        results[code] = _normalize_frame(data)
finally:
    ctx.close()
```

**Implementation guidance:** Phase 11 requirements name Tushare/AKShare/yfinance/TqSdk/OKX/CCXT/Databento, but `HybridDataFetcher` routes HK to Futu first when available. If Futu is included in the contract, copy this explicit prefix pattern.

---

### `agent/backtest/runner.py` (route/orchestrator, batch request-response)

**Analog:** `agent/backtest/runner.py`

**Shared market/source grouping pattern** (lines 383-425):
```python
def _detect_source(code: str) -> str:
    """Infer legacy source name from symbol (back-compat for metrics/engine).

    Args:
        code: Ticker / symbol string.

    Returns:
        Source name (tushare/okx/yfinance/akshare).
    """
    market = _detect_market(code)
    return _MARKET_TO_SOURCE.get(market, "tushare")


def _group_codes_by_market(codes: List[str]) -> Dict[str, List[str]]:
    """Group symbols by detected market type.

    Args:
        codes: List of symbol strings.

    Returns:
        Mapping market_type -> list of codes.
    """
    groups: Dict[str, List[str]] = {}
    for code in codes:
        market = _detect_market(code)
        groups.setdefault(market, []).append(code)
    return groups


def _group_codes_by_source(codes: List[str]) -> Dict[str, List[str]]:
    """Group symbols by inferred source (back-compat).

    Args:
        codes: List of symbol strings.

    Returns:
        Mapping source -> list of codes.
    """
    groups: Dict[str, List[str]] = {}
    for code in codes:
        src = _detect_source(code)
        groups.setdefault(src, []).append(code)
    return groups
```

**Normalization compatibility pattern** (lines 446-458):
```python
def _normalize_codes(codes: List[str], source: str) -> List[str]:
    """Normalize symbol strings for a source.

    Args:
        codes: Raw code list.
        source: Data source.

    Returns:
        Normalized codes.
    """
    if source in ("okx", "ccxt"):
        return [c.replace("/", "-").upper() for c in codes]
    return codes
```

**Fallback routing pattern** (lines 694-723):
```python
for market, market_codes in market_groups.items():
    try:
        loader = resolve_loader(market)
    except NoAvailableSourceError as exc:
        # Fallback: try legacy source mapping
        legacy_src = _MARKET_TO_SOURCE.get(market, "tushare")
        logger.warning("Fallback chain failed for %s: %s — trying %s", market, exc, legacy_src)
        LoaderCls = _get_loader(legacy_src)
        loader = LoaderCls()

    src_name = getattr(loader, "name", "unknown")
    normalized_codes = _normalize_codes(market_codes, src_name)
    fields = config.get("extra_fields") if src_name == "tushare" else None
    result = loader.fetch(normalized_codes, start_date, end_date, fields=fields, interval=interval)

    # Runtime fallback: try remaining sources when primary returns empty
    if not result:
        for fb_name in FALLBACK_CHAINS.get(market, []):
            if fb_name == src_name or fb_name not in LOADER_REGISTRY:
                continue
            fb_loader = LOADER_REGISTRY[fb_name]()
            if not fb_loader.is_available():
                continue
            fb_codes = _normalize_codes(market_codes, fb_name)
            result = fb_loader.fetch(fb_codes, start_date, end_date, interval=interval)
            if result:
                logger.info("Runtime fallback: %s -> %s for %s", src_name, fb_name, market)
                break

    merged.update(result)
```

**Implementation guidance:** This is a fallback-preservation analog, not necessarily a required edit. If Phase 11 changes auto-mode normalization, re-key normalized results back to canonical just like yfinance/tqsdk patterns.

---

## Test Pattern Assignments

### `agent/tests/test_symbol_translator_contract.py` (new test, transform contract)

**Analogs:** `agent/tests/test_market_detection.py`, `agent/tests/test_akshare_loader.py`, `agent/tests/test_tqsdk_loader.py`

**Parametrize style** (`test_market_detection.py` lines 28-69):
```python
class TestDetectMarket:
    """Symbol pattern → market type mapping."""

    @pytest.mark.parametrize(
        "code, expected",
        [
            # A-share mainboard
            ("000001.SZ", "a_share"),
            ("600519.SH", "a_share"),
            ("300750.SZ", "a_share"),
            # A-share Beijing exchange
            ("830799.BJ", "a_share"),
            # A-share ETF
            ("510300.SH", "a_share"),
            ("159919.SZ", "a_share"),
            ("560010.SH", "a_share"),
```

**Exact endpoint assertion style** (`test_akshare_loader.py` lines 131-147, 166-185):
```python
class TestRouting:
    def test_etf_routes_to_fund_etf_hist_sina(self, fake_akshare: SimpleNamespace) -> None:
        loader = DataLoader()
        df = loader._fetch_one("518880.SH", "2024-01-01", "2024-12-31", "1D")

        fake_akshare.fund_etf_hist_sina.assert_called_once_with(symbol="sh518880")
        fake_akshare.stock_zh_a_daily.assert_not_called()
        assert df is not None
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 2

    def test_etf_sz_uses_sz_prefix(self, fake_akshare: SimpleNamespace) -> None:
        loader = DataLoader()
        loader._fetch_one("159915.SZ", "2024-01-01", "2024-12-31", "1D")

        fake_akshare.fund_etf_hist_sina.assert_called_once_with(symbol="sz159915")
```

```python
def test_a_share_routes_to_stock_zh_a_daily(
    self, fake_akshare: SimpleNamespace
) -> None:
    loader = DataLoader()
    loader._fetch_one("600519.SH", "2024-01-01", "2024-01-10", "1D")

    # Sina format: sh600519
    fake_akshare.stock_zh_a_daily.assert_called_once()
    call_args = fake_akshare.stock_zh_a_daily.call_args
    assert call_args.kwargs["symbol"] == "sh600519"
```

**TqSdk exact conversion assertions** (`test_tqsdk_loader.py` lines 60-75):
```python
def test_symbol_translation_uses_tqsdk_main_contract_format():
    assert _to_tqsdk_symbol("rb0") == "KQ.m@SHFE.rb"


def test_symbol_translation_uses_correct_dce_exchange():
    assert _to_tqsdk_symbol("i0") == "KQ.m@DCE.i"


def test_symbol_translation_uses_correct_cffex_case():
    assert _to_tqsdk_symbol("if0") == "KQ.m@CFFEX.IF"


def test_symbol_translation_normalizes_specific_contract_case():
    assert _to_tqsdk_symbol("RB2405") == "SHFE.rb2405"
    assert _to_tqsdk_symbol("if2406") == "CFFEX.IF2406"
```

**Recommended contract-test matrix:**

| Canonical | Market | Vendor | Expected Vendor Symbol | Notes |
|-----------|--------|--------|------------------------|-------|
| `600036.SH` | `Market.CN_STOCK` | `DataVendor.TUSHARE` | `600036.SH` | Tushare expects `ts_code` suffix |
| `600036.SH` | `Market.CN_STOCK` | `DataVendor.AKSHARE` | `sh600036` | Sina stock endpoint |
| `000001.SZ` | `Market.CN_STOCK` | `DataVendor.AKSHARE` | `sz000001` | Sina stock endpoint |
| `518880.SH` | `Market.CN_ETF` or `Market.CN_STOCK` | `DataVendor.AKSHARE` | `sh518880` | ETF endpoint uses same prefix style |
| `159915.SZ` | `Market.CN_ETF` or `Market.CN_STOCK` | `DataVendor.AKSHARE` | `sz159915` | ETF endpoint uses same prefix style |
| `AAPL.US` | `Market.US_STOCK` | `DataVendor.YAHOO_FINANCE` | `AAPL` | yfinance strips `.US` |
| `0700.HK` | `Market.HK_STOCK` | `DataVendor.YAHOO_FINANCE` | `0700.HK` | yfinance min 4 digits |
| `00700.HK` | `Market.HK_STOCK` | `DataVendor.AKSHARE` | `00700` | AKShare HK endpoint |
| `GC=F` | `Market.US_FUTURES` | `DataVendor.AKSHARE` | `GC` | AKShare foreign futures |
| `ZC=F` | `Market.US_FUTURES` | `DataVendor.YAHOO_FINANCE` | `ZC=F` | current Yahoo futures map handles `C -> ZC` only when input is `C=F` |
| `GC=F` | `Market.US_FUTURES` | `DataVendor.DATABENTO` | `GC.c.0` | existing Databento map |
| `rb0` | `Market.CN_FUTURES` | `DataVendor.TQSDK` | `KQ.m@SHFE.rb` | current tested behavior |
| `IF2406` | `Market.CN_FUTURES` | `DataVendor.TQSDK` | `CFFEX.IF2406` | concrete contract |
| `rb2410` | `Market.CN_FUTURES` | `DataVendor.TQSDK` | `SHFE.rb2410` | concrete contract |
| `rb0` | `Market.CN_FUTURES` | `DataVendor.AKSHARE` | `RB0` | AKShare CN futures endpoint |
| `BTC-USDT` | crypto market representation | `OKX` if added | `BTC-USDT` | OKX hyphen |
| `BTC-USDT` | crypto market representation | `CCXT` if added | `BTC/USDT` | CCXT slash |
| `EURUSD` | forex market representation | `DataVendor.AKSHARE` | `EURUSD` | AKShare forex endpoint |

---

### `agent/tests/test_hybrid_fetcher.py` (test, mocked request-response)

**Analog:** `agent/tests/test_hybrid_fetcher.py`

**Mock fixture pattern** (lines 138-162):
```python
@pytest.fixture
def fetcher(self):
    with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
        return HybridDataFetcher()

@pytest.fixture
def mock_router(self, fetcher):
    with patch.object(fetcher.router, "route_symbol") as mock:
        mock.return_value = (MarketType.A_SHARE, DataSource.AKSHARE)
        yield mock

@pytest.fixture
def mock_pool(self, fetcher):
    with patch.object(fetcher.pool, "fetch") as mock:
        mock.return_value = {
            "600519.SH": pd.DataFrame({
                "open": [100.0],
                "high": [105.0],
                "low": [98.0],
                "close": [103.0],
                "volume": [1000.0],
            })
        }
        yield mock
```

**Existing fetch test pattern** (lines 171-197):
```python
def test_fetch_multiple_symbols(self, fetcher):
    with patch.object(fetcher.router, "route_symbol") as mock_route, \
         patch.object(fetcher.router, "check_available_sources") as mock_avail, \
         patch.object(fetcher.pool, "fetch") as mock_fetch:

        def route_side_effect(symbol):
            if symbol == "600519.SH":
                return MarketType.A_SHARE, DataSource.AKSHARE
            elif symbol == "AAPL.US":
                return MarketType.US_EQUITY, DataSource.YFINANCE
            return MarketType.A_SHARE, DataSource.AKSHARE

        mock_route.side_effect = route_side_effect
        mock_avail.return_value = {
            DataSource.AKSHARE: True,
            DataSource.YFINANCE: True,
        }
        mock_fetch.return_value = {
            "600519.SH": pd.DataFrame({"close": [100]}),
            "AAPL.US": pd.DataFrame({"close": [150]}),
        }

        results = fetcher.fetch(["600519.SH", "AAPL.US"], "2024-01-01", "2024-01-10")
        assert len(results) == 2
        assert "600519.SH" in results
        assert "AAPL.US" in results
```

**Current shallow translator tests to replace/extend** (lines 449-500):
```python
class TestSymbolTranslatorIntegration:
    """Tests for SymbolTranslator integration in HybridDataFetcher."""

    @pytest.fixture
    def router(self):
        with patch("agent.backtest.loaders.hybrid_fetcher._ensure_registered"):
            return SymbolRouter()

    def test_source_to_vendor_mapping(self, router):
        """Test that SOURCE_TO_VENDOR maps DataSource to DataVendor."""
        from agent.src.data.symbol_translator import DataVendor as SrcVendor

        assert router.SOURCE_TO_VENDOR.get(DataSource.YFINANCE) == SrcVendor.YAHOO_FINANCE
        assert router.SOURCE_TO_VENDOR.get(DataSource.AKSHARE) == SrcVendor.AKSHARE
        assert router.SOURCE_TO_VENDOR.get(DataSource.TUSHARE) == SrcVendor.TUSHARE
        assert router.SOURCE_TO_VENDOR.get(DataSource.TQSDK) == SrcVendor.TQSDK
```

**Implementation guidance:** New tests should assert `mock_fetch.call_args` vendor symbols exactly, e.g. AKShare called with `['sh600519']` but final result contains `600519.SH`. If compatibility fallback accepts canonical return keys, add one test for vendor-key raw return and one for canonical-key raw return during migration.

---

### `agent/tests/test_get_market_data_unresolved.py` (test, unresolved request-response)

**Analog:** `agent/tests/test_get_market_data_unresolved.py`

**Unresolved key convention** (lines 0-8, 62-87):
```python
"""Regression test for P05 — get_market_data must not silently drop a
requested symbol that returned no data.

Pre-fix: the result dict only held winners, so a typo / wrong-suffix /
delisted / no-data code just vanished — indistinguishable from "no data",
and a loader exception lost every already-resolved symbol. Post-fix: any
unresolved requested code is surfaced under the reserved ``_unresolved``
key (additive: omitted entirely when all codes resolve, so the happy-path
payload is byte-identical to before), and a loader blow-up is contained.
"""
```

```python
def test_unresolved_symbol_is_surfaced(good_only):
    out = _call(["GOOD.US", "BOGUS.US"])
    assert "GOOD.US" in out
    assert out.get("_unresolved") == ["BOGUS.US"]


def test_all_resolved_has_no_unresolved_key(good_only):
    """Happy path must stay byte-identical (additive only)."""
    out = _call(["GOOD.US"])
    assert "GOOD.US" in out
    assert "_unresolved" not in out
```

```python
def test_partial_loader_only_missing_codes_unresolved(monkeypatch):
    """G2: a loader returning only SOME requested codes -> the rest land
    under _unresolved (not silently dropped)."""
    monkeypatch.setattr(mcp_server, "_get_loader", lambda src: _PartialLoader)
    out = _call(["OK1.US", "OK2.US", "MISS1.US", "MISS2.US"])
    assert "OK1.US" in out and "OK2.US" in out
    assert sorted(out.get("_unresolved", [])) == ["MISS1.US", "MISS2.US"]
```

**Implementation guidance:** Phase 11 should preserve canonical unresolved symbols. If a vendor symbol fails, report the original canonical symbol as unresolved, never `sh600036`, `AAPL`, or `BTC/USDT`.

---

### `agent/tests/test_registry.py` (test, fallback routing)

**Analog:** `agent/tests/test_registry.py`

**Fallback-chain completeness pattern** (lines 117-129):
```python
class TestFallbackChains:
    def test_all_expected_markets_present(self) -> None:
        expected = {
            "a_share", "us_equity", "hk_equity", "crypto", "futures",
            "cn_futures", "fund", "macro", "forex",
            "us_futures", "us_futures_daily", "us_futures_intraday"
        }
        assert expected == set(FALLBACK_CHAINS.keys())

    def test_chains_are_non_empty(self) -> None:
        for market, chain in FALLBACK_CHAINS.items():
            assert len(chain) > 0, f"Fallback chain for {market} is empty"
```

**Init-error fallback pattern** (lines 212-236):
```python
class TestInitErrorFallback:
    def test_resolve_loader_skips_init_error(self) -> None:
        with patch.dict(LOADER_REGISTRY, {
            "fake_init_error": _FakeInitErrorLoader,
            "fake_available": _FakeAvailableLoader,
        }, clear=True):
            with patch.dict(FALLBACK_CHAINS, {
                "a_share": ["fake_init_error", "fake_available"],
            }):
                with patch("agent.backtest.loaders.registry._wrap_with_cache", side_effect=lambda x, y: x):
                    loader = resolve_loader("a_share")
                    assert loader.name == "fake_available"
```

**Implementation guidance:** If symbol translation happens before fallback, each fallback source must get its own vendor translation. Do not reuse the primary source’s vendor symbol for the fallback source.

## Shared Patterns

### Canonical key preservation

**Sources:** `agent/backtest/loaders/yfinance_loader.py`, `agent/backtest/loaders/tqsdk_loader.py`, `agent/backtest/loaders/futu.py`

**Apply to:** `HybridDataFetcher.fetch()`, direct loaders, new tests

```python
# yfinance_loader.py lines 285-287
symbol_groups: Dict[str, List[str]] = defaultdict(list)
for code in codes:
    symbol_groups[_to_yfinance_symbol(code)].append(code)
```

```python
# yfinance_loader.py lines 319-320
for original_code in symbol_groups[symbol]:
    results[original_code] = normalized.copy()
```

```python
# tqsdk_loader.py lines 354-356, 375
for code in codes:
    tqsdk_code = _to_tqsdk_symbol(code)
    ...
    results[code] = _normalize_frame(df)
```

**Rule:** Vendor symbols are boundary-only. The caller should see canonical symbols in return maps, validation/freshness reports, unresolved lists, cache keys, and run plans.

### Explicit unsupported handling

**Sources:** `agent/src/data/market.py`, `agent/backtest/loaders/registry.py` tests

**Apply to:** `SymbolTranslator` unsupported combinations, future daily scan validation

```python
# market.py lines 90-95
def parse_market(market_str: str) -> Market:
    """解析市场字符串到枚举"""
    key = market_str.lower().strip()
    if key not in MARKET_STR_TO_ENUM:
        raise ValueError(f"Unknown market: {market_str}")
    return MARKET_STR_TO_ENUM[key]
```

**Rule:** Do not silently strip suffixes into plausible but wrong symbols. Unsupported market/vendor combinations should be explicit via a raised `ValueError`, a documented unsupported result, or a clearly named compatibility pass-through if the plan chooses to keep plain-string API compatibility.

### Per-symbol error containment

**Sources:** `akshare_loader.py`, `ccxt_loader.py`, `tqsdk_loader.py`

**Apply to:** loader shims and hybrid fetch translation loop

```python
# akshare_loader.py lines 168-176
result: Dict[str, pd.DataFrame] = {}
for code in codes:
    try:
        df = self._fetch_one(code, start_date, end_date, interval)
        if df is not None and not df.empty:
            result[code] = df
    except Exception as exc:
        logger.debug("akshare failed for %s: %s", code, exc)
return result
```

```python
# ccxt_loader.py lines 96-105
result: Dict[str, pd.DataFrame] = {}
for code in codes:
    try:
        ccxt_symbol = code.replace("-", "/").upper()
        df = self._fetch_one(exchange, ccxt_symbol, timeframe, since_ms, end_ms)
        if df is not None and not df.empty:
            result[code] = df
    except Exception as exc:
        logger.warning("CCXT failed for %s: %s", code, exc)
return result
```

**Rule:** One bad symbol should not drop already-resolved symbols. Tests should prove partial success behavior.

### Mocked provider endpoint tests, no live provider dependency

**Source:** `agent/tests/test_akshare_loader.py`

**Apply to:** `test_symbol_translator_contract.py`, updated loader tests

```python
# test_akshare_loader.py lines 117-128
@pytest.fixture
def fake_akshare(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Install a stub `akshare` module with mocked endpoints."""
    fake = SimpleNamespace(
        fund_etf_hist_sina=MagicMock(return_value=_stub_etf_response()),
        forex_hist_em=MagicMock(return_value=_stub_forex_response()),
        stock_zh_a_daily=MagicMock(return_value=_stub_a_share_response()),
        stock_us_hist=MagicMock(return_value=pd.DataFrame()),
        stock_hk_hist=MagicMock(return_value=pd.DataFrame()),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake)
    return fake
```

**Rule:** Phase 11 required tests must be offline/mocked. Live smoke is optional/manual only.

### Shared market detection source of truth

**Source:** `agent/backtest/engines/_market_hooks.py`

**Apply to:** `runner.py`, hybrid router tests, daily scan planning prerequisites

```python
# _market_hooks.py lines 24-42
_MARKET_PATTERNS = [
    (re.compile(r"^\d{6}\.(SZ|SH|BJ)$", re.I), "a_share"),
    (re.compile(r"^(51|15|56)\d{4}\.(SZ|SH)$", re.I), "a_share"),
    (re.compile(r"^[A-Z]+\.US$", re.I), "us_equity"),
    (re.compile(r"^\d{3,5}\.HK$", re.I), "hk_equity"),
    (re.compile(r"^[A-Z]+-USDT$", re.I), "crypto"),
    (re.compile(r"^[A-Z]+/USDT$", re.I), "crypto"),
```

```python
# _market_hooks.py lines 80-108
def _is_china_futures(code: str) -> bool:
    """Check whether a futures code belongs to a Chinese exchange.
```

**Rule:** If adding or changing canonical examples, update shared tests and avoid duplicating divergent regex tables.

## Conventions to Preserve

1. **Canonical symbols are user-facing.** Never expose vendor symbols in watchlists, backtest configs, output keys, `_unresolved`, quality reports, freshness reports, cache keys, or daily scan plans.
2. **Loader `fetch()` returns input keys.** Direct loader compatibility must remain: callers can pass canonical symbols directly and receive the same symbols back.
3. **Provider tests are mocked.** Do not require yfinance, AKShare, TqSdk, OKX, CCXT, Futu, or Databento live calls for Phase 11 completion.
4. **Use existing `Market` and `DataVendor` enums.** Add enum values only when the implementation needs a new explicit vendor contract.
5. **Keep source-specific fallback behavior.** If primary source fails or returns empty, fallback source must receive its own vendor-format symbols and return canonical keys.
6. **Use logging for new errors/warnings.** Existing modules mix `print` and `logger`, but new code should follow project guidance and existing loader debug/warning patterns.
7. **Keep validation additive.** Existing happy-path output should stay byte-compatible where tests say so; add unsupported/diagnostic behavior without breaking resolved payloads unless a plan explicitly requires it.
8. **No yfinance proxy remediation.** Proxy failures are deferred; Phase 11 only proves translation contract and mocked routing behavior.
9. **No daily scan CLI/run-plan implementation.** Phase 11 only establishes symbol-format prerequisites for Phase 12+.

## No Analog Found

No Phase 11 file lacks a close analog. The new `agent/tests/test_symbol_translator_contract.py` should copy structure from existing parametrized market tests and mocked endpoint routing tests rather than inventing a new test style.

## Metadata

**Analog search scope:**
- `agent/src/data/`
- `agent/backtest/loaders/`
- `agent/backtest/engines/_market_hooks.py`
- `agent/backtest/runner.py`
- `agent/tests/test_market_detection.py`
- `agent/tests/test_hybrid_fetcher.py`
- `agent/tests/test_akshare_loader.py`
- `agent/tests/test_tqsdk_loader.py`
- `agent/tests/test_get_market_data_unresolved.py`
- `agent/tests/test_registry.py`

**Files scanned:** 19
**Pattern extraction date:** 2026-06-08
