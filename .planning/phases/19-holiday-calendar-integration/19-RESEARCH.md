# Phase 19: Holiday Calendar Integration - Research

**Researched:** 2026-06-11
**Domain:** Exchange holiday calendar detection for A-share, US equity, and HK markets
**Confidence:** HIGH

## Summary

Phase 19 adds holiday calendar awareness to the exchange session system from Phase 18. The key insight is that the `holidays` library (Vacanza) provides purpose-built financial market calendars for NYSE, Shanghai Stock Exchange, and HKEX out of the box, including proper handling of Chinese lunar calendar holidays (Spring Festival, Dragon Boat, Mid-Autumn, Qingming) and NYSE half-day rules. Integration is a thin wrapper layer over these calendars, not a custom implementation. The `is_trading_day()` function should return `False` on exchange holidays, and the existing `get_session_status()` from Phase 18 should be extended to return a `HOLIDAY` state so the `DataFreshnessChecker` can suppress false-stale warnings on known holidays.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Holiday data source | `holidays` library (financial modules) | — | NYSE/SSE/HKEX calendars already built; lunar date calculation is hard |
| Holiday awareness | `agent/src/data/trading_sessions.py` | — | Natural home; shares `MARKET_TZ` and `MarketSessionStatus` with Phase 18 |
| Freshness integration | `agent/src/data/freshness.py` | — | Suppress stale warnings on known exchange holidays |
| Market enum alignment | `agent/src/data/market.py` | — | Unchanged; holiday calendar keyed by `market_code` string |

---

## User Constraints (from CONTEXT.md)

*No CONTEXT.md found for Phase 19. This section is empty — using standard approaches.*

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAL-02 | Holiday lookup returns whether a date is a trading day | `is_trading_day()` function using `holidays` library; covers CN, US, HK markets |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `holidays` | 0.98 | Exchange holiday calendars | Industry-standard Python holiday library; has dedicated financial market calendars for NYSE, SSE, HKEX with lunar date support |
| `datetime` (stdlib) | built-in | Date handling | All date comparisons |
| `zoneinfo` (stdlib) | built-in | Timezone-aware date extraction | Same as Phase 18; market dates extracted in market TZ |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pandas` | existing | Date range generation in tests | Use `pd.date_range()` for holiday range tests |
| `dataclasses` (stdlib) | existing | Data model patterns | Consistent with Phase 18 codebase |

**Installation:**
```bash
pip install holidays>=0.98
```

---

## Package Legitimacy Audit

> slopcheck was not available at research time; `holidays` is tagged `[ASSUMED]` and the planner must gate install behind `checkpoint:human-verify`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `holidays` | PyPI | ~9 yrs (since 2015) | ~4M/wk [ASSUMED] | github.com/vacanza/holidays | not run | Flagged — planner inserts `checkpoint:human-verify`; library has clean audit trail (MIT, Vacanza team, published 2025-06) |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

*If slopcheck was unavailable at research time, all packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

---

## Architecture Patterns

### System Architecture Diagram

```
User / Checker calls is_trading_day(market_code, date)
                          │
                          ▼
          ┌─────────────────────────────────┐
          │  holiday_calendar.py              │
          │  (new module — thin wrapper)     │
          │                                   │
          │  NYSE: NewYorkStockExchange()     │ ← holidays.financial.ny_stock_exchange
          │  SSE:  ShanghaiStockExchange()    │ ← holidays.financial.shanghai_stock_exchange
          │  HKEX: HongKongStockExchange()   │ ← holidays.financial.hong_kong_stock_exchange
          └──────────────────┬────────────────┘
                             │
                             ▼
          ┌─────────────────────────────────┐
          │  is_trading_day(market, date)   │
          │  returns: True / False / None   │
          └──────────────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────────┐  ┌──────────────┐
        │ get_     │  │ freshness.py  │  │ trading_     │
        │ session  │  │ DataFreshness│  │ sessions.py   │
        │ _status()│  │ Checker      │  │ is_session   │
        │          │  │ integration  │  │ _time()      │
        └──────────┘  └──────────────┘  └──────────────┘
