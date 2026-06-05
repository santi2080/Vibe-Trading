# External Integrations

**Analysis Date:** 2026-06-03

## APIs & External Services

**LLM providers:**
- OpenRouter - Default multi-model gateway for chat/research agent execution and settings-driven model switching.
  - SDK/Client: `langchain-openai` via `agent/src/providers/llm.py`
  - Auth: `OPENROUTER_API_KEY`
- OpenAI - Direct OpenAI-compatible chat provider for the same agent surface.
  - SDK/Client: `langchain-openai` via `agent/src/providers/llm.py`
  - Auth: `OPENAI_API_KEY`
- OpenAI Codex (ChatGPT OAuth) - OAuth-based coding/reasoning provider variant.
  - SDK/Client: `langchain-openai` + custom adapter in `agent/src/providers/openai_codex.py`
  - Auth: OAuth via `oauth-cli-kit`; base URL in `OPENAI_CODEX_BASE_URL`
- DeepSeek, Gemini, Groq, DashScope/Qwen, Zhipu, Moonshot/Kimi, MiniMax, Xiaomi MIMO, Z.ai, Ollama - All exposed through the same provider abstraction and selectable from settings.
  - SDK/Client: `langchain-openai` via `agent/src/providers/llm.py` and provider catalog `agent/src/providers/llm_providers.json`
  - Auth: provider-specific env vars such as `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `DASHSCOPE_API_KEY`, `ZHIPU_API_KEY`, `MOONSHOT_API_KEY`, `MINIMAX_API_KEY`, `MIMO_API_KEY`, `ZAI_API_KEY`; Ollama uses `OLLAMA_BASE_URL` and no API key

**Market data providers:**
- Tushare - China A-shares, funds, futures, macro, and fundamentals; primary authenticated China-market source.
  - SDK/Client: `tushare` via `agent/backtest/loaders/tushare.py` and `agent/backtest/loaders/tushare_fundamentals.py`
  - Auth: `TUSHARE_TOKEN`
- TqSdk - China futures data with pooled connections and optional credentialed access.
  - SDK/Client: `tqsdk` via `agent/backtest/loaders/tqsdk_loader.py`
  - Auth: `TQSDK_ACCOUNT` and `TQSDK_PASSWORD` (or `TQ_ACCOUNT` / `TQ_PASSWORD`)
- YFinance / Yahoo Finance - Free HK/US equity and some futures access, optionally routed through proxies.
  - SDK/Client: `yfinance` via `agent/backtest/loaders/yfinance_loader.py`
  - Auth: None
- AKShare - Free fallback/primary source across A-shares, macro, forex, and some futures scenarios.
  - SDK/Client: `akshare` via `agent/backtest/loaders/akshare_loader.py` and routing docs in `agent/src/skills/data-routing/SKILL.md`
  - Auth: None
- OKX public API - Primary public crypto candles source.
  - SDK/Client: `requests` via `agent/backtest/loaders/okx.py`
  - Auth: None
- CCXT exchanges - Multi-exchange crypto fallback, defaulting to Binance unless overridden.
  - SDK/Client: `ccxt` via `agent/backtest/loaders/ccxt_loader.py`
  - Auth: Public market data path uses no key; exchange choice via `CCXT_EXCHANGE`
- Futu OpenAPI - Optional HK/A-share source when local FutuOpenD is running.
  - SDK/Client: `futu` via `agent/backtest/loaders/futu.py`
  - Auth: local service coordinates via `FUTU_HOST` and `FUTU_PORT`

**Search / web research:**
- DuckDuckGo search - Web discovery for research flows.
  - SDK/Client: `ddgs` in `agent/src/tools/web_search_tool.py`
  - Auth: None

**Documentation hosting:**
- Cloudflare Pages - Static wiki deployment pipeline.
  - SDK/Client: `cloudflare/wrangler-action` via `.github/workflows/wiki-deploy.yml`
  - Auth: GitHub Actions secrets for Cloudflare credentials

## Data Storage

**Databases:**
- SQLite - Session search index and finance research goal store.
  - Connection: local file at `~/.vibe-trading/sessions.db` in `agent/src/session/search.py` and `agent/src/goal/store.py`
  - Client: Python `sqlite3`

**File Storage:**
- Local filesystem only for primary runtime data.
  - Sessions: `agent/sessions/` via `agent/src/session/store.py`
  - Runs/artifacts: `agent/runs/` and `.swarm/runs/` via `agent/api_server.py` and `agent/src/swarm/store.py`
  - Uploads: `agent/uploads/` via `agent/api_server.py`
  - Reports: HTML/PDF artifacts generated under report directories in `agent/src/shadow_account/reporter.py`

**Caching:**
- Filesystem cache for market data loaders.
  - Service: local cache directory configured by `VIBE_CACHE_DIR`
  - Client: `CachedDataLoader` wrapper enabled in `agent/backtest/loaders/registry.py`
  - Disable switch: `VIBE_DISABLE_CACHE`

## Authentication & Identity

**Auth Provider:**
- Custom bearer-token auth for HTTP API.
  - Implementation: `API_AUTH_KEY` checked by `require_auth` / `require_event_stream_auth` in `agent/api_server.py`
- Loopback/dev-mode local trust path.
  - Implementation: local-only access allowed when `API_AUTH_KEY` is unset, guarded in `agent/api_server.py`; Docker loopback exception controlled by `VIBE_TRADING_TRUST_DOCKER_LOOPBACK`
- OAuth for OpenAI Codex provider login.
  - Implementation: login command surfaced from `agent/src/providers/llm_providers.json` and supported by CLI/settings flows

## Monitoring & Observability

**Error Tracking:**
- None detected as a third-party SaaS integration.

**Logs:**
- Application logging uses Python logging and Rich console output in files such as `agent/api_server.py`, `agent/mcp_server.py`, and `agent/src/providers/llm.py`.
- Swarm runs persist append-only event logs in `.swarm/runs/{run_id}/events.jsonl` via `agent/src/swarm/store.py`.
- CI validation logs are produced by GitHub Actions workflows in `.github/workflows/test.yml` and `.github/workflows/wiki.yml`.

## CI/CD & Deployment

**Hosting:**
- Main app: self-hosted/containerized FastAPI + built SPA from `Dockerfile` and `docker-compose.yml`.
- Documentation site: Cloudflare Pages via `.github/workflows/wiki-deploy.yml`.

**CI Pipeline:**
- GitHub Actions.
  - Test/build workflow: `.github/workflows/test.yml`
  - Wiki validation: `.github/workflows/wiki.yml`
  - Wiki deployment: `.github/workflows/wiki-deploy.yml`

## Environment Configuration

**Required env vars:**
- LLM runtime: `LANGCHAIN_PROVIDER`, `LANGCHAIN_MODEL_NAME`
- One provider credential/base pair depending on chosen model, such as `OPENROUTER_API_KEY` + `OPENROUTER_BASE_URL` or `OPENAI_API_KEY` + `OPENAI_BASE_URL`
- China market data when using Tushare: `TUSHARE_TOKEN`
- API protection when exposing beyond localhost: `API_AUTH_KEY`
- Frontend dev proxy target when running UI separately: `VITE_API_URL` in `frontend/vite.config.ts`

**Secrets location:**
- Local backend secrets and provider settings live in `agent/.env` with the template in `agent/.env.example`.
- Docker Compose loads backend env from `agent/.env` via `docker-compose.yml`.
- CI/deploy secrets live in GitHub Actions secrets referenced by `.github/workflows/wiki-deploy.yml`.

## Webhooks & Callbacks

**Incoming:**
- SSE streams for live progress and chat/swarm updates.
  - Session events: `/sessions/{session_id}/events` in `agent/api_server.py`
  - Swarm events: `/swarm/runs/{run_id}/events` in `agent/api_server.py`
  - Alpha bench stream: `/alpha/bench/{job_id}/stream` in `agent/src/api/alpha_routes.py`
- MCP transports.
  - Stdio and SSE modes supported by `agent/mcp_server.py`

**Outgoing:**
- HTTP calls to external LLM APIs through `langchain-openai` in `agent/src/providers/llm.py`
- HTTP calls to OKX public REST API in `agent/backtest/loaders/okx.py`
- HTTP/data fetches through Yahoo Finance in `agent/backtest/loaders/yfinance_loader.py`
- Exchange/API calls through CCXT in `agent/backtest/loaders/ccxt_loader.py`
- Optional DuckDuckGo search requests from `agent/src/tools/web_search_tool.py`

---

*Integration audit: 2026-06-03*
