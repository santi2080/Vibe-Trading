# Technology Stack

**Analysis Date:** 2026-06-03

## Languages

**Primary:**
- Python 3.11+ - Core product runtime in `pyproject.toml`, backend API in `agent/api_server.py`, MCP server in `agent/mcp_server.py`, CLI in `agent/cli/main.py`, trading/backtest engine in `agent/backtest/`.
- TypeScript 5.x - Browser UI in `frontend/src/`, built with `frontend/tsconfig.json` and `frontend/vite.config.ts`.

**Secondary:**
- Markdown - Skill system and research guidance under `agent/src/skills/*/SKILL.md`.
- YAML - MCP/config and proxy settings in `config/proxy.yaml`, skill metadata frontmatter in `agent/src/skills/**/SKILL.md`, and swarm presets shipped under package data from `pyproject.toml`.
- JSON - Provider catalog in `agent/src/providers/llm_providers.json`, run/session artifacts under `agent/runs/` and `agent/sessions/`, and frontend package metadata in `frontend/package.json`.

## Runtime

**Environment:**
- Python 3.11 slim container runtime in `Dockerfile`.
- Node.js 20 for frontend build/dev in `Dockerfile`, `docker-compose.yml`, and `.github/workflows/test.yml`.
- Browser runtime for the SPA mounted by FastAPI from `frontend/dist` in `agent/api_server.py`.

**Package Manager:**
- Python packaging via setuptools/PEP 621 in `pyproject.toml`.
- Docker image installs Python dependencies from `agent/requirements.txt` and then performs `pip install -e .` in `Dockerfile`.
- Frontend uses npm with lockfile-backed installs from `frontend/package-lock.json` in `Dockerfile` and `.github/workflows/test.yml`.
- Lockfile: Python lockfile missing; npm lockfile present at `frontend/package-lock.json`.

## Frameworks

**Core:**
- FastAPI - Main HTTP API, settings API, session API, swarm API, upload API, and SPA static hosting in `agent/api_server.py`.
- FastMCP - MCP server and tool exposure for Claude Desktop/OpenClaw/Cursor-style clients in `agent/mcp_server.py`.
- LangChain OpenAI adapter - Unified chat model client surface in `agent/src/providers/llm.py` and `agent/src/providers/chat.py`.
- LangGraph - Declared orchestration dependency in `pyproject.toml`; direct scanned usage is not prominent in the mapped runtime files, so it is likely supporting agent workflow layers rather than the main FastAPI entrypoint.
- React 19 + React Router 7 - SPA shell and route-level UI in `frontend/src/main.tsx` and `frontend/src/router.tsx`.
- Zustand - Frontend session/chat state store in `frontend/src/stores/agent.ts`.

**Testing:**
- Pytest - Backend/unit/integration test runner configured in `pyproject.toml`, with suites in `agent/tests/`.
- FastAPI TestClient - API regression coverage in files such as `agent/tests/test_settings_api.py`.

**Build/Dev:**
- Vite 6 - Frontend dev server and production bundler in `frontend/package.json` and `frontend/vite.config.ts`.
- TypeScript compiler - Frontend typecheck/build step in `frontend/package.json`.
- Tailwind CSS + PostCSS + Autoprefixer - Styling pipeline in `frontend/tailwind.config.ts` and `frontend/postcss.config.js`.
- Ruff - Python lint configuration in `pyproject.toml`.
- Docker Compose - Local multi-service orchestration in `docker-compose.yml`.

## Key Dependencies

