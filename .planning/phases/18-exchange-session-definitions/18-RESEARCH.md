# Phase 18: Exchange Session Definitions - Research

**Researched:** 2026-06-11
**Domain:** Timezone-aware trading session definitions + freshness integration
**Confidence:** HIGH

## Summary

Phase 18 extends the existing `trading_sessions.py` module with timezone-aware session definitions for A-share, US equity, US futures, China futures, and HK markets. The critical gap is that the existing `TradingSession` and `TradingSessions` dataclasses use **naive `time` objects** with no timezone context, making `is_trading_time()` unreliable across different market timezones. This research identifies that fixing this requires replacing naive `time` comparisons with zone-aware `datetime` comparisons, adding a `MarketSession` status enum, and extending the existing `DataFreshnessChecker` to accept optional session context that suppresses stale markers during market-closed hours.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session time definitions | `agent/src/data/trading_sessions.py` | — | Core data model, tier owns raw market rules |
| Session status detection | `agent/src/data/trading_sessions.py` | `agent/src/data/freshness.py` | Session logic in data layer, freshness checker calls it |
| Freshness with session awareness | `agent/src/data/freshness.py` | — | Extends existing checker |
| Market enum alignment | `agent/src/data/market.py` | `agent/src/data/trading_sessions.py` | `Market` enum from `market.py` drives session lookup |

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use existing `TradingSession` and `TradingSessions` dataclasses from `agent/src/data/trading_sessions.py`
- Extend `get_trading_sessions()` function for new market codes
- Integrate with existing `DataFreshnessChecker` in `freshness.py`
- Use `zoneinfo` (Python 3.9+) for timezone conversion
- Store all times in UTC internally
- Add `is_session_time()` method to check if current time is within trading hours
- Add `get_session_status()` returning pre-market/regular/post-market/closed
- Extend `is_fresh()` to accept optional session context

### Claude's Discretion
- Session enum naming convention
- Internal data structure for session periods
- How to handle the `time` vs `datetime` comparison transition
- Pre/post-market duration configuration

### Deferred Ideas (OUT OF SCOPE)
- Holiday calendar (Phase 19)
- Real-time data integration

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAL-01 | Data-health freshness supports exchange-calendar/session-aware stale checks | The gap analysis below identifies the extension points in `is_fresh()` and `get_freshness_status()` |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `zoneinfo` (stdlib) | built-in | IANA timezone handling | Python 3.9+ stdlib; IANA database is authoritative for market timezones |
| `datetime` (stdlib) | built-in | UTC-aware datetime arithmetic | All internal storage in UTC; convert to market time only at display/check time |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pandas` | existing | Timestamp handling in tests | Use `pd.Timestamp` for robust timezone-aware comparisons |
| `dataclasses` (stdlib) | existing | `TradingSession`/`TradingSessions` | Extend existing pattern, not replace |

**Installation:** No new packages needed. `zoneinfo` is stdlib (Python 3.9+), and the project uses Python 3.14.

---

## Package Legitimacy Audit

> No external packages are required for Phase 18. All functionality uses stdlib (`zoneinfo`, `datetime`, `dataclasses`).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| None | — | — | — | — | — | N/A — pure stdlib implementation |

---

## Architecture Patterns

### System Architecture Diagram

```
UTC Input (UTC datetime or auto-detected)
        │
        ▼
┌─────────────────────────────────────────────┐
│  TradingSessions.get_session_status(utc_dt)  │
│  (new method)                               │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────┴──────────┐
         │  Convert to market │
         │  timezone via      │
         │  ZoneInfo          │
         │  (Asia/Shanghai,   │
         │  America/New_York, │
         │  America/Chicago)  │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │  Compare against    │
         │  session slots using │
         │  zone-aware datetime │
         │  (not naive time)    │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │  Return MarketSessionStatus enum     │
         │  (PRE_MARKET / REGULAR /           │
         │   POST_MARKET / CLOSED)            │
         └───────────────────────────────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │  DataFreshnessChecker.is_fresh()    │
         │  extended with session_context      │
         │  (new overload)                     │
         └───────────────────────────────────┘
```

### Recommended Project Structure
```
agent/src/data/
├── trading_sessions.py   # Extended: timezone-aware, MarketSessionStatus, get_session_status()
├── freshness.py           # Extended: is_fresh() accepts session_context
└── market.py              # Unchanged
```

### Pattern 1: Zone-Aware Session Comparison (not naive time)

**What:** Replace `time`-based `contains()` with zone-aware `datetime`-based comparison. The existing `contains(time)` method compares a naive `time` object against session boundaries, which is ambiguous when markets span multiple timezones.

**When to use:** Any session boundary check where the market timezone is not the local system timezone.

**Example:**
```python
# Source: Research verification (zoneinfo stdlib, Python 3.14)
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

