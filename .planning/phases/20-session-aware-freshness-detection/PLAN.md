# Phase 20: Session-Aware Freshness Detection — Plan

**Phase:** 20
**Date:** 2026-06-12
**Depends on:** Phase 19 (Holiday Calendar Integration)
**Requirements:** CAL-03

## Goal

Replace simple staleness checks in `data_refresh.py` with session-aware freshness detection. Data that was updated during the most recent trading session should not be marked stale even if it exceeds the raw age threshold — because the market is closed and there is no opportunity to update it.

---

## Success Criteria

1. `stale_after_for()` returns session-adjusted thresholds (e.g., A-share closed since 15:00 → 1D data from yesterday is fresh, not stale)
2. `get_freshness_report()` returns session-aware status: `fresh` / `stale` / `session_closed` / `holiday`
3. Pre-market / regular-hours / after-hours status distinction works for all supported markets
4. Non-trading-hours data is not marked stale for fixed-hour markets (A-share, US equity)
5. Continuous markets (US futures, crypto) retain original threshold behavior
6. Session-aware freshness report is available in scan results

---

## Tasks

### 20-01: Extend `stale_after_for()` with session-aware thresholds

**File:** `agent/src/data/data_refresh.py`

Replace the fixed `stale_after_for()` with a session-aware version that uses `get_session_status()` from `trading_sessions.py`.

**Changes:**
- In `stale_after_for()`, after computing the base threshold, check `get_session_status(market_code, utc_now)`
- If status is `CLOSED` and `_updated_today_while_closed()` → return base threshold unchanged (data is fresh)
- If status is `CLOSED` and NOT updated today → return base threshold * 1.5 (lenient, market was closed)
- If status is `HOLIDAY` → return base threshold * 2 (holiday, market closed)
- If status is `PRE_MARKET`, `POST_MARKET`, or `CONTINUOUS` → return base threshold unchanged

**Note:** `DataFreshnessChecker.is_fresh()` already has session context logic from Phase 18. This task extends the refresh-layer `stale_after_for()` function used by `data_refresh.py`.

```python
def stale_after_for(
    market: str,
    timeframe: str,
    utc_now: datetime | None = None,
) -> timedelta:
    """Return session-aware staleness threshold for a market/timeframe.

    When market is closed and data was updated during last session, use
    base threshold (data is fresh). When closed with no update today,
    extend threshold by 1.5x. When holiday, extend by 2x.
    """
    from .trading_sessions import get_session_status, MARKET_TZ
    from .holiday_calendar import is_trading_day
    from zoneinfo import ZoneInfo

    utc_now = utc_now or datetime.now(timezone.utc)

    base = _stale_after_for_base(market, timeframe)

    # Get market code for session check (normalize)
    norm_market = market.strip().lower()

    # Check session status
    session_status = get_session_status(norm_market, utc_now)

    if session_status == MarketSessionStatus.HOLIDAY:
        return base * 2
    elif session_status == MarketSessionStatus.CLOSED:
        # Check if data was updated today in market timezone
        tz_name = MARKET_TZ.get(norm_market)
        if tz_name:
            market_tz = ZoneInfo(tz_name)
            market_now = utc_now.astimezone(market_tz)
            market_date = market_now.date()
            # Check last market open date — implemented in 20-02
            if _updated_on_date(norm_market, timeframe, market_date):
                return base  # updated today, base threshold
            return base * 1.5  # closed, not updated today
        return base * 1.5
    else:
        return base  # pre-market, regular, post-market, continuous
```

**Tests:**
- [ ] A-share closed, data from yesterday → threshold * 1.5
- [ ] A-share closed, data from today → threshold unchanged
- [ ] US equity closed, holiday → threshold * 2
- [ ] US futures (continuous) → threshold unchanged regardless of time
- [ ] Unknown market → base threshold unchanged

---

### 20-02: Add `_updated_on_date()` helper

**File:** `agent/src/data/data_refresh.py`

A helper that checks whether a parquet file was updated on a given market-local date. This enables the session-aware threshold logic in 20-01.

```python
def _updated_on_date(
    market: str,
    timeframe: str,
    market_date: date,
    data_dir: Path | None = None,
) -> bool:
    """Return True if the parquet for market/timeframe was last-updated on market_date.

    Checks the latest timestamp in the parquet index against the market-local date.
    Returns False if the parquet doesn't exist or can't be read.
    """
    if data_dir is None:
        from agent.src.data.watchlist_data_health import DEFAULT_DATA_DIR
        data_dir = Path(DEFAULT_DATA_DIR)

    cache_path = _resolve_cache_file(data_dir, market, "*", timeframe)
    if not cache_path.exists():
        # Try glob to find any matching file
        matches = list(cache_path.parent.glob(cache_path.name.replace("*", "*")))
        if not matches:
            return False
        cache_path = matches[0]

    try:
        df, _ = read_local_parquet(cache_path)
        if df is None or df.empty:
            return False
        latest_ts = pd.Timestamp(df.index.max())
        tz_name = MARKET_TZ.get(market.strip().lower())
        if tz_name:
            latest_date = latest_ts.tz_convert(tz_name).date()
            return latest_date == market_date
        return latest_ts.date() == market_date
    except Exception:
        return False
```

