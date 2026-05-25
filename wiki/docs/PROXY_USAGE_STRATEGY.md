# 代理使用策略

**版本**: v1.0  
**日期**: 2026-05-25  
**状态**: 已实施

---

## 📋 概述

本文档说明 Vibe-Trading 项目中各数据源的代理使用策略。

**核心原则**: 只有访问国外 API 的数据源需要代理，中国本地 API 不需要代理。

---

## 🌍 数据源分类

### 需要代理的数据源

| 数据源 | 市场 | 原因 | 代理配置 |
|--------|------|------|----------|
| **yfinance** | 美股、港股、美国期货 | Yahoo Finance 在中国被限制访问 | ✅ 强制代理 + 健康检查 |

### 不需要代理的数据源

| 数据源 | 市场 | 原因 | 代理配置 |
|--------|------|------|----------|
| **tushare** | A股、中国期货 | 中国本地 API，直连更快 | ❌ 无代理 |
| **akshare** | A股、中国期货 | 中国本地 API，直连更快 | ❌ 无代理 |
| **TqSdk** | 中国期货 | 中国本地 API，直连更快 | ❌ 无代理 |
| **futu** | 港股、美股 | 富途 API，直连更快 | ❌ 无代理 |

---

## 🔧 实现细节

### yfinance 代理实现

**文件**: `agent/backtest/loaders/yfinance_loader.py`

**特性**:
1. ✅ **强制代理健康检查** - 下载前检查代理状态
2. ✅ **自动代理配置** - 从环境变量读取代理
3. ✅ **失败快速响应** - 代理不可用时立即失败
4. ✅ **清晰错误信息** - 提供故障排查指导

**代码示例**:
```python
class DataLoader:
    """yfinance data loader with proxy support."""
    
    def __init__(self, enable_proxy: bool = True):
        # 只有 yfinance 需要代理
        self.proxy_manager = ProxyManager() if enable_proxy else None
    
    def fetch(self, codes, start_date, end_date, interval):
        # 下载前强制检查代理健康状态
        proxy = self.proxy_manager.get_proxy(force_check=True)
        # ... download logic
```

### 其他数据源实现

**文件**: 
- `agent/backtest/loaders/tushare.py`
- `agent/backtest/loaders/akshare_loader.py`
- `agent/backtest/loaders/tqsdk_loader.py`

**特性**:
- ❌ **不使用 ProxyManager**
- ✅ **直连 API** - 更快、更稳定
- ✅ **使用 API Token** - 通过 token 认证

**代码示例**:
```python
class TushareLoader:
    """Tushare data loader - no proxy needed."""
    
    def __init__(self, token: str):
        # 直连，不需要代理
        self.api = ts.pro_api(token)
    
    def fetch(self, codes, start_date, end_date):
        # 直接调用 API，无代理
        df = self.api.daily(ts_code=code, start_date=start_date, end_date=end_date)
        return df
```

---

## 📊 性能对比

### yfinance（需要代理）

| 指标 | 无代理 | 有代理 |
|------|--------|--------|
| 连接成功率 | ❌ 0% (被墙) | ✅ 95%+ |
| 平均延迟 | N/A | ~500ms |
| 限流风险 | ❌ 高 | ✅ 低 |

### tushare/akshare（不需要代理）

| 指标 | 无代理 | 有代理 |
|------|--------|--------|
| 连接成功率 | ✅ 99%+ | ⚠️ 可能更慢 |
| 平均延迟 | ~100ms | ~300ms |
| 稳定性 | ✅ 高 | ⚠️ 依赖代理 |

**结论**: 中国本地 API 直连更快、更稳定。

---

## 🔍 代理健康检查

### 仅对 yfinance 启用

**检查时机**:
- ✅ 每次下载前强制检查
- ✅ 周期性健康检查（5分钟）

**检查方法**:
```python
# 测试连接 Yahoo Finance
response = requests.get(
    "https://finance.yahoo.com",
    proxies={"http": proxy, "https": proxy},
    timeout=10,
)
```

**失败处理**:
- ❌ 代理不可用 → 抛出 `RuntimeError`，阻止下载
- ✅ 代理可用 → 继续下载

### 其他数据源

**检查时机**:
- ❌ 不检查代理（因为不使用代理）

**失败处理**:
- 直接处理 API 错误（token 无效、限流等）

---

## 🎯 使用指南

### 场景 1: 下载美股数据（yfinance）

**前提条件**:
1. ✅ 代理服务运行中（Clash/V2Ray）
2. ✅ 环境变量配置正确

**步骤**:
```python
from agent.backtest.loaders.yfinance_loader import DataLoader

# 自动使用代理
loader = DataLoader(enable_proxy=True)

# 下载前会自动检查代理
data = loader.fetch(
    codes=["AAPL.US"],
    start_date="2024-01-01",
    end_date="2024-01-10",
    interval="1D",
)
```