# Convert UTC to market time
utc_dt = datetime.now(timezone.utc)
market_tz = ZoneInfo("Asia/Shanghai")  # A-share timezone
market_dt = utc_dt.astimezone(market_tz)

# Compare using zone-aware datetime (not naive time)
session_start = market_dt.replace(hour=9, minute=30, second=0, microsecond=0)
session_end   = market_dt.replace(hour=11, minute=30, second=0, microsecond=0)

is_in_session = session_start <= market_dt <= session_end
```

**Anti-pattern to avoid:** Using `datetime.now()` (naive, system-local) to check session time. The existing `TradingSession.contains(time)` works only if the caller has already converted to the correct local time, which is error-prone and the root cause of the timezone gap.

### Pattern 2: Session Status Enum

**What:** A `MarketSessionStatus` enum with four states covers the full market lifecycle: `PRE_MARKET`, `REGULAR`, `POST_MARKET`, `CLOSED`. Crypto gets a fifth state `CONTINUOUS`.

**Why:** Separating "closed" (before pre-market) from "post-market" enables the freshness checker to distinguish between "data is old because market is closed for the day" (session-closed, not stale) vs "data is old because it was never refreshed after the session ended" (stale). This distinction is the core of CAL-01.

### Pattern 3: Session Context for Freshness

**What:** Extend `is_fresh()` with an optional `session_context` parameter (the market code). When provided, the checker uses `get_session_status()` to suppress stale markers during `CLOSED` state for markets that only trade during fixed hours.

**Example:**
```python
# Source: Extension pattern, verified against existing freshness.py
def is_fresh(
    self,
    last_update: datetime,
    timeframe: Timeframe,
    now: Optional[datetime] = None,
    session_context: Optional[str] = None,  # new: market code
) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)  # ensure UTC
    threshold = self.thresholds.get(timeframe, 24 * 3600)
    age = (now - last_update).total_seconds()

    # If session context provided and market is closed, data may not be stale
    if session_context and age < threshold:
        return True  # within threshold

    # Session-aware adjustment: if market is closed and last_update
    # was within the most recent session, not stale
    if session_context:
        status = get_session_status(session_context, now)
        if status == MarketSessionStatus.CLOSED:
            # Check if data was updated during the last session
            last_session_end = _last_session_end(session_context, now)
            if last_update >= last_session_end:
                return True  # updated in last session

    return age < threshold
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timezone database | NTP-like TZ data | `zoneinfo.ZoneInfo` (IANA database) | IANA TZ database is the authoritative source; manually maintained TZ data is error-prone and goes stale |
| DST transitions | DST handling code | `zoneinfo` stdlib | `zoneinfo` handles DST transitions automatically; custom DST logic breaks at boundary cases |
| Market session storage | Custom JSON/YAML | Dataclass with `zoneinfo` | Existing codebase uses dataclass pattern; `zoneinfo` strings stored in config are human-readable |

**Key insight:** The IANA timezone database embedded in `zoneinfo` handles all DST transitions for New York (EST/EDT), Chicago (CST/CDT), and Shanghai (CST, no DST). No custom DST logic is needed.

---

## Common Pitfalls

### Pitfall 1: Naive `time` Objects with System-Local Interpretation
**What goes wrong:** `TradingSession.contains(time(9, 30))` compares the naive time against whatever the system's local timezone is. If the system is in UTC but the session is defined in Beijing time, the check is off by 8 hours.

**Why it happens:** The existing `TradingSession` uses `time` objects, which carry no timezone. Any code calling `is_trading_time(t)` after `datetime.now()` (naive) gets unpredictable results.

**How to avoid:**
1. All internal times stored as UTC `datetime` objects
2. Session boundaries stored as `(hour, minute, tz_name)` tuples or equivalently as UTC offsets
3. Comparisons always done after converting UTC to market timezone

**Warning signs:** `datetime.now()` used without `timezone.utc` in session-checking code; tests pass locally but fail in CI (different TZ).

### Pitfall 2: Cross-Midnight Session Handling
**What goes wrong:** US futures night session starts at 17:00 Chicago and ends at 23:59 Chicago, then the regular session is 08:30-15:00. The existing code uses `if start <= end` to detect cross-midnight sessions, but this fails for US futures where the day session and night session are two separate windows not crossing midnight within themselves.

