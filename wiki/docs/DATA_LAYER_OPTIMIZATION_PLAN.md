# 数据层优化方案

**版本**: v1.0  
**日期**: 2026-05-25  
**状态**: 待实施

---

## 📋 背景

### 当前状况
- ✅ 已实现三级缓存架构（L1内存 + L2磁盘 + L3原始数据）
- ✅ 已实现多数据源切换和回退链
- ✅ 已实现数据质量检查（5维度）
- ✅ 已实现增量更新机制
- ✅ 已配置代理解决 yfinance 限流问题

### 发现的问题
1. **代理依赖未管理**：代理是核心依赖，但没有健康检查和故障切换
2. **限流控制过度设计**：代理解决了80%的限流问题，复杂的退避重试不再必要
3. **监控不足**：缺少数据源健康度评分和实时告警
4. **缓存未生效**：测试发现缓存命中率为0%，需要排查

---

## 🎯 优化目标

### P0 - 核心功能（保持）
- [x] 三级缓存系统
- [x] 多数据源切换
- [x] 数据质量检查
- [x] 增量更新

### P1 - 新增功能（高优先级）
- [ ] 代理管理模块
- [ ] 数据源健康度评分
- [ ] 缓存问题修复

### P2 - 优化功能（中优先级）
- [ ] 监控和告警强化
- [ ] 简化限流控制
- [ ] 简化退避重试

### P3 - 未来功能（低优先级）
- [ ] 数据预热机制
- [ ] 智能缓存失效策略

---

## 📐 详细设计

### 1. 代理管理模块 (P1)

#### 1.1 功能需求
- 代理池管理（支持多个代理轮换）
- 代理健康检查（定期测试可用性）
- 自动切换代理（失败时）
- 代理性能监控（延迟、成功率）

#### 1.2 架构设计
```python
class ProxyManager:
    """代理管理器"""
    
    def __init__(self, proxies: List[str]):
        self.proxies = proxies  # 代理列表
        self.health_scores = {}  # 健康度评分
        self.current_proxy = None
        
    def get_proxy(self) -> Optional[str]:
        """获取当前最优代理"""
        
    def check_health(self, proxy: str) -> bool:
        """检查代理健康状态"""
        
    def rotate_proxy(self):
        """切换到下一个代理"""
        
    def get_stats(self) -> Dict:
        """获取代理统计信息"""
```

#### 1.3 配置方式
```yaml
# config/proxy.yaml
proxies:
  - socks5://127.0.0.1:10829
  - http://proxy2.example.com:8080
  
health_check:
  interval: 300  # 5分钟检查一次
  timeout: 10    # 超时时间
  test_url: https://finance.yahoo.com
  
rotation:
  on_failure: true  # 失败时自动切换
  max_retries: 3    # 最大重试次数
```

#### 1.4 实施步骤
1. 创建 `agent/backtest/loaders/proxy_manager.py`
2. 实现代理池管理
3. 实现健康检查机制
4. 集成到 yfinance_loader
5. 添加单元测试

---

### 2. 数据源健康度评分 (P1)

#### 2.1 功能需求
- 实时计算数据源健康度
- 基于多维度评分（成功率、延迟、数据质量）
- 自动降级/恢复机制
- 影响数据源选择优先级

#### 2.2 评分维度
| 维度 | 权重 | 说明 |
|------|------|------|
| 成功率 | 40% | 最近100次请求的成功率 |
| 平均延迟 | 30% | 响应时间 |
| 数据完整性 | 20% | 数据质量检查通过率 |
| 可用性 | 10% | 是否在线 |

#### 2.3 架构设计
```python
class SourceHealthScore:
    """数据源健康度评分"""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.request_history = deque(maxlen=100)
        
    def record_request(self, success: bool, latency: float, quality_score: float):
        """记录请求结果"""
        
    def get_score(self) -> float:
        """计算综合健康度评分 (0-100)"""
        
    def should_downgrade(self) -> bool:
        """是否应该降级"""
        
    def should_recover(self) -> bool:
        """是否应该恢复"""
```

#### 2.4 实施步骤
1. 创建 `agent/backtest/loaders/health_score.py`
2. 实现评分算法
3. 集成到 Registry
4. 修改回退链逻辑（优先选择高分数据源）
5. 添加单元测试

---

### 3. 缓存问题修复 (P1)

#### 3.1 问题分析
测试发现缓存命中率为0%，可能原因：
- 缓存键生成不一致
- 缓存目录权限问题
- 缓存过期策略过于激进
- 数据格式不匹配

#### 3.2 排查步骤
1. 添加详细日志，记录缓存键生成过程
2. 检查缓存目录是否正常创建
3. 验证缓存读写流程
4. 测试缓存命中场景

#### 3.3 修复方案
```python
# 在 CachedDataLoader.fetch() 中添加调试日志
logger.debug(f"Cache key: {cache_key}")
logger.debug(f"Cache dir: {self.cache.cache_dir}")
logger.debug(f"Cache file exists: {cache_file.exists()}")
```

#### 3.4 实施步骤
1. 添加调试日志
2. 运行测试用例，收集日志
3. 定位问题根因
4. 修复代码
5. 验证缓存功能

---

### 4. 监控和告警强化 (P2)