```

### Recommended Project Structure
```
agent/src/data/
├── trading_sessions.py    # Extended: is_holiday(), is_trading_day(), HOLIDAY status
├── holiday_calendar.py     # NEW: thin wrappers over holidays.financial
├── freshness.py            # Extended: holiday-aware freshness check
└── market.py              # Unchanged
```

### Pattern 1: Thin Wrapper Over `holidays.financial`

**What:** Rather than hardcoding holidays or building a custom lunar calendar, wrap the purpose-built `holidays.financial` market calendars. These classes handle:
- Chinese lunar calendar holidays (Spring Festival, Dragon Boat, Mid-Autumn, Qingming) via `ChineseCalendarHolidays` mixin
- NYSE half-day rules (Independence Day, Christmas Eve, day after Thanksgiving) via `HALF_DAY` category
- Observed rules (weekend bridging) per market
- Historical data back to 2001 (SSE), 1863 (NYSE), 2014 (HKEX)

**When to use:** For any market with an established exchange holiday calendar.

**Example:**
```python
# Source: holidays library financial module inspection (v0.98, 2025-06)
from holidays.financial.ny_stock_exchange import NewYorkStockExchange
from holidays.financial.shanghai_stock_exchange import ShanghaiStockExchange
from holidays.financial.hong_kong_stock_exchange import HongKongStockExchange

nyse = NewYorkStockExchange(years=range(2020, 2027))
sse = ShanghaiStockExchange(years=range(2020, 2027))
hkex = HongKongStockExchange(years=range(2020, 2027))

# Check a specific date
from datetime import date
nyse_holidays = nyse.get_named(date(2026, 1, 1))  # New Year's Day
sse_holidays = sse.get_named(date(2026, 1, 29))   # Chinese New Year (lunar)
print(nyse.holiday_name(date(2026, 1, 1)))        # "New Year's Day"
print(sse.holiday_name(date(2026, 1, 29)))         # "春节" (Spring Festival)

# Half-day check (NYSE)
nyse_half = NewYorkStockExchange(years=[2026], categories=["HALF_DAY"])
print(nyse_half.holiday_name(date(2026, 7, 3)))   # "Independence Day (observed)" — half day
```

### Pattern 2: Holiday-Aware Session Status

**What:** Extend `get_session_status()` from Phase 18 to check `is_trading_day()` first. If a date is a confirmed holiday, return `MarketSessionStatus.HOLIDAY` before checking session time windows.

**Why:** Prevents the freshness checker from flagging data as stale on known exchange holidays when no trading data is expected.

**Example:**
```python
# Source: Phase 18 integration pattern
from .trading_sessions import MARKET_TZ, MarketSessionStatus, get_session_status
from .holiday_calendar import is_trading_day

def get_session_status_holiday_aware(
    market_code: str, utc_dt: Optional[datetime] = None
) -> MarketSessionStatus:
    """Return session status, accounting for holidays."""
    code = market_code.lower()
    utc_dt = _ensure_utc(utc_dt)
    market_tz = ZoneInfo(MARKET_TZ.get(code, "UTC"))
    market_date = utc_dt.astimezone(market_tz).date()

    # Check holiday first — holidays take precedence over session windows
    trading = is_trading_day(code, market_date)
    if trading is False:
        return MarketSessionStatus.HOLIDAY
    if trading is None:
        # Unknown market — fall back to session-only logic
        pass

    # Fall through to Phase 18 session status logic
    return get_session_status(code, utc_dt)
```

### Pattern 3: Market Code to Calendar Mapping

**What:** Map project `market_code` strings to `holidays` calendar classes. This is the single point of integration.

**Why:** Isolates the third-party dependency; if the holidays library changes or is replaced, only this mapping changes.

**Example:**
```python
# Source: Pattern from existing codebase (MARKET_TZ mapping in trading_sessions.py)
from holidays.financial.ny_stock_exchange import NewYorkStockExchange
from holidays.financial.shanghai_stock_exchange import ShanghaiStockExchange
from holidays.financial.hong_kong_stock_exchange import HongKongStockExchange

_holiday_calendars: dict[str, object] = {}

def _get_calendar(market_code: str):
    """Lazily create and cache holiday calendar instances."""
    code = market_code.lower()
    if code not in _holiday_calendars:
        if code in ("us_stock", "us_stocks"):
            _holiday_calendars[code] = NewYorkStockExchange()
        elif code in ("cn_stock", "cn_stocks"):
            _holiday_calendars[code] = ShanghaiStockExchange()
        elif code in ("hk_stock", "hk_stocks"):
            _holiday_calendars[code] = HongKongStockExchange()
        else:
            return None
        # Pre-populate for current and next year
        import datetime as dt
        _holiday_calendars[code].years = set(range(2020, dt.date.today().year + 2))
    return _holiday_calendars[code]