**如果代理不可用**:
```
RuntimeError: No available proxies! All 1 proxies are unavailable.
⚠️  Please ensure your proxy is running before downloading data.
```

---

### 场景 2: 下载 A股数据（tushare）

**前提条件**:
1. ✅ Tushare Token 配置正确
2. ❌ 不需要代理

**步骤**:
```python
from agent.backtest.loaders.tushare import TushareLoader

# 直连，不使用代理
loader = TushareLoader(token="your_token")

# 直接下载，无代理检查
data = loader.fetch(
    codes=["000001.SZ"],
    start_date="20240101",
    end_date="20240110",
)
```

**优势**:
- ✅ 更快（直连）
- ✅ 更稳定（不依赖代理）
- ✅ 无代理健康检查开销

---

### 场景 3: 混合下载（美股 + A股）

**步骤**:
```python
from agent.backtest.loaders.registry import Registry

# 注册表会自动选择合适的数据源
registry = Registry()

# 美股 - 自动使用 yfinance + 代理
us_data = registry.fetch(
    codes=["AAPL.US"],
    start_date="2024-01-01",
    end_date="2024-01-10",
    market="us_equity",
)

# A股 - 自动使用 tushare，无代理
cn_data = registry.fetch(
    codes=["000001.SZ"],
    start_date="2024-01-01",
    end_date="2024-01-10",
    market="cn_equity",
)
```

**自动路由**:
- ✅ yfinance → 使用代理 + 健康检查
- ✅ tushare → 直连，无代理

---

## 🔧 配置管理

### 环境变量配置

**yfinance 代理配置**:
```bash
# 设置代理（yfinance 会自动读取）
export HTTPS_PROXY=socks5://127.0.0.1:10829
export HTTP_PROXY=socks5://127.0.0.1:10829
export ALL_PROXY=socks5://127.0.0.1:10829
```

**其他数据源配置**:
```bash
# Tushare Token
export TUSHARE_TOKEN=your_token_here

# Akshare 不需要配置（免费）

# TqSdk 账号
export TQSDK_ACCOUNT=your_account
export TQSDK_PASSWORD=your_password
```

### 代码配置

**禁用 yfinance 代理**（不推荐）:
```python
# 仅用于测试或特殊场景
loader = DataLoader(enable_proxy=False)
```

**强制其他数据源使用代理**（不推荐）:
```python
# 不推荐：会降低性能
# tushare/akshare 不支持代理配置
```

---

## 📝 最佳实践

### ✅ 推荐做法

1. **yfinance 始终使用代理**
   - 避免被墙
   - 避免限流
   - 健康检查保证可用性

2. **中国 API 直连**
   - 更快
   - 更稳定
   - 减少代理负载

3. **代理池管理**（Phase 6 计划）
   - 多代理轮换
   - 自动切换
   - 负载均衡

### ❌ 避免做法

1. **不要给中国 API 配置代理**
   - 降低性能
   - 增加复杂度
   - 浪费代理资源

2. **不要禁用 yfinance 代理**
   - 会被墙
   - 会被限流
   - 下载失败

3. **不要混用代理配置**
   - 保持配置清晰
   - 避免冲突

---

## 🔄 未来优化

### Phase 6.2: 代理管理增强

**计划**:
- [ ] 多代理池支持
- [ ] 自动代理轮换
- [ ] 代理性能监控
- [ ] 代理故障切换

**仍然只针对 yfinance**:
- ✅ yfinance → 使用代理池
- ❌ tushare/akshare → 继续直连

### Phase 6.3: 智能路由

**计划**:
- [ ] 根据数据源自动选择代理策略
- [ ] 动态调整代理配置
- [ ] 代理使用统计

**路由规则**:
```python
routing_rules = {
    "yfinance": {"proxy": "required", "health_check": True},
    "tushare": {"proxy": "disabled", "health_check": False},
    "akshare": {"proxy": "disabled", "health_check": False},
    "tqsdk": {"proxy": "disabled", "health_check": False},
}
```

---

## 📚 相关文档

- [代理健康检查修复报告](PROXY_HEALTH_CHECK_FIX.md)
- [数据层优化方案](DATA_LAYER_OPTIMIZATION_PLAN.md)
- [ProxyManager 源码](../../agent/backtest/loaders/proxy_manager.py)
- [yfinance Loader 源码](../../agent/backtest/loaders/yfinance_loader.py)

---

## 📝 变更记录

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| v1.0 | 2026-05-25 | Kiro | 初始版本，明确代理使用策略 |

---

**最后更新**: 2026-05-25  
**维护者**: Kiro (Claude Sonnet 4.6)
