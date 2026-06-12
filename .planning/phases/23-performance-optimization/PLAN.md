# Phase 23: Performance Optimization

**目标**: 提升扫描循环性能 - 并行处理 + 缓存  
**优先级**: P1  
**基于 Spike**: `SPIKE.md`  
**预计工时**: 2-3 小时  
**版本**: v1.0

---

## 📋 概述

### 当前瓶颈
1. **顺序符号处理** - watchlist_analyzer.py 中符号逐一处理
2. **指标重复计算** - 无缓存，每次扫描重新计算
3. **Parquet 逐个读取** - 无批量读取优化

### 优化目标
- 并行符号处理：3-4x 加速
- 指标缓存：2-10x 加速（重复扫描）
- 批量读取：1.5-2x 加速

---

## 🎯 目标

1. **并行符号处理** - 使用 ThreadPoolExecutor 并行分析符号
2. **指标结果缓存** - 基于哈希键缓存指标计算结果
3. **批量 Parquet 读取** - 优化数据加载

---

## 📊 实施计划

### Task 1: 并行符号处理

**文件**: `agent/src/analysis/watchlist_analyzer.py`

**修改**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加并行处理方法
def analyze_symbols_parallel(
    self,
    symbols: List[str],
    max_workers: int = 4
) -> List[AnalysisResult]:
    """并行分析符号列表"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(self.analyze_symbol, symbol): symbol
            for symbol in symbols
        }
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                symbol = futures[future]
                results.append(AnalysisResult(symbol=symbol, error=str(e)))
        return results
```

### Task 2: 指标结果缓存

**文件**: `agent/src/analysis/indicator_cache.py` (新建)

**功能**:
```python
import hashlib
import json
from functools import lru_cache
from typing import Optional

class IndicatorCache:
    """指标计算结果缓存"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, pd.DataFrame] = {}
        self._max_size = max_size
    
    def _make_key(
        self,
        symbol: str,
        timeframe: str,
        indicator_type: str,
        params: dict
    ) -> str:
        """生成缓存键"""
        key_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "type": indicator_type,
            "params": params
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, symbol, timeframe, indicator_type, params) -> Optional[pd.DataFrame]:
        key = self._make_key(symbol, timeframe, indicator_type, params)
        return self._cache.get(key)
    
    def set(self, symbol, timeframe, indicator_type, params, df: pd.DataFrame):
        key = self._make_key(symbol, timeframe, indicator_type, params)
        if len(self._cache) >= self._max_size:
            # LRU: 删除最早的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = df
    
    def clear(self):
        self._cache.clear()
    
    def stats(self) -> dict:
        return {"size": len(self._cache), "max_size": self._max_size}
```

### Task 3: 批量 Parquet 读取优化

**文件**: `agent/src/data/watchlist_data_health.py`

**修改**:
```python
import pyarrow.parquet as pq

def read_parquet_batch(file_paths: List[Path]) -> Dict[str, pd.DataFrame]:
    """批量读取多个 Parquet 文件"""
    results = {}
    for path in file_paths:
        if path.exists():
            # 使用 pyarrow 批量读取
            table = pq.read_table(path)
            results[path.stem] = table.to_pandas()
    return results
```

### Task 4: 性能基准测试

**文件**: `agent/tests/test_performance.py` (新建)

**测试用例**:
- [ ] 顺序处理基准时间
- [ ] 并行处理基准时间
- [ ] 缓存命中率
- [ ] 批量读取 vs 逐个读取

---

## 📁 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/src/analysis/watchlist_analyzer.py` | 修改 | 添加并行处理方法 |
| `agent/src/analysis/indicator_cache.py` | 新建 | 指标缓存类 |
| `agent/src/data/watchlist_data_health.py` | 修改 | 添加批量读取函数 |
| `agent/tests/test_performance.py` | 新建 | 性能基准测试 |

---

## ✅ 验收标准

### 功能验收
- [ ] 并行处理结果与顺序处理一致
- [ ] 缓存正确存储和检索指标
- [ ] 批量读取返回正确数据

### 性能验收
- [ ] 并行处理比顺序处理快 2x 以上
- [ ] 缓存命中率 > 50%（重复扫描）
- [ ] 批量读取比逐个读取快 1.5x 以上

### 测试验收
- [ ] 性能基准测试通过
- [ ] 回归测试全部通过

---

## 📝 更新日志

| 日期 | 描述 |
|------|------|
| 2026-06-13 | 创建计划 v1.0 |

---

**Plan 状态**: ✅ 完成  
**版本**: v1.0  
**Planned by**: Claude Sonnet  
**Date**: 2026-06-13
