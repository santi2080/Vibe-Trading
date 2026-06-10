# Phase 18: Exchange Session Definitions - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Define and extend trading session rules for each market type. Integrate session awareness into the existing freshness detection system.

**Scope:**
- Extend existing `agent/src/data/trading_sessions.py` with timezone-aware session definitions
- Add session-aware freshness detection
- Support A-share, US, HK, and futures markets

**Out of scope:**
- Holiday calendar (Phase 19)
- Real-time data integration
</domain>

<decisions>
## Implementation Decisions

### Existing Code
- Use existing `TradingSession` and `TradingSessions` dataclasses
- Extend `get_trading_sessions()` function for new market codes
- Integrate with existing `DataFreshnessChecker` in `freshness.py`

### Session API
- Add `is_session_time()` method to check if current time is within trading hours
- Add `get_session_status()` returning pre-market/regular/post-market/closed
- Extend `is_fresh()` to accept optional session context

### Timezone Handling
- Use `zoneinfo` (Python 3.9+) for timezone conversion
- Store all times in UTC internally
- Convert to local market time for display

### Configuration
- Hardcoded session definitions (Phase 18)
- Extensible via config file in future phases

</decisions>

<canonical_refs>
## Canonical References

### Existing Code
- `agent/src/data/trading_sessions.py` — existing trading session definitions
- `agent/src/data/freshness.py` — DataFreshnessChecker class
- `agent/src/data/market.py` — Timeframe enum

### Patterns
- Use dataclass pattern consistent with existing codebase
- Extend existing `get_trading_sessions()` function

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TradingSession.contains(time)` — check if time is in session
- `TradingSessions.is_trading_time(time)` — check any session
- Predefined constants: CN_FUTURES, US_STOCK, etc.

### Established Patterns
- Dataclass-based data models
- Module-level constants for market configs
- `get_*()` factory functions

### Integration Points
- `DataFreshnessChecker.is_fresh()` — extend to accept session context
- `symbol_translator.py` — market code from canonical symbol
</code_context>

<specifics>
## Specific Ideas

- Use `zoneinfo.ZoneInfo` for timezone-aware datetime handling
- Add `MarketSession` enum for session states
- Extend existing freshness checker with session awareness
</specifics>

<deferred>
## Deferred Ideas

None — discussion skipped, using standard approaches.

</deferred>

---

*Phase: 18-Exchange Session Definitions*
*Context gathered: 2026-06-11*