#### 4.1 功能需求
- 下载成功率监控
- 数据质量监控
- 异常告警（Slack/邮件）
- 性能指标（延迟、吞吐量）

#### 4.2 架构设计
```python
class DownloadMonitor:
    """下载监控器"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        
    def record_download(self, source: str, symbol: str, success: bool, 
                       latency: float, data_size: int):
        """记录下载事件"""
        
    def get_metrics(self) -> Dict:
        """获取监控指标"""
        
    def check_alerts(self) -> List[Alert]:
        """检查是否需要告警"""
        
    def send_alert(self, alert: Alert):
        """发送告警"""
```

#### 4.3 监控指标
- 下载成功率（按数据源、按品种）
- 平均延迟（P50、P95、P99）
- 数据质量评分
- 缓存命中率
- API 调用次数

#### 4.4 告警规则
| 指标 | 阈值 | 级别 |
|------|------|------|
| 成功率 < 80% | 连续5分钟 | Warning |
| 成功率 < 50% | 连续1分钟 | Critical |
| P95延迟 > 10s | 连续5分钟 | Warning |
| 数据质量 < 60分 | 单次 | Warning |

#### 4.5 实施步骤
1. 创建 `agent/backtest/loaders/monitor.py`
2. 实现监控指标收集
3. 实现告警规则引擎
4. 集成到 CachedDataLoader
5. 添加 Slack/邮件通知

---

### 5. 简化限流控制 (P2)

#### 5.1 当前实现
- 复杂的令牌桶算法
- 动态速率调整
- 多级限流策略

#### 5.2 简化方案
代理解决了大部分限流问题，简化为：
```python
# 从复杂的令牌桶简化为固定间隔
import time

class SimpleRateLimiter:
    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.last_request = 0
        
    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_request = time.time()
```

#### 5.3 实施步骤
1. 创建 `agent/backtest/loaders/rate_limiter.py`
2. 实现简单限流器
3. 替换现有复杂实现
4. 更新测试用例

---

### 6. 简化退避重试 (P2)

#### 6.1 当前实现
- 指数退避算法
- 动态调整退避时间
- 复杂的重试策略

#### 6.2 简化方案
```python
# 从指数退避简化为固定重试
def fetch_with_retry(func, max_retries=3, retry_delay=1.0):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
            time.sleep(retry_delay)
```

#### 6.3 实施步骤
1. 修改 `agent/backtest/loaders/yfinance_loader.py`
2. 简化重试逻辑
3. 更新测试用例

---

## 📅 实施计划

### Phase 1: 核心修复 (1-2天)
- [x] Task 1.1: yfinance 集成 US Futures
- [ ] Task 1.2: 缓存问题排查和修复
- [ ] Task 1.3: 验证缓存功能

### Phase 2: 代理管理 (2-3天)
- [ ] Task 2.1: 实现 ProxyManager
- [ ] Task 2.2: 集成到 yfinance_loader
- [ ] Task 2.3: 添加配置文件
- [ ] Task 2.4: 单元测试

### Phase 3: 健康度评分 (2-3天)
- [ ] Task 3.1: 实现 SourceHealthScore
- [ ] Task 3.2: 集成到 Registry
- [ ] Task 3.3: 修改回退链逻辑
- [ ] Task 3.4: 单元测试

### Phase 4: 监控强化 (2-3天)
- [ ] Task 4.1: 实现 DownloadMonitor
- [ ] Task 4.2: 集成到 CachedDataLoader
- [ ] Task 4.3: 实现告警通知
- [ ] Task 4.4: 添加监控面板

### Phase 5: 简化优化 (1-2天)
- [ ] Task 5.1: 简化限流控制
- [ ] Task 5.2: 简化退避重试
- [ ] Task 5.3: 更新文档

**总工期**: 8-13 天

---

## 🧪 验收标准

### 功能验收
- [ ] yfinance 可以下载 US Futures 数据
- [ ] 缓存命中率 > 80%（重复请求）
- [ ] 代理自动切换正常工作
- [ ] 数据源健康度评分准确
- [ ] 监控指标正常收集
- [ ] 告警规则正常触发

### 性能验收
- [ ] 首次下载延迟 < 2s/品种
- [ ] 缓存命中延迟 < 50ms
- [ ] 内存占用 < 500MB
- [ ] 磁盘缓存大小合理

### 质量验收
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 代码审查通过
- [ ] 文档完整

---

## 📊 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 代理不稳定 | 高 | 中 | 实现代理池，自动切换 |
| 缓存问题复杂 | 中 | 低 | 详细日志，逐步排查 |
| 监控性能开销 | 低 | 低 | 异步收集，采样策略 |
| 简化后功能退化 | 中 | 低 | 保留原实现，灰度切换 |

---

## 📚 参考资料

- [Phase 1 数据层增强计划](./PHASE1_DATA_ENHANCEMENT_PLAN.md)
- [缓存系统设计文档](./CACHE_SYSTEM_DESIGN.md)
- [数据质量检查规范](./DATA_QUALITY_SPEC.md)
- [Watchlist 数据下载规则](../.claude/projects/-Users-iagent-projects/memory/watchlist-data-rules.md)

---

## 📝 变更记录

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| v1.0 | 2026-05-25 | Kiro | 初始版本 |