```

### Anti-Patterns to Avoid

- **Hand-rolling lunar calendar calculations:** Chinese holidays (Spring Festival, Dragon Boat, Mid-Autumn) follow the lunar calendar and require astronomical data. The `holidays` library uses `ChineseCalendarHolidays` with pre-computed dates. Do not implement custom lunar conversions.
- **Hardcoding individual holiday dates:** Holiday schedules change (e.g., CNY bridging, observed rules). Use the library's observed-rule engine.
- **Ignoring half-day rules:** NYSE has early close (13:00 ET) on Independence Day observed and Christmas Eve. Use the `HALF_DAY` category for partial-day awareness.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chinese lunar holidays | Custom lunar-to-solar conversion | `holidays.financial.shanghai_stock_exchange` | Lunar calendar requires astronomical calculations; library has verified data back to 2001 |
| NYSE half-day rules | Hardcoded early-close dates | `NewYorkStockExchange(categories=["HALF_DAY"])` | Library encodes historical half-day rules |
| HKEX lunar holidays | Custom HKEX holiday list | `HongKongStockExchange` | HKEX bridges lunar holidays to adjacent weekdays |
| Yearly holiday updates | Static annual data | Library auto-generates from rules | Holiday rules are formulaic (4th Thu Nov = Thanksgiving); library handles formula |

**Key insight:** The `holidays` library is the authoritative source for these calendars. The Vacanza team maintains them with references to official exchange websites and publishes annual updates.

---

## Common Pitfalls

### Pitfall 1: Calendar Not Pre-populated for Requested Year
**What goes wrong:** `holidays` calendar only contains holidays for the years specified at instantiation. Calling `.holiday_name(date(2027, 1, 1))` returns `None` if the calendar was created with `years=range(2020, 2027)`.

**Why it happens:** The `holidays` library generates holidays lazily by year. It does not auto-expand.

**How to avoid:** Lazily extend the calendar's `years` set when a date outside the known range is requested. Or pre-populate with `range(current_year - 2, current_year + 3)`.

**Warning signs:** `holiday_name(date)` returns `None` on known holidays (e.g., CNY 2027), then silently wrong behavior.

### Pitfall 2: Mixing Market Holidays with Public Holidays
**What goes wrong:** Using `holidays.country_holidays('CN')` for A-share calendar — this includes national holidays that are NOT exchange holidays. The SSE has its own special rules (weekend makeup work days, SSE-specific extended holidays) that differ from national holidays.

**Why it happens:** `holidays.country_holidays('CN')` is for general public holidays, not financial markets. The `ShanghaiStockExchange` class is specifically for the exchange.

**How to avoid:** Always use `holidays.financial.shanghai_stock_exchange.ShanghaiStockExchange`, not `holidays.country_holidays('CN')`.

### Pitfall 3: UTC Date vs Market-Local Date for Holiday Check
**What goes wrong:** Converting a UTC midnight timestamp (00:00 UTC) to market date can shift the date for markets west of UTC. Example: `2026-01-30 00:00 UTC` is `2026-01-29` in New York (EST, UTC-5).

**Why it happens:** `holidays` library checks `datetime.date` objects. UTC midnight may not correspond to the market's local date.

**How to avoid:** Always extract the market-local date using `ZoneInfo` before passing to `holidays`:
```python
utc_dt.astimezone(ZoneInfo(MARKET_TZ[market_code])).date()  # Use this
```

### Pitfall 4: `is_trading_day` Returning None for Unknown Markets
**What goes wrong:** Unknown markets (e.g., crypto) return `None`, which is falsy but ambiguous — does `None` mean "unknown" or "not a trading day"?

**Why it happens:** The holiday calendar only covers cn_stock, us_stock, hk_stock. Other markets (crypto, forex) have no holiday concept.

**How to avoid:** Return `None` explicitly for unknown markets, and have callers handle `None` explicitly. Do not conflate "unknown" with "not a trading day."

---

## Code Examples

Verified patterns from holidays library inspection (v0.98, 2025-06):

### Common Operation 1: Check if a Date is a Market Holiday
```python
# Source: holidays library financial module, verified by whl inspection
from datetime import date
from holidays.financial.shanghai_stock_exchange import ShanghaiStockExchange

sse = ShanghaiStockExchange(years=range(2020, 2028))
d = date(2026, 1, 29)  # CNY 2026
holiday_name = sse.holiday_name(d)
is_holiday = holiday_name is not None
# holiday_name: "春节" (Spring Festival)
# is_holiday: True
```

### Common Operation 2: Check Trading Day with Market-Local Date
```python
# Source: Phase 18 integration pattern; market TZ from existing MARKET_TZ
from datetime import datetime, date
from zoneinfo import ZoneInfo