**Tests:**
- [ ] Returns True when parquet last updated today (market timezone)
- [ ] Returns False when parquet last updated yesterday
- [ ] Returns False when parquet doesn't exist

---

### 20-03: Extend `DataFreshnessChecker` with session-aware status methods

**File:** `agent/src/data/freshness.py`

Add `get_session_aware_status()` that returns richer status including session context.

**Changes:**
- Add `get_session_aware_status()` method that combines session status + freshness age
- Add `get_freshness_report()` dataclass with fields: `status`, `age_hours`, `session_status`, `threshold_hours`, `freshness_reason`

```python
@dataclass
class FreshnessReport:
    """Full session-aware freshness report."""
    status: str          # "fresh" | "stale" | "very_stale" | "session_closed" | "holiday"
    age_hours: float
    session_status: str   # MarketSessionStatus.value
    threshold_hours: float
    freshness_reason: str # Human-readable reason for the status
    last_update: datetime
    check_time: datetime


def get_session_aware_report(
    last_update: datetime,
    timeframe: Timeframe,
    market_code: str,
    now: datetime | None = None,
) -> FreshnessReport:
    """Return a full session-aware freshness report."""
```

**Tests:**
- [ ] A-share after-hours → status="session_closed", freshness_reason mentions market close
- [ ] A-share during trading → status="fresh"/"stale" based on threshold
- [ ] US equity holiday → status="holiday"
- [ ] US futures continuous → status based on raw threshold only

---

### 20-04: Add focused tests for session-aware freshness

**File:** `agent/src/data/test_freshness.py` (new)

```python
# Coverage for all Phase 20 success criteria
class TestSessionAwareFreshness:
    """Tests for session-aware staleness detection (CAL-03)."""

    # 20-01: stale_after_for session adjustment
    def test_ashare_closed_extends_threshold(self): ...
    def test_ushare_closed_with_today_data_base_threshold(self): ...
    def test_us_equity_holiday_extends_threshold(self): ...
    def test_us_futures_continuous_unchanged_threshold(self): ...

    # 20-02: _updated_on_date helper
    def test_updated_today_returns_true(self): ...
    def test_updated_today_returns_false_for_yesterday(self): ...
    def test_updated_today_returns_false_missing_file(self): ...

    # 20-03: get_session_aware_report
    def test_ashare_afterhours_session_closed(self): ...
    def test_ushare_during_trading_regular_freshness(self): ...
    def test_us_equity_holiday_status(self): ...
    def test_us_futures_continuous_ignores_session(self): ...
```

**Run command:** `pytest agent/src/data/test_freshness.py -x -q`

---

### 20-05: Update `__init__.py` exports

**File:** `agent/src/data/__init__.py`

Add `FreshnessReport`, `get_session_aware_report()` to exports.

---

### 20-06: Update ROADMAP progress

**File:** `.planning/ROADMAP.md`

Mark Phase 20 plan complete (1/1 plans).

---

## Files Modified

| File | Change |
|------|--------|
| `agent/src/data/data_refresh.py` | 20-01, 20-02: session-aware `stale_after_for()` |
| `agent/src/data/freshness.py` | 20-03: `get_session_aware_report()`, `FreshnessReport` dataclass |
| `agent/src/data/test_freshness.py` | 20-04: new focused tests |
| `agent/src/data/__init__.py` | 20-05: new exports |
| `.planning/ROADMAP.md` | 20-06: update progress |

---

## Dependency Chain

```
20-02 helper
    ↓
20-01 stale_after_for  ──→ (uses 20-02 helper)
    ↓
20-03 FreshnessReport  ──→ (uses get_session_status from Phase 18)
    ↓
20-04 tests
    ↓
20-05 exports
    ↓
20-06 ROADMAP
```

---

## Verification

After each task:
```bash
pytest agent/src/data/ -x -q
```

Phase gate:
```bash
pytest agent/src/data/test_freshness.py -x -q
pytest agent/src/data/test_trading_sessions.py -x -q
pytest agent/src/data/test_holiday_calendar.py -x -q
```

All must pass before closing Phase 20.

---

## Assumptions

| # | Assumption | Risk |
|---|-----------|------|
| A1 | `last_update` in parquet files is timezone-aware UTC | Low — pandas stores UTC timestamps by convention |
| A2 | `stale_after_for()` is the only staleness threshold function used by the refresh layer | Medium — verify no other callers need updating |
| A3 | US futures treated as continuous (24/7) — no session-aware adjustment | Low — CME futures trade nearly 24/7 |