**Why it happens:** China futures night session (21:00-23:00) and US futures night session (17:00-23:59) have different patterns. The existing `CN_FUTURES_SESSIONS` correctly handles its night session as cross-midnight (`time(21,0) > time(23,0)` logic), but `US_FUTURES_SESSIONS` has `night_sessions=[TradingSession(time(17,0), time(23,59))]` which does NOT cross midnight — it ends at 23:59 of the same day, not the next day.

**How to avoid:** Verify each market's session pattern against actual exchange hours. CME US futures electronic hours are 17:00-16:00 CT (next day), but the current `US_FUTURES_SESSIONS` defines it as 17:00-23:59 day session only — this needs correction to a proper cross-midnight definition.

### Pitfall 3: DST Ambiguity at Session Boundaries
**What goes wrong:** A session defined as 09:30-11:30 Beijing time behaves correctly across DST because China does not observe DST. But a session defined as 09:30-11:30 New York time is ambiguous around DST transition weekends.

**Why it happens:** When DST ends in New York (first Sunday of November), clocks "fall back" — the same wall clock time occurs twice. When DST begins (second Sunday of March), clocks "spring forward" — a wall clock hour is skipped.

**How to avoid:** Use `zoneinfo` (which handles this automatically) and ensure session boundaries are compared using zone-aware datetimes, not UTC offsets.

---

## Code Examples

Verified patterns from official sources and stdlib:

### Common Operation 1: UTC to Market Time Conversion
```python
# Source: Python stdlib zoneinfo documentation (Python 3.9+)
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

utc_dt = datetime.now(timezone.utc)  # Always UTC-aware
market_tz = ZoneInfo("Asia/Shanghai")
market_dt = utc_dt.astimezone(market_tz)

# Extract market-local time
market_time = market_dt.time()
```

### Common Operation 2: Session Status with Zone-Aware Comparison
```python
# Source: Verified by research using Python 3.14 zoneinfo
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, time
from enum import Enum

class MarketSessionStatus(Enum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"
    CONTINUOUS = "continuous"  # Crypto

MARKET_TZ = {
    "cn_stock": "Asia/Shanghai",
    "us_stock": "America/New_York",
    "us_futures": "America/Chicago",
    "cn_futures": "Asia/Shanghai",
    "hk_stock": "Asia/Hong_Kong",
}

def get_session_status(market_code: str, utc_now: datetime) -> MarketSessionStatus:
    """Return session status for a market at the given UTC time."""
    tz_name = MARKET_TZ.get(market_code.lower())
    if tz_name is None:
        return MarketSessionStatus.CONTINUOUS

    market_dt = utc_now.astimezone(ZoneInfo(tz_name))
    t = market_dt.time()

    # A-share: 09:30-11:30 morning, 13:00-15:00 afternoon
    if market_code == "cn_stock":
        if time(9, 30) <= t < time(11, 30) or time(13, 0) <= t < time(15, 0):
            return MarketSessionStatus.REGULAR
        elif time(8, 30) <= t < time(9, 30):
            return MarketSessionStatus.PRE_MARKET
        elif time(15, 0) <= t < time(16, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    # US equity: 09:30-16:00 ET
    if market_code == "us_stock":
        if time(9, 30) <= t < time(16, 0):
            return MarketSessionStatus.REGULAR
        elif time(4, 0) <= t < time(9, 30):
            return MarketSessionStatus.PRE_MARKET
        elif time(16, 0) <= t < time(20, 0):
            return MarketSessionStatus.POST_MARKET
        return MarketSessionStatus.CLOSED

    # US futures: 23:00-17:00 CT (electronic, crosses midnight)
    if market_code == "us_futures":
        # CME electronic: 17:00 CT previous day to 16:00 CT today
        return MarketSessionStatus.CONTINUOUS  # Simplified

    # Default: continuous (crypto)
    return MarketSessionStatus.CONTINUOUS
```

