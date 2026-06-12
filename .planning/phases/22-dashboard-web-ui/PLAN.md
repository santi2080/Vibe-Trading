# Phase 22: Dashboard Web UI

**目标**: 添加 Dashboard 页面展示扫描结果和信号统计  
**优先级**: P1  
**基于 Spike**: `SPIKE.md`  
**预计工时**: 3-4 小时  
**版本**: v1.0

---

## 📋 概述

基于现有的 React 前端 + 扫描循环产物，构建 Dashboard 页面。

### 现有能力
- ✅ React 19 + Vite + TypeScript 前端
- ✅ 扫描循环产物 (manifest.json, scan_results.json, data_health.json)
- ✅ API 层 (api.ts, runReports.ts)
- ✅ 路由系统 (React Router v7)
- ✅ 状态管理 (Zustand)
- ✅ 图表 (ECharts)

### 本次新增
- ⭐ Dashboard 页面 (`/dashboard`)
- ⭐ 扫描摘要组件
- ⭐ 信号分布图表
- ⭐ 健康状态显示
- ⭐ 扫描历史列表

---

## 🎯 目标

创建 Dashboard 页面，包含：

1. **扫描摘要卡片** - 最新扫描的信号统计
2. **数据健康状态** - 健康门控结果
3. **信号分布图表** - Actionable/Watch/Risk 分布
4. **扫描历史列表** - 历史扫描记录

---

## 📊 实施计划

### Task 1: 创建 Dashboard 页面骨架

**文件**: `frontend/src/pages/Dashboard.tsx`

**路由**: `/dashboard`

**组件结构**:
```tsx
export default function Dashboard() {
  return (
    <div className="space-y-6">
      <h1>Dashboard</h1>
      <ScanSummary />
      <HealthStatus />
      <SignalChart />
      <ScanHistory />
    </div>
  );
}
```

### Task 2: 创建扫描摘要组件

**文件**: `frontend/src/components/dashboard/ScanSummary.tsx`

**功能**:
- 显示最新扫描时间
- 信号统计 (Actionable, Watch, Risk, Skipped, Failed)
- 总符号数统计

### Task 3: 创建健康状态组件

**文件**: `frontend/src/components/dashboard/HealthStatus.tsx`

**功能**:
- 显示数据健康状态 (PASS, WARN, FAIL)
- 过期数据列表
- 数据新鲜度信息

### Task 4: 创建信号分布图表

**文件**: `frontend/src/components/dashboard/SignalChart.tsx`

**功能**:
- 饼图显示信号分布
- 使用 ECharts (已有依赖)
- 响应式设计

### Task 5: 创建扫描历史列表

**文件**: `frontend/src/components/dashboard/ScanHistory.tsx`

**功能**:
- 列出历史扫描记录
- 显示时间、状态、摘要
- 可点击查看详情

### Task 6: 创建 API 服务

**文件**: `frontend/src/lib/dashboardApi.ts`

**功能**:
- 获取最新扫描结果
- 获取扫描历史列表
- 获取数据健康状态

### Task 7: 添加路由

**文件**: `frontend/src/router.tsx`

**添加**:
```tsx
{ path: "/dashboard", element: wrap(Dashboard) },
```

### Task 8: 单元测试

**文件**: `frontend/src/__tests__/Dashboard.test.tsx`

**测试用例**:
- [ ] Dashboard 渲染
- [ ] 摘要卡片显示
- [ ] 历史列表显示
- [ ] 空状态处理

---

## 🏗️ 数据接口

### 扫描摘要数据

```typescript
interface ScanSummary {
  timestamp: string;
  total_symbols: number;
  actionable: number;
  watch: number;
  risk: number;
  skipped: number;
  failed: number;
  health_status: "PASS" | "WARN" | "FAIL";
}
```

### 扫描历史项

```typescript
interface ScanHistoryItem {
  id: string;
  timestamp: string;
  health_status: "PASS" | "WARN" | "FAIL";
  total_symbols: number;
  actionable: number;
}
```

---

## 📁 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/pages/Dashboard.tsx` | 新建 | Dashboard 页面 |
| `frontend/src/components/dashboard/ScanSummary.tsx` | 新建 | 扫描摘要组件 |
| `frontend/src/components/dashboard/HealthStatus.tsx` | 新建 | 健康状态组件 |
| `frontend/src/components/dashboard/SignalChart.tsx` | 新建 | 信号图表组件 |
| `frontend/src/components/dashboard/ScanHistory.tsx` | 新建 | 历史列表组件 |
| `frontend/src/lib/dashboardApi.ts` | 新建 | API 服务 |
| `frontend/src/router.tsx` | 修改 | 添加路由 |
| `frontend/src/__tests__/Dashboard.test.tsx` | 新建 | 测试 |

---

## ✅ 验收标准

### 功能验收
- [ ] Dashboard 页面正常加载
- [ ] 扫描摘要显示正确
- [ ] 信号图表显示正确
- [ ] 历史列表显示正确
- [ ] 路由正确跳转

### 测试验收
- [ ] 新增测试全部通过
- [ ] 回归测试全部通过

### UI 验收
- [ ] 响应式布局
- [ ] 加载状态处理
- [ ] 空状态处理
- [ ] 错误状态处理

---

## 🔄 未来扩展

| 功能 | 说明 | 触发条件 |
|------|------|---------|
| 实时更新 | WebSocket 推送新结果 | 扫描自动化 |
| 图表详情 | 点击展开信号详情 | v2 |
| 导出功能 | 导出报告为 PDF | v2 |
| 通知集成 | 扫描完成通知 | v3 |

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
