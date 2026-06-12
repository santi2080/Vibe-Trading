# Phase 22 Spike: Dashboard/Web UI

**Phase**: 22  
**Direction**: Dashboard / Web UI  
**Status**: IN PROGRESS  
**Date**: 2026-06-13  
**Goal**: Research and scope Dashboard/Web UI implementation for Vibe-Trading

---

## Context

After v2.4 exchange calendar awareness milestone, we're exploring Dashboard/Web UI as Phase 22.

**What exists today**:
- CLI/TUI interface via `vibe-trading` command
- React frontend in `frontend/` directory (existing but may be stale)
- FastAPI backend potentially available

**What users want**:
- Visual dashboard for scan results
- Real-time monitoring of signals
- Historical performance tracking
- Easy configuration

---

## Research Questions

### RQ1: Frontend Stack Assessment

**Q**: What frontend stack is currently in `frontend/` directory?

**Tasks**:
- [ ] Read `frontend/package.json` for dependencies
- [ ] Check `frontend/src/` structure
- [ ] Assess framework (React, Vue, Svelte, etc.)
- [ ] Note any API integration points

### RQ2: Backend API Assessment

**Q**: What API endpoints exist or need to be created?

**Tasks**:
- [ ] Check for existing FastAPI app
- [ ] Identify scan result endpoints needed
- [ ] Check for WebSocket support if real-time needed
- [ ] Define API contract for dashboard

### RQ3: Dashboard Scope

**Q**: What should the dashboard show?

**Options**:
1. **Minimal**: Show latest scan results + signal counts
2. **Medium**: Scan results + watchlist status + signal history
3. **Full**: All of above + charts + configuration UI

**Recommendation**: Start with Medium (v1), leverages existing frontend

### RQ4: Architecture Decision

**Q**: How should frontend and backend communicate?

**Options**:
1. **SPA + REST API**: Single page app with REST API calls
2. **SSR**: Server-side rendering with FastAPI templates
3. **Static + JSON**: Static frontend reading JSON artifacts

**Recommendation**: SPA + REST API (leverages existing frontend + api.ts)

---

## Research Findings

### RQ1: Frontend Stack Assessment ✅

**Current Stack**:
- React 19 + Vite (modern)
- TypeScript (strict mode)
- Tailwind CSS + shadcn/ui components
- Zustand for state management
- ECharts for charts
- React Router for routing
- Lucide icons
- Sonner for toasts

**Existing Pages**:
- `/` - Home
- `/agent` - Agent interface
- `/settings` - Settings
- `/runs/:runId` - Run detail
- `/compare` - Compare runs
- `/correlation` - Correlation analysis
- `/alpha-zoo` - Alpha library

**Conclusion**: Modern, well-structured React app. Add Dashboard page.

### RQ2: Backend API Assessment ✅

**Existing API utilities** (`frontend/src/lib/api.ts`):
- File upload support
- Authentication headers
- Error handling with ApiError class
- Scan results fetching via `runReports.ts`

**Data artifacts** (from scan loop):
- `manifest.json` - scan metadata
- `scan_results.json` - signal results
- `data_health.json` - health gate results

**Conclusion**: API layer exists. Need to add dashboard endpoints.

### RQ3: Dashboard Scope ✅

**Recommendation: Dashboard v1 (Medium)**

| Feature | Priority | Notes |
|---------|----------|-------|
| Dashboard home page | P0 | New `/dashboard` route |
| Latest scan summary | P0 | Signal counts, health status |
| Scan results list | P0 | Browse recent scans |
| Data health display | P1 | Show health gate results |
| Signal breakdown chart | P1 | ECharts pie/bar |
| Watchlist status | P2 | Current watchlist overview |

### RQ4: Architecture Decision ✅

**Recommendation: SPA + REST API (extend existing)**

- Add `/api/dashboard` endpoints to backend
- Create `/dashboard` React page
- Use existing Zustand stores
- Fetch scan artifacts via API

---

## Next Steps

1. [x] Frontend stack assessment
2. [x] Define dashboard scope
3. [x] Architecture decision
4. [ ] Create implementation plan (PLAN.md)
5. [ ] Implement dashboard page
6. [ ] Add API endpoints
7. [ ] Add components

---

## Initial Scope Ideas

### Dashboard v1 Features

| Feature | Priority | Notes |
|---------|----------|-------|
| Dashboard home page | P0 | New route `/dashboard` |
| Latest scan summary | P0 | Signal counts, health status |
| Scan results list | P0 | Browse recent scans |
| Data health display | P1 | Show health gate results |
| Signal breakdown chart | P1 | ECharts pie/bar |

### Tech Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Framework | React 19 + Vite | Existing |
| Routing | React Router v7 | Existing |
| State | Zustand | Existing |
| Charts | ECharts | Existing |
| Styling | Tailwind CSS | Existing |
| Icons | Lucide React | Existing |

---

*Spike status: COMPLETE*
*Date: 2026-06-13*