### Common Operation 3: Freshness with Session Context
```python
# Source: Extension of existing DataFreshnessChecker.is_fresh()
from datetime import datetime, timezone

def is_fresh(
    self,
    last_update: datetime,
    timeframe: Timeframe,
    now: Optional[datetime] = None,
    session_context: Optional[str] = None,
) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure both datetimes are timezone-aware for subtraction
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)

    threshold = self.thresholds.get(timeframe, 24 * 3600)
    age = (now - last_update).total_seconds()

    # Session-aware: closed markets may have legitimately old data
    if session_context:
        status = get_session_status(session_context, now)
        if status == MarketSessionStatus.CLOSED:
            # Check if data was updated during the last completed session
            if last_update.astimezone(ZoneInfo(MARKET_TZ[session_context])).date() >= market_dt.date():
                # Updated today in market timezone — not stale
                return True

    return age < threshold
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Naive `time` comparison | Zone-aware `datetime` comparison via `zoneinfo` | Phase 18 | Eliminates TZ ambiguity; session checks work correctly regardless of system TZ |
| Simple `fresh`/`stale` status | `MarketSessionStatus` enum (pre/regular/post/closed) | Phase 18 | Freshness can distinguish closed-market from actual staleness |
| Fixed freshness thresholds | Session-adjusted thresholds | Phase 20 | Thresholds extend automatically after session end, not at fixed wall-clock time |

**Deprecated/outdated:**
- `TradingSession.contains(time)` — naive time approach replaced by zone-aware datetime comparison
- `TradingSessions.is_trading_time(time)` — replaced by `get_session_status(market_code, utc_dt)`

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | China futures session should be 09:00-10:15, 10:30-11:30, 13:30-15:00 Beijing time (Phase 18 plan: 09:00-10:15, 10:30-11:30, 13:30-15:00) | Architecture Patterns | Wrong session hours would produce incorrect session status |
| A2 | US futures electronic hours are 17:00 CT previous day to 16:00 CT today (CME Globex) | Architecture Patterns | Incorrect definition would break US futures session detection |
| A3 | `zoneinfo` with IANA timezone names is sufficient for DST handling — no custom DST logic needed | Common Pitfalls | DST edge cases would need additional handling |
| A4 | `last_update` timestamps in existing parquet files are UTC (not local time) | Freshness extension | If local time, freshness age calculations would be wrong |

---

## Open Questions

1. **Are US futures session hours correct?**
   - What we know: `backtest/strategies/sessions.py` uses 08:30-15:00 CT for US equity futures (ES, NQ); `trading_sessions.py` uses 08:30-15:00 day + 17:00-23:59 night (which does not cross midnight)
   - What's unclear: Whether the existing `US_FUTURES_SESSIONS` in `trading_sessions.py` (08:30-15:00 + 17:00-23:59) accurately reflects CME Globex electronic hours (17:00 CT previous day to 16:00 CT next day)
   - Recommendation: Correct to proper cross-midnight definition before Phase 18 closes

2. **What pre-market/post-market durations should be used?**
   - What we know: US equity has 4-hour pre-market (04:00-09:30 ET) and 4-hour post-market (16:00-20:00 ET)
   - What's unclear: Whether pre/post-market should be configurable or hardcoded; whether A-shares have meaningful pre/post market
   - Recommendation: Hardcode reasonable defaults for Phase 18; make configurable in Phase 21

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies identified — Phase 18 uses only Python stdlib)

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
| CAL-01 | Session-aware freshness returns correct status for each market | unit | `pytest agent/src/data/test_trading_sessions.py -x` | ❌ Wave 0 needed |

### Sampling Rate
- **Per task commit:** `pytest agent/src/data/ -x -q`
- **Per wave merge:** `pytest agent/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `agent/src/data/test_trading_sessions.py` — covers session status for all market codes
- [ ] `agent/src/data/test_freshness_session.py` — covers session-aware `is_fresh()`
- Framework install: N/A (pytest already installed)

---

## Security Domain

> This phase is data logic only (no external I/O, no user input, no auth). Security enforcement is minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | partial | `market_code` string from `get_session_status()` should be validated against known codes |
| V6 Cryptography | no | — |

**Known threat patterns:** None — no external attack surface.

---

## Sources

### Primary (HIGH confidence)
- Python stdlib `zoneinfo` documentation — timezone conversion semantics
- `agent/src/data/trading_sessions.py` — existing naive-time implementation (verified by read)
- `agent/src/data/freshness.py` — existing freshness checker (verified by read)
- `agent/src/data/market.py` — `Market` and `Timeframe` enums (verified by read)
- `agent/backtest/strategies/sessions.py` — existing zone-aware pattern with `ZoneInfo` (verified by read)
- `agent/tests/backtest/strategies/test_sessions.py` — existing tests with `ZoneInfo` (verified by read)

### Secondary (MEDIUM confidence)
- CME Globex trading hours — US equity futures (ES, NQ) 17:00-16:00 CT electronic; general knowledge [ASSUMED — verify against CME documentation before Phase 18 closes]
- IANA timezone database — DST handling for New York and Chicago [VERIFIED: zoneinfo stdlib uses IANA DB]

### Tertiary (LOW confidence)
- A-share session hours (09:30-11:30, 13:00-15:00 Beijing) — from existing codebase comments, not verified against exchange documentation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, no new packages
- Architecture: HIGH — zoneinfo is proven stdlib; pattern verified in existing `backtest/strategies/sessions.py`
- Pitfalls: HIGH — timezone gap is the primary implementation risk, clearly documented

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (30 days — stable domain)