**Critical:**
- `langchain`, `langchain-openai`, `langgraph`, `langgraph-checkpoint` - Agent reasoning/orchestration stack powering chat, tool calling, and swarm-style workflows in `agent/src/providers/llm.py`, `agent/src/providers/chat.py`, and `agent/src/tools/swarm_tool.py`.
- `fastapi`, `uvicorn[standard]`, `sse-starlette`, `python-multipart` - API serving, SSE streaming, and file upload support in `agent/api_server.py`.
- `pydantic` - Request/response contracts and config schemas in `agent/api_server.py` and `agent/src/config/schema.py`.
- `pandas`, `numpy`, `scipy` - Backtest/data processing foundation across `agent/backtest/` and `agent/src/analysis/`.
- `tushare`, `tqsdk`, `yfinance`, `akshare`, `ccxt`, `requests`, `httpx`, `python-socks` - Multi-market data access layer behind market routing and fallback chains in `agent/backtest/loaders/registry.py` and `agent/backtest/loaders/hybrid_fetcher.py`.
- `fastmcp` - External tool integration surface in `agent/mcp_server.py` and MCP client adapter code in `agent/src/tools/mcp.py`.

**Infrastructure:**
- `jinja2`, `matplotlib`, `weasyprint` - HTML/PDF research and shadow-account report generation in `agent/src/shadow_account/reporter.py`.
- `python-docx`, `python-pptx`, `openpyxl`, `pypdfium2`, `Pillow` - Document ingestion for research workflows in `agent/src/tools/doc_reader_tool.py`.
- `ddgs` - DuckDuckGo-backed web search tool in `agent/src/tools/web_search_tool.py`.
- `scikit-learn`, `joblib` - ML/statistical helpers used in research features such as `agent/src/shadow_account/extractor.py`.
- `smartmoneyconcepts`, `pyharmonics` - Specialized signal-analysis support exposed through skill/example engines under `agent/src/skills/smc/` and `agent/src/skills/harmonic/`.
- `duckdb` - Declared in `pyproject.toml`, but direct runtime references were not detected in the mapped files; treat as available dependency rather than a confirmed active path.

## Configuration

**Environment:**
- Main runtime environment is documented in `agent/.env.example` and read through `agent/src/providers/llm.py` plus settings endpoints in `agent/api_server.py`.
- LLM provider selection is environment-driven through `LANGCHAIN_PROVIDER`, `LANGCHAIN_MODEL_NAME`, provider-specific API keys, and provider-specific base URLs defined in `agent/.env.example` and catalogued in `agent/src/providers/llm_providers.json`.
- Data-source credentials and toggles include `TUSHARE_TOKEN`, optional `TQSDK_ACCOUNT`/`TQSDK_PASSWORD`, optional `FUTU_HOST`/`FUTU_PORT`, `CCXT_EXCHANGE`, proxy variables, and runtime cache flags documented in `agent/.env.example` and consumed in `agent/backtest/loaders/*.py`.
- API/server controls include `API_AUTH_KEY`, `CORS_ORIGINS`, `ENABLE_SESSION_RUNTIME`, `VIBE_TRADING_TRUST_DOCKER_LOOPBACK`, and swarm timeouts in `agent/.env.example` and `agent/api_server.py`.

**Build:**
- Python package/build metadata: `pyproject.toml`.
- Docker image build and entrypoint: `Dockerfile`.
- Local container orchestration: `docker-compose.yml`.
- Frontend build config: `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js`.
- CI pipeline: `.github/workflows/test.yml`.

## Platform Requirements

**Development:**
- Python 3.11+ with editable install from `pyproject.toml`.
- Node.js 20 + npm for `frontend/` builds in `.github/workflows/test.yml` and `Dockerfile`.
- Optional local services for richer capabilities: Ollama via `OLLAMA_BASE_URL`, Futu OpenD via `FUTU_HOST`/`FUTU_PORT`, and TqSdk credentials for China futures in `agent/.env.example`.
- Frontend dev server expects backend at `VITE_API_URL` or `http://localhost:8899` via `frontend/vite.config.ts`.

**Production:**
- Primary packaged target is a single Docker image that builds the React frontend, installs the Python backend, serves the SPA from FastAPI, and listens on port `8899` via `Dockerfile`.
- Local/proxy-safe deployment pattern uses loopback-only port exposure in `docker-compose.yml`.
- Separate static wiki deployment targets Cloudflare Pages through `.github/workflows/wiki-deploy.yml`; this is documentation hosting, not the main application runtime.

---

*Stack analysis: 2026-06-03*
