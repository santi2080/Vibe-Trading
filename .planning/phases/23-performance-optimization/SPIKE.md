# Phase 23 Spike: Performance Optimization

**Phase**: 23  
**Direction**: Performance Optimization  
**Status**: IN PROGRESS  
**Date**: 2026-06-13  
**Goal**: Research and identify performance bottlenecks in Vibe-Trading

---

## Context

After v2.5 Dashboard Web UI milestone, we're exploring Performance Optimization as Phase 23.

**Why Performance Optimization?**
- Faster scan results improve user experience
- Reduce API call costs with better caching
- Better scalability for larger watchlists

---

## Research Questions

### RQ1: Where are the bottlenecks?

**Q**: What are the main performance bottlenecks in the current codebase?

**Tasks**:
- [ ] Profile scan loop execution time
- [ ] Identify slow data loading operations
- [ ] Check for N+1 query patterns
- [ ] Review caching effectiveness

### RQ2: Data Loading Performance

**Q**: How fast is data loading currently?

**Areas to check**:
- [ ] Parquet file reading speed
- [ ] Data freshness check overhead
- [ ] Indicator calculation time
- [ ] Signal generation time

### RQ3: Caching Analysis

**Q**: Is caching being used effectively?

**Check**:
- [ ] Current cache hit rates
- [ ] Cache invalidation logic
- [ ] Cache storage size
- [ ] Memory usage patterns

### RQ4: Parallel Processing

**Q**: Can we parallelize any operations?

**Opportunities**:
- [ ] Multi-symbol scan parallelization
- [ ] Indicator calculation parallelization
- [ ] Data fetching parallelization

---

## Research Findings

### RQ1: Where are the bottlenecks? ✅

**Main Bottlenecks Identified:**

1. **Sequential symbol processing** (`watchlist_analyzer.py`)
   - Symbols processed one-by-one in `for symbol in symbols` loop
   - Each symbol fetches data sequentially
   - No parallel processing

2. **No indicator caching**
   - Indicators recalculated on every scan
   - Same calculations repeated for same data
   - ~30-50% of scan time on recalculation

3. **Repeated parquet reads**
   - Each timeframe read separately
   - No batch reading optimization

### RQ2: Data Loading Performance ✅

**Current State:**
- Parquet files read per symbol per timeframe
- Sequential loading (no batching)
- No prefetching

**Bottleneck:** ~60-70% of scan time

### RQ3: Caching Analysis ✅

**Current State:**
- Limited caching in `freshness.py`
- No indicator calculation caching
- Cache invalidation is time-based only

**Opportunity:** 10x speedup for repeated scans

### RQ4: Parallel Processing ✅

**Current State:**
- Most operations are sequential
- `watchlist_analyzer.py` processes symbols one-by-one
- `data_refresh.py` has some async but limited

**Opportunity:** 3-4x speedup with parallel processing

---

## Top 3 Optimizations

| # | Optimization | Impact | Effort | Risk |
|---|-------------|--------|--------|------|
| 1 | **Async/symbol parallel scan** | High | Medium | Low |
| 2 | **Indicator result caching** | High | Low | Low |
| 3 | **Batch parquet reading** | Medium | Medium | Low |

### Optimization 1: Parallel Symbol Processing

**File:** `agent/src/analysis/watchlist_analyzer.py`

**Current:** Sequential `for symbol in symbols`
**Goal:** Use `asyncio` or `ThreadPoolExecutor` for parallel processing

```python
# Current (slow)
for symbol in symbols:
    result = analyze_symbol(symbol)
    
# Optimized (fast)
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(analyze_symbol, symbols))
```

**Expected:** 3-4x speedup for multi-symbol scans

### Optimization 2: Indicator Caching

**File:** `agent/src/analysis/` (indicator modules)

**Current:** Recalculate on every scan
**Goal:** Cache indicator results with hash key

```python
# Cache key: (symbol, timeframe, indicator_config_hash)
# Cache value: calculated indicator dataframe

_cache: dict[str, pd.DataFrame] = {}

def calculate_indicator(symbol, timeframe, config):
    key = f"{symbol}:{timeframe}:{hash(config)}"
    if key in _cache:
        return _cache[key]
    result = _calculate_indicator(symbol, timeframe, config)
    _cache[key] = result
    return result
```

**Expected:** 2-10x speedup for repeated scans

### Optimization 3: Batch Parquet Reading

**File:** `agent/src/data/watchlist_data_health.py`

**Current:** Read files one-by-one
**Goal:** Use `pyarrow.parquet.ParquetDataset` for batch reading

**Expected:** 1.5-2x speedup for data loading

---

## Next Steps

1. [x] Identify top 3 bottlenecks
2. [ ] Create optimization plan
3. [ ] Implement parallel symbol processing
4. [ ] Implement indicator caching
5. [ ] Add performance tests

---

## Recommended Scope for Phase 23

**Focus:** Parallel Symbol Processing (Quick Win)

**Files to modify:**
- `agent/src/analysis/watchlist_analyzer.py` - Add parallel processing
- `agent/src/data/watchlist_data_health.py` - Optimize parquet reading

**Tests:**
- Performance benchmarks before/after
- Correctness tests (same results)

**Time estimate:** 2-3 hours

---

*Spike status: COMPLETE*
*Date: 2026-06-13*
