---
phase: 19
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/src/data/holiday_calendar.py
  - agent/src/data/trading_sessions.py
  - agent/src/data/freshness.py
autonomous: true
requirements:
  - CAL-02
must_haves:
  truths:
    - "is_trading_day() returns True/False/None for cn_stock, us_stock, hk_stock dates"
    - "MarketSessionStatus.HOLIDAY exists and is used when market is closed for holiday"
    - "DataFreshnessChecker suppresses false staleness on known exchange holidays"
  artifacts:
    - path: agent/src/data/holiday_calendar.py
      provides: is_trading_day() function, holiday calendar wrappers
      exports: is_trading_day, is_holiday
    - path: agent/src/data/trading_sessions.py
      provides: HOLIDAY status in MarketSessionStatus
      exports: MarketSessionStatus.HOLIDAY
    - path: agent/src/data/freshness.py
      provides: holiday-aware freshness check
      exports: DataFreshnessChecker (updated)
    - path: agent/src/data/test_holiday_calendar.py
      provides: Unit tests for holiday calendar
      min_lines: 80
  key_links:
    - from: agent/src/data/trading_sessions.py
      to: agent/src/data/holiday_calendar.py
      via: is_trading_day import
      pattern: "from.*holiday_calendar import.*is_trading_day"
---

<objective>
Add holiday calendar awareness using the `holidays` library, integrate with Phase 18 session system, and extend freshness checker to suppress false staleness on known exchange holidays.
</objective>

<context>
@agent/src/data/trading_sessions.py
@agent/src/data/freshness.py
@agent/src/data/market.py

The Phase 18 research has established:
- `MARKET_TZ` maps market codes to timezone names
- `MarketSessionStatus` enum has PRE_MARKET, REGULAR, POST_MARKET, CLOSED, CONTINUOUS
- `get_session_status()` returns session status for a given UTC datetime
- DataFreshnessChecker.is_fresh() accepts optional session_context parameter

Phase 19 extends this by:
- Adding `MarketSessionStatus.HOLIDAY` for confirmed exchange holidays
- Creating `is_trading_day()` using `holidays.financial` calendars
- Suppressing stale warnings when market is closed for a known holiday
</context>

<tasks>

<task type="checkpoint" name="Task 0: Verify holidays library availability">
<action>
Before installing, verify the holidays library is accessible:

1. Check if holidays is already installed:
```bash
cd /Users/iagent/projects/vibe-trading && .venv/bin/pip show holidays
```

2. If not installed, install with version constraint:
```bash
cd /Users/iagent/projects/vibe-trading && .venv/bin/pip install 'holidays>=0.98'
```

3. Verify installation:
```bash
cd /Users/iagent/projects/vibe-trading && .venv/bin/python -c "from holidays.financial.ny_stock_exchange import NewYorkStockExchange; print('holidays OK')"
```
</action>
<verify>
<automated>cd /Users/iagent/projects/vibe-trading && .venv/bin/python -c "
import pkg_resources
try:
    ver = pkg_resources.get_distribution('holidays').version
    print(f'holidays {ver} already installed')
except pkg_resources.DistributionNotFound:
    print('NOT INSTALLED')
"</automated>
</verify>
<done>holidays>=0.98 available in .venv</done>
</task>

<task type="auto">
<name>Task 1: Create holiday_calendar.py with is_trading_day()</name>
<files>agent/src/data/holiday_calendar.py</files>
<action>
Create `agent/src/data/holiday_calendar.py` with thin wrappers over `holidays.financial`:

1. **Imports**:
```python
"""Holiday calendar for exchange trading days."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    pass

# Import holiday calendars lazily to avoid import-time overhead
_holiday_calendars: dict[str, object] = {}

# Map market codes to timezone names (shares with trading_sessions.py MARKET_TZ)
_MARKET_TZ: dict[str, str] = {
    "us_stock": "America/New_York",
    "us_stocks": "America/New_York",
    "cn_stock": "Asia/Shanghai",
    "cn_stocks": "Asia/Shanghai",
    "hk_stock": "Asia/Hong_Kong",
    "hk_stocks": "Asia/Hong_Kong",
}


def _get_calendar(market_code: str):
    """Lazily create and cache holiday calendar instances."""
    code = market_code.lower()
    if code in _holiday_calendars:
        return _holiday_calendars[code]

    # Import calendar classes
    try:
        from holidays.financial.ny_stock_exchange import NewYorkStockExchange
        from holidays.financial.shanghai_stock_exchange import ShanghaiStockExchange
        from holidays.financial.hong_kong_stock_exchange import HongKongStockExchange
    except ImportError:
        return None

    if code in ("us_stock", "us_stocks"):
        cal = NewYorkStockExchange()
    elif code in ("cn_stock", "cn_stocks"):
        cal = ShanghaiStockExchange()
    elif code in ("hk_stock", "hk_stocks"):
        cal = HongKongStockExchange()
    else:
        return None

    _holiday_calendars[code] = cal
    return cal


def is_trading_day(market_code: str, dt_or_date) -> Optional[bool]:
    """Return True if trading day, False if holiday, None if unknown market.

    Args:
        market_code: Market identifier (e.g., 'cn_stock', 'us_stock', 'hk_stock')
        dt_or_date: datetime or date object to check

    Returns:
        True if trading day, False if holiday, None if market not supported.
        Note: Half-day trading (e.g., NYSE Christmas Eve) returns True (still a trading day).
    """
    code = market_code.lower()

    # Get market timezone
    tz_name = _MARKET_TZ.get(code)
    if tz_name is None:
        return None  # Unknown market

    # Extract market-local date (critical — prevents UTC midnight date shift)
    if isinstance(dt_or_date, datetime):
        market_local_date = dt_or_date.astimezone(ZoneInfo(tz_name)).date()
    elif isinstance(dt_or_date, date):
        market_local_date = dt_or_date
    else:
        return None

    # Get or create calendar
    cal = _get_calendar(code)
    if cal is None:
        return None

    # Check if this is a holiday
    # holiday_name() returns None if not a holiday, string name if holiday
    holiday_name = cal.holiday_name(market_local_date)
    return holiday_name is None  # None = not a holiday = trading day


def is_holiday(market_code: str, dt_or_date) -> Optional[bool]:
    """Return True if market is closed for a holiday on the given date.

    Args:
        market_code: Market identifier (e.g., 'cn_stock', 'us_stock')
        dt_or_date: datetime or date object to check

    Returns:
        True if holiday, False if trading day, None if unknown market.
    """
    trading = is_trading_day(market_code, dt_or_date)
    if trading is None:
        return None
    return not trading


def get_holiday_name(market_code: str, dt_or_date) -> Optional[str]:
    """Return the name of the holiday if the date is a holiday.

    Args:
        market_code: Market identifier
        dt_or_date: datetime or date object to check

    Returns:
        Holiday name string if holiday, None if trading day or unknown market.
    """
    code = market_code.lower()
    tz_name = _MARKET_TZ.get(code)
    if tz_name is None:
        return None

    if isinstance(dt_or_date, datetime):
        market_local_date = dt_or_date.astimezone(ZoneInfo(tz_name)).date()
    elif isinstance(dt_or_date, date):
        market_local_date = dt_or_date
    else:
        return None

    cal = _get_calendar(code)
    if cal is None:
        return None

    return cal.holiday_name(market_local_date)
</action>
<verify>
<automated>cd /Users/iagent/projects/vibe-trading && .venv/bin/python -c "
from agent.src.data.holiday_calendar import is_trading_day, is_holiday, get_holiday_name
from datetime import date, datetime
from zoneinfo import ZoneInfo

# Test 1: CNY 2026 (January 29, 2026) - holiday
d = date(2026, 1, 29)
result = is_trading_day('cn_stock', d)
print(f'CNY 2026-01-29 is_trading_day: {result} (expect False)')
assert result == False, f'Expected False, got {result}'

# Test 2: Normal trading day (June 11, 2026)
d2 = date(2026, 6, 11)
result2 = is_trading_day('us_stock', d2)
print(f'US stock 2026-06-11 is_trading_day: {result2}')
assert result2 in (True, False), f'Expected True/False, got {result2}'

# Test 3: Unknown market returns None
result3 = is_trading_day('crypto', date(2026, 6, 11))
print(f'crypto is_trading_day: {result3} (expect None)')
assert result3 is None, f'Expected None, got {result3}'

# Test 4: is_holiday is inverse of is_trading_day
h = is_holiday('cn_stock', d)
t = is_trading_day('cn_stock', d)
assert h == (not t), f'is_holiday/is_trading_day mismatch: {h} vs {t}'
print(f'is_holiday CNY: {h}, is_trading_day: {t}')

# Test 5: get_holiday_name on known holiday
name = get_holiday_name('cn_stock', d)
print(f'CNY holiday name: {name}')
assert name is not None, 'Expected holiday name for CNY 2026'

print('All holiday_calendar checks passed')
"</automated>
</verify>
<done>holiday_calendar.py created with is_trading_day(), is_holiday(), get_holiday_name()</done>
</task>

<task type="auto">
<name>Task 2: Add HOLIDAY to MarketSessionStatus</name>
<files>agent/src/data/trading_sessions.py</files>
<action>
Extend `agent/src/data/trading_sessions.py`:

1. **Add HOLIDAY to MarketSessionStatus enum** (after CONTINUOUS):
```python
    HOLIDAY = "holiday"  # Market is closed for an exchange holiday