def is_trading_day(market_code: str, dt_or_date) -> bool | None:
    """Return True if trading day, False if holiday, None if unknown market."""
    from holidays.financial.ny_stock_exchange import NewYorkStockExchange
    from holidays.financial.shanghai_stock_exchange import ShanghaiStockExchange
    from holidays.financial.hong_kong_stock_exchange import HongKongStockExchange

    code = market_code.lower()
    calendar_map = {
        "us_stock": NewYorkStockExchange,
        "us_stocks": NewYorkStockExchange,
        "cn_stock": ShanghaiStockExchange,
        "cn_stocks": ShanghaiStockExchange,
        "hk_stock": HongKongStockExchange,
        "hk_stocks": HongKongStockExchange,
    }
    Cal = calendar_map.get(code)
    if Cal is None:
        return None  # Unknown market

    # Ensure we have the year covered
    check_date = dt_or_date.date() if hasattr(dt_or_date, "date") else dt_or_date
    cal = Cal(years=range(check_date.year - 1, check_date.year + 2))

    # Extract market-local date (critical — prevents UTC midnight shift)
    tz_map = {"us_stock": "America/New_York", "cn_stock": "Asia/Shanghai", "hk_stock": "Asia/Hong_Kong"}
    market_tz = ZoneInfo(tz_map[code])
    if hasattr(dt_or_date, "astimezone"):
        market_local_date = dt_or_date.astimezone(market_tz).date()
    else:
        market_local_date = check_date

    return cal.holiday_name(market_local_date) is None  # None = not a holiday = trading day
```

### Common Operation 3: Half-Day Holiday Check (NYSE)
```python
# Source: holidays library HALF_DAY category inspection
from datetime import date
from holidays.financial.ny_stock_exchange import NewYorkStockExchange

# Full calendar
nyse = NewYorkStockExchange(years=[2026])
print(nyse.holiday_name(date(2026, 7, 3)))    # "Independence Day (observed)" — full holiday

# Half-day calendar
nyse_half = NewYorkStockExchange(years=[2026], categories=["HALF_DAY"])
print(nyse_half.holiday_name(date(2026, 7, 3)))  # "Independence Day (observed)" — half day flag
print(nyse_half.holiday_name(date(2026, 12, 24))) # "Christmas Eve" — half day
```

### Common Operation 4: Extend `get_session_status` with Holiday Check
```python
# Source: Integration of Phase 18 get_session_status with Phase 19 holiday calendar
def get_session_status(
    market_code: str, utc_dt: Optional[datetime] = None
) -> MarketSessionStatus:
    code = market_code.lower()
    utc_dt = _ensure_utc(utc_dt)
    tz_name = MARKET_TZ.get(code)
    if tz_name is None:
        return MarketSessionStatus.CONTINUOUS  # Crypto/forex: continuous

    market_dt = utc_dt.astimezone(ZoneInfo(tz_name))
    market_date = market_dt.date()

    # Phase 19: Check if it's a market holiday
    from .holiday_calendar import is_trading_day
    trading = is_trading_day(code, market_date)
    if trading is False:
        return MarketSessionStatus.HOLIDAY  # New state: market is closed for holiday

    # Phase 18: Existing session time logic
    # ... (rest of Phase 18 get_session_status implementation)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No holiday awareness | `holidays` library financial modules | Phase 19 | Correctly identifies non-trading days; freshness checker knows market is closed, not stale |
| Hardcoded holiday lists | Lunar calendar + observed rules via library | Phase 19 | CNY/Dragon Boat/Mid-Autumn auto-calculated; no annual hardcoding |
| Session-closed = stale | Holiday/closed distinction | Phase 19 | Freshness checker suppresses false stale warnings on known exchange holidays |