```

2. **Update get_session_status() function** to check holidays first:
At the beginning of get_session_status(), after getting market_tz but before checking session windows:

```python
# Phase 19: Check if it's a market holiday (before session windows)
from .holiday_calendar import is_trading_day
market_date = market_dt.date()
trading = is_trading_day(code, market_date)
if trading is False:
    return MarketSessionStatus.HOLIDAY
```

Insert this check right after `market_dt = utc_dt.astimezone(ZoneInfo(tz_name))` and before the session time window checks.

3. **Keep all existing code intact** — only add the holiday check, do not modify any existing session window logic.
</action>
<verify>
<automated>cd /Users/iagent/projects/vibe-trading && .venv/bin/python -c "
from agent.src.data.trading_sessions import MarketSessionStatus, get_session_status
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo

# Test 1: MarketSessionStatus has HOLIDAY
assert hasattr(MarketSessionStatus, 'HOLIDAY'), 'HOLIDAY missing from MarketSessionStatus'
print(f'MarketSessionStatus.HOLIDAY: {MarketSessionStatus.HOLIDAY.value}')

# Test 2: CNY 2026 returns HOLIDAY status
# CNY 2026: Jan 29, 2026 - Shanghai timezone
cn_tz = ZoneInfo('Asia/Shanghai')
cn_dt = datetime(2026, 1, 29, 10, 0, 0, tzinfo=timezone.utc)  # 18:00 CST Jan 29
status = get_session_status('cn_stock', cn_dt)
print(f'CNY 2026-01-29 18:00 CST session status: {status.value}')
assert status == MarketSessionStatus.HOLIDAY, f'Expected HOLIDAY, got {status}'

# Test 3: Normal day returns session status (not HOLIDAY)
us_tz = ZoneInfo('America/New_York')
us_dt = datetime(2026, 6, 11, 14, 30, 0, tzinfo=timezone.utc)  # 10:30 AM ET - regular hours
status2 = get_session_status('us_stock', us_dt)
print(f'US 2026-06-11 10:30 AM ET session status: {status2.value}')
assert status2 != MarketSessionStatus.HOLIDAY, f'Normal day should not be HOLIDAY, got {status2}'

print('All MarketSessionStatus.HOLIDAY checks passed')
"</automated>
</verify>
<done>MarketSessionStatus.HOLIDAY added, get_session_status() returns HOLIDAY on known exchange holidays</done>
</task>

<task type="auto">
<name>Task 3: Extend freshness.py with holiday awareness</name>
<files>agent/src/data/freshness.py</files>
<action>
Extend `agent/src/data/freshness.py` to handle holidays:

1. **Update get_freshness_status()** to return "holiday" for confirmed holidays:
In the session_context block, after checking for CLOSED session:

```python
# In the session_context block of get_freshness_status():
if status == MarketSessionStatus.HOLIDAY:
    return "holiday"  # Market closed for holiday, not stale

if status == MarketSessionStatus.CLOSED:
    # ... existing closed-session logic ...
```

2. **Keep is_fresh() behavior unchanged** — holiday-aware freshness is already handled by the session status check in Phase 18's implementation. When get_session_status() returns HOLIDAY, the freshness checker can suppress staleness appropriately. No change to is_fresh() logic is needed beyond the updated get_session_status() call.

3. **Add optional holiday_context parameter** to get_freshness_status() that explicitly checks holiday calendar (optional, session_context already covers it via updated get_session_status).

Read the existing freshness.py first to find the exact insertion points.
</action>
<verify>
<automated>cd /Users/iagent/projects/vibe-trading && .venv/bin/python -c "
from agent.src.data.freshness import DataFreshnessChecker
from agent.src.data.market import Timeframe
from datetime import datetime, timezone, timedelta

checker = DataFreshnessChecker()

# Test: get_freshness_status returns 'holiday' for holiday dates
# CNY 2026 Jan 29
from zoneinfo import ZoneInfo
cn_tz = ZoneInfo('Asia/Shanghai')
cn_dt = datetime(2026, 1, 29, 10, 0, 0, tzinfo=timezone.utc)  # Market is closed for CNY
last_update = datetime(2026, 1, 28, 15, 0, 0, tzinfo=timezone.utc)  # Updated day before

status = checker.get_freshness_status(last_update, Timeframe.H1, cn_dt, session_context='cn_stock')
print(f'Freshness status on CNY holiday: {status}')
assert status == 'holiday', f'Expected holiday, got {status}'

# Test: is_fresh on holiday - should suppress staleness
is_fresh = checker.is_fresh(last_update, Timeframe.H1, cn_dt, session_context='cn_stock')
print(f'is_fresh on CNY holiday: {is_fresh}')

print('Holiday-aware freshness checks passed')
"</automated>
</verify>
<done>get_freshness_status() returns 'holiday' on known exchange holidays</done>
</task>

<task type="auto">
<name>Task 4: Create test file for holiday calendar</name>
<files>agent/src/data/test_holiday_calendar.py</files>
<action>
Create `agent/src/data/test_holiday_calendar.py` with comprehensive tests:

1. **Test is_trading_day()**:
   - CNY 2026 (Jan 29): returns False
   - Normal weekday: returns True (or False on weekend)
   - US Thanksgiving 2026: returns False (fourth Thursday of November)
   - US Christmas 2026: returns False
   - HK Chinese New Year 2026: returns False
   - Unknown market (crypto): returns None

2. **Test is_holiday()**:
   - Inverse of is_trading_day for known markets
   - Returns None for unknown markets

3. **Test get_holiday_name()**:
   - Returns holiday name string on holiday dates
   - Returns None on trading days

4. **Test MarketSessionStatus.HOLIDAY**:
   - CNY 2026 date returns HOLIDAY from get_session_status()
   - Regular trading day does NOT return HOLIDAY

5. **Test freshness on holidays**:
   - get_freshness_status() returns 'holiday' for holiday dates
   - is_fresh() suppresses staleness on known holidays

6. **Test datetime input**:
   - is_trading_day accepts datetime objects (not just date)
   - UTC midnight date shift is handled correctly

7. **Test calendar caching**:
   - Multiple calls don't recreate calendars

Use parameterized tests for multiple known holidays.
</action>
<verify>
<automated>cd /Users/iagent/projects/vibe-trading && .venv/bin/pytest agent/src/data/test_holiday_calendar.py -x -v --tb=short 2>&1 | head -80</automated>
</verify>
<done>test_holiday_calendar.py created with 15+ test cases covering all markets and holiday scenarios</done>
</task>

<task type="auto">
<name>Task 5: Update __init__.py exports</name>
<files>agent/src/data/__init__.py</files>
<action>
Update `agent/src/data/__init__.py` to export new holiday calendar APIs:

Add to the existing exports:
```python
from .holiday_calendar import is_trading_day, is_holiday, get_holiday_name
```
</action>
<verify>
<automated>cd /Users/iagent/projects/vibe-trading && .venv/bin/python -c "
from agent.src.data import is_trading_day, is_holiday, get_holiday_name
from datetime import date
print('Holiday calendar exports OK')
result = is_trading_day('cn_stock', date(2026, 1, 29))
print(f'is_trading_day(cn_stock, 2026-01-29) = {result}')
"</automated>
</verify>
<done>holiday calendar APIs exported from agent.src.data package</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client code -> is_trading_day | market_code string only selects from known codes; date/datetime is validated |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-19-01 | Denial of Service | holidays library init | accept | library is well-maintained; calendar caching prevents repeated init |
| T-19-02 | Information | holiday data accuracy | mitigate | library is authoritative for NYSE/SSE/HKEX; tested against known holidays |
| T-19-03 | Tampering | date parameter | mitigate | coerce to date type before passing to holidays; type checking in place |

No external I/O beyond package install.
</threat_model>

<verification>
## Phase Verification

```bash
# Quick: Holiday calendar tests only
cd /Users/iagent/projects/vibe-trading && .venv/bin/pytest agent/src/data/test_holiday_calendar.py -x -q

# Session integration: holiday status in trading sessions
cd /Users/iagent/projects/vibe-trading && .venv/bin/pytest agent/src/data/test_trading_sessions.py -x -q

# Full: All data layer tests
cd /Users/iagent/projects/vibe-trading && .venv/bin/pytest agent/src/data/ -x -q
```
</verification>

<success_criteria>
1. is_trading_day() returns False on CNY 2026, US Thanksgiving 2026, and other confirmed holidays
2. is_trading_day() returns True on normal trading days
3. is_trading_day() returns None for unknown markets (crypto, forex)
4. MarketSessionStatus.HOLIDAY exists and is returned by get_session_status() on holiday dates
5. DataFreshnessChecker.get_freshness_status() returns 'holiday' on known exchange holidays
6. DataFreshnessChecker.is_fresh() suppresses staleness warnings on known holidays
7. All 15+ test cases pass covering all markets and holiday scenarios
</success_criteria>

<output>
Create `.planning/phases/19-holiday-calendar-integration/19-01-SUMMARY.md` when done
</output>