**Deprecated/outdated:**
- Hardcoded holiday date lists — replaced by `holidays.financial` library
- Public holiday calendars for exchange trading day checks — replaced by market-specific financial calendars

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `holidays>=0.98` install is safe and stable (MIT license, Vacanza team, PyPI) | Package Legitimacy | Wrong library could produce incorrect holiday data |
| A2 | NYSE partial-day (half-day) check via `categories=["HALF_DAY"]` works as expected | Code Examples | Would need different API for partial-day detection |
| A3 | HKEX half-day handling (Chinese New Year's Eve, Christmas Eve, New Year's Eve) is covered | Architecture Patterns | Missing half-day data would not affect v1 holiday calendar scope |
| A4 | `holidays` library supports Python 3.14 (the project's Python version) | Standard Stack | If not compatible, would need alternative library |
| A5 | Freshness checker should suppress stale warnings on known exchange holidays | Common Pitfalls | This is a design choice; user may prefer explicit warnings |

---

## Open Questions

1. **Should partial-day (half-day) trading be represented as a distinct status?**
   - What we know: NYSE has early close on Independence Day observed (13:00 ET) and Christmas Eve (14:00 ET). The `holidays` library's `HALF_DAY` category exposes these.
   - What's unclear: Whether `MarketSessionStatus.HALF_DAY` should be a distinct state, or whether half-day awareness belongs only in the trading sessions (Phase 18) not the holiday calendar (Phase 19).
   - Recommendation: For Phase 19, treat half-day as still a trading day (return `True` from `is_trading_day()`). Add `MarketSessionStatus.HALF_DAY` only if Phase 18 session logic is extended to handle partial sessions.

2. **How far back should historical holiday data be pre-populated?**
   - What we know: The library generates holidays by year lazily. Backtesting may need historical data.
   - What's unclear: What is the minimum year to support for backtesting (e.g., 2020 for 5-year backtest)?
   - Recommendation: Default to `range(current_year - 5, current_year + 2)` for Phase 19. Make it configurable in Phase 20.

3. **Should CN futures (China futures) have a separate holiday calendar from A-shares?**
   - What we know: China futures (CN_FUTURES) and A-shares (CN_STOCK) share the same exchange holidays (Shanghai Stock Exchange). CME US futures have their own schedule.
   - What's unclear: Whether CN_FUTURES should use the same `ShanghaiStockExchange` calendar or a different one.
   - Recommendation: Use the same `ShanghaiStockExchange` for CN_FUTURES in Phase 19; add CME-specific calendar if needed in a future phase.

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies identified at research time — `holidays` is the primary addition)

---

## Validation Architecture

> Configuration: `workflow.nyquist_validation` is not explicitly set in `.planning/config.json`, so section is included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pytest.ini` (existing) |
| Quick run command | `pytest agent/src/data/ -x -q` |
| Full suite command | `pytest agent/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAL-02 | `is_trading_day()` returns correct values for CNY, National Day, Thanksgiving, Christmas | unit | `pytest agent/src/data/test_holiday_calendar.py -x` | `❌ Wave 0 needed` |

### Sampling Rate
- **Per task commit:** `pytest agent/src/data/ -x -q`
- **Per wave merge:** `pytest agent/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `agent/src/data/test_holiday_calendar.py` — covers `is_trading_day()` for CN, US, HK markets
- [ ] `agent/src/data/test_holiday_calendar.py` — covers `MarketSessionStatus.HOLIDAY` in `get_session_status`
- [ ] Framework install: `pip install holidays>=0.98` (add to setup if not in pyproject.toml)

---

## Security Domain

> This phase is data logic only (no external I/O, no user input, no auth). Security enforcement is minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | partial | `market_code` string should be validated against known codes; `date` input should be coerced to `date` type |
| V6 Cryptography | no | — |

**Known threat patterns:** None — no external attack surface.

---

## Sources

### Primary (HIGH confidence)
- `holidays` library v0.98 (2025-06) — financial market calendars inspected from whl; NYSE, SSE, HKEX confirmed
- `agent/src/data/trading_sessions.py` — Phase 18 implementation (verified by read)
- `agent/src/data/freshness.py` — Phase 18 freshness checker (verified by read)
- `agent/src/data/market.py` — Phase 11 market enum (verified by read)

### Secondary (MEDIUM confidence)
- `holidays` GitHub (github.com/vacanza/holidays) — project stats, maintenance status [ASSUMED from whl inspection; not verified via web]
- Lunar calendar date accuracy for China holidays [ASSUMED from library design; library is industry-standard]
- NYSE half-day close times (13:00 ET / 14:00 ET) [ASSUMED from library constants; not independently verified]

### Tertiary (LOW confidence)
- CN futures holiday calendar differs from A-share [ASSUMED; not verified against CME documentation]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `holidays` library verified by whl inspection; financial modules confirmed present
- Architecture: HIGH — thin wrapper pattern is low-risk; shares existing Phase 18 code patterns
- Pitfalls: HIGH — calendar not pre-populated is the primary risk; clearly documented

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (30 days — stable domain, library version confirmed)
