# Phase 10: Empirical Composite Backtest Evidence Closure - Research

**Researched:** 2026-06-07  
**Domain:** empirical composite backtest evidence closure, requirements traceability, reproducible reporting  
**Confidence:** MEDIUM-HIGH — Phase 09 infrastructure and repository patterns were verified from code and planning artifacts; live data availability remains a runtime uncertainty. [VERIFIED: codebase Read]

## User Constraints

No Phase 10 `CONTEXT.md` was found because the Phase 10 directory did not exist before this research run. [VERIFIED: Bash ls] The user supplied the controlling constraints in the research request: Phase 10 is a v2.1 closure/verification phase, not a new feature phase; it must close DATA/RPT empirical evidence and REQUIREMENTS traceability after Phase 09 verified infrastructure and UAT. [VERIFIED: user request]

### Locked Decisions
- Phase 10 is not a new feature phase; it is a v2.1 closure/verification phase. [VERIFIED: user request]
- Phase 10 must address `DATA-01`, `DATA-02`, `DATA-03`, `RPT-01`, `RPT-02`, `RPT-03`, and final empirical-report evidence for `METR-01`, `METR-02`, `METR-03`. [VERIFIED: user request]
- Research must focus on existing commands/files to reuse, likely closure waves, verification commands and expected artifacts, risks/blockers around data availability and reproducibility, and exclusions that belong to Phase 11 Daily Scan Report or future scoring. [VERIFIED: user request]

### Claude's Discretion
- Decide the recommended closure waves and validation architecture for converting Phase 09 infrastructure into empirical evidence. [VERIFIED: user request]
- Decide which existing repository scripts/modules should be reused rather than hand-rolled. [VERIFIED: user request]

### Deferred Ideas (OUT OF SCOPE)
- Daily Scan Report work belongs to Phase 11. [VERIFIED: user request]
- Future scoring/ranking beyond reporting the best fixed strategy variant belongs outside Phase 10. [VERIFIED: user request]

## Summary

Phase 10 should be planned as an evidence-production and traceability-closure phase, not as a strategy implementation phase. [VERIFIED: user request] Phase 09 already introduced the composite backtest comparison command, runner-compatible signal engine, report generation module, metrics helpers, run-card/artifact writing, UAT evidence, and security closure; Phase 10 should reuse those components to run empirical 2024-2026 comparisons, generate final DATA/RPT/METR artifacts, and update requirements traceability. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SUMMARY.md][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-UAT.md][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md]

The most important planning risk is data availability: repository code supports `1D` and `4H` intervals in the runner schema, and the yfinance loader implements `4H` by fetching `1h` bars and resampling, but live `1h` coverage over 2024-2026 may be limited or flaky. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/loaders/yfinance_loader.py] Existing local reports show only partial historical local-cache coverage around 2025-05-27 to 2026-05-08 for selected US futures, not full DATA-01 2024-2026 evidence. [VERIFIED: data_quality_report_20260524_122047.txt][VERIFIED: data_quality_report_20260524_122250.txt]

**Primary recommendation:** Plan Phase 10 as four closure waves: environment/data readiness audit, empirical run matrix execution, final composite report generation, and requirements/UAT evidence closure; do not add new strategy logic, daily scan reporting, or future scoring. [VERIFIED: codebase Read][VERIFIED: user request]

## Project Constraints (from CLAUDE.md)

| Directive | Planning Impact |
|-----------|-----------------|
| Python projects use PEP 8, type hints, docstrings, pytest, black, and >80% coverage. [CITED: /Users/iagent/projects/CLAUDE.md] | Any support script or small closure helper should be typed, simple, and test-backed. [CITED: /Users/iagent/projects/CLAUDE.md] |
| Git commit messages follow `<type>: <description>` with types including `feat`, `fix`, `refactor`, `test`, `docs`. [CITED: /Users/iagent/projects/CLAUDE.md] | If the planner includes commit tasks, use conventional commit style. [CITED: /Users/iagent/projects/CLAUDE.md] |
| Precision changes are required: every changed line must directly trace to the user request. [CITED: /Users/iagent/projects/CLAUDE.md] | Phase 10 tasks should avoid opportunistic refactors. [CITED: /Users/iagent/projects/CLAUDE.md] |
| Avoid over-engineering and keep the simple solution. [CITED: /Users/iagent/projects/CLAUDE.md] | Prefer run manifests and reports over new orchestration frameworks. [CITED: /Users/iagent/projects/CLAUDE.md] |
| Tests should be run after modifications. [CITED: /Users/iagent/projects/CLAUDE.md] | Each wave should include targeted tests plus empirical artifact checks. [CITED: /Users/iagent/projects/CLAUDE.md] |
| Sensitive information such as API keys and passwords must not be committed; `.env` is used for configuration. [CITED: /Users/iagent/projects/CLAUDE.md] | Data-source credentials such as `TUSHARE_TOKEN` and `TQSDK_ACCOUNT`/`TQSDK_PASSWORD` must remain env-only. [CITED: /Users/iagent/projects/CLAUDE.md][VERIFIED: agent/backtest/loaders/tushare.py][VERIFIED: agent/backtest/loaders/tqsdk_loader.py] |

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Use near two-year data for 2024-2026. [VERIFIED: .planning/REQUIREMENTS.md] | Existing composite config uses `start_date: "2024-01-01"` and `end_date: "2026-01-01"`; Phase 10 must execute and preserve run cards/artifacts proving actual data rows and date ranges. [VERIFIED: agent/backtest/configs/composite_backtest.yaml][VERIFIED: agent/backtest/run_card.py] |
| DATA-02 | Cover main watchlist instruments, including futures/ETF. [VERIFIED: .planning/REQUIREMENTS.md] | `watchlist/us_futures_watchlist.csv` has 8 US futures with `1D-4H`; `watchlist/etf_watchlist.csv` has 35 ETF/stock/HK entries mostly declared as `1W-1D`. [VERIFIED: watchlist/us_futures_watchlist.csv][VERIFIED: watchlist/etf_watchlist.csv] |
| DATA-03 | Support `1D` and `4H` timeframes. [VERIFIED: .planning/REQUIREMENTS.md] | Runner validates `1D` and `4H`; yfinance supports `4H` by fetching `1h` and resampling. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/loaders/yfinance_loader.py] |
| METR-01 | Compare composite strategy return against single strategies. [VERIFIED: .planning/REQUIREMENTS.md] | `composite_backtest_compare.py` runs `MTES+SuperTrend`, `MTESv3-only`, and `SuperTrend-only` variants and writes a comparison report. [VERIFIED: agent/backtest/composite_backtest_compare.py] |
| METR-02 | Record win rate, Sharpe, and max drawdown metrics. [VERIFIED: .planning/REQUIREMENTS.md] | `calc_metrics()` produces performance metrics, and comparison/report modules include win rate, return, max drawdown, and Sharpe-style fields. [VERIFIED: agent/backtest/metrics.py][VERIFIED: agent/backtest/strategies/comparison.py][VERIFIED: agent/backtest/reporting/composite_report.py] |
| METR-03 | Record per-source independent performance/signal breakdown. [VERIFIED: .planning/REQUIREMENTS.md] | `signals_per_source.json` is written when the signal engine exposes composite output, and `generate_composite_report()` renders `Per-Source Performance (METR-03)`. [VERIFIED: agent/backtest/engines/base.py][VERIFIED: agent/backtest/reporting/composite_report.py] |
| RPT-01 | Generate composite-vs-single comparison report. [VERIFIED: .planning/REQUIREMENTS.md] | `run_comparison()` writes `comparison_report.md`; `generate_composite_report()` renders `Strategy Comparison (RPT-01)`. [VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/reporting/composite_report.py] |
| RPT-02 | Identify the best strategy combination. [VERIFIED: .planning/REQUIREMENTS.md] | `StrategyComparator` can rank variants, and `generate_composite_report()` renders `Best Configuration (RPT-02)`. [VERIFIED: agent/backtest/strategies/comparison.py][VERIFIED: agent/backtest/reporting/composite_report.py] |
| RPT-03 | Record data quality and completeness checks. [VERIFIED: .planning/REQUIREMENTS.md] | `check_watchlist_data()` and run-card artifact metadata can supply quality/completeness evidence; `generate_composite_report()` renders `Data Quality (RPT-03)`. [VERIFIED: agent/src/data/watchlist_data_health.py][VERIFIED: scripts/check_watchlist_data.py][VERIFIED: agent/backtest/run_card.py][VERIFIED: agent/backtest/reporting/composite_report.py] |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Empirical composite-vs-single backtest execution | Backend / Batch CLI | Data loaders | The comparison CLI prepares runner dirs and invokes `python -m backtest.runner` for each variant. [VERIFIED: agent/backtest/composite_backtest_compare.py] |
| Market data acquisition | Data / Storage boundary | Backend / Batch CLI | Backtest runner loads OHLCV through registered loaders and then writes artifacts. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/loaders/registry.py] |
| Metrics calculation | Backend / Domain logic | Artifacts | Metrics are computed in backtest metrics and strategy-comparison modules, then serialized to run artifacts. [VERIFIED: agent/backtest/metrics.py][VERIFIED: agent/backtest/strategies/comparison.py][VERIFIED: agent/backtest/engines/base.py] |
| Final empirical report generation | Backend / Reporting | Artifacts | `generate_composite_report()` consumes run dirs/run cards and emits Markdown report sections for RPT/METR closure. [VERIFIED: agent/backtest/reporting/composite_report.py] |
| Requirements traceability closure | Planning / Documentation | Backend artifact references | `.planning/REQUIREMENTS.md` currently marks all v2.1 requirements Pending, so closure requires linking generated artifacts back to requirements. [VERIFIED: .planning/REQUIREMENTS.md] |
| Security guard preservation | Backend / Batch CLI | Environment config | Runner and comparison code enforce trusted signal-engine hashes, safe run roots, safe YAML loading, output limits, and timeout/redaction behavior. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md] |

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Python | 3.11+ project constraint; environment probe saw Python 3.14.4. [CITED: /Users/iagent/projects/CLAUDE.md][VERIFIED: Bash python3 --version] | Execute repository backtest and reporting CLIs. | Existing project is Python-based and backtest modules are Python packages. [VERIFIED: pyproject.toml][VERIFIED: agent/backtest/runner.py] |
| `backtest.runner` | repo module | Execute configured backtests and emit run artifacts. | Existing Phase 09 infrastructure is built around `python -m backtest.runner <run_dir>`. [VERIFIED: agent/backtest/runner.py][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SUMMARY.md] |
| `backtest.composite_backtest_compare` | repo module | Run composite and single-strategy variants. | It already prepares variant run dirs and writes `comparison_report.md`. [VERIFIED: agent/backtest/composite_backtest_compare.py] |
| `backtest.reporting.composite_report` | repo module | Generate RPT/METR closure Markdown. | It renders RPT-01, RPT-02, METR-03, and RPT-03 sections from run dirs. [VERIFIED: agent/backtest/reporting/composite_report.py] |
| `agent/backtest/configs/signal_engine.py` | repo module | Runner-compatible composite signal engine. | The comparison command copies this packaged engine into each run dir. [VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/configs/signal_engine.py] |
| `scripts/check_watchlist_data.py` | repo script | Local data completeness/quality gate. | It writes table/JSON data-health reports and returns nonzero when local data cannot support backtest. [VERIFIED: scripts/check_watchlist_data.py] |

### Supporting

| Library / Module | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| `yfinance` | dependency declared in `pyproject.toml`; exact installed version not verified in this session. [VERIFIED: pyproject.toml][ASSUMED] | No-auth US futures/ETF data loader. | Use for US futures and ETF empirical runs when live network/proxy is available. [VERIFIED: agent/backtest/loaders/yfinance_loader.py] |
| `akshare` | dependency declared in `pyproject.toml`; exact installed version not verified in this session. [VERIFIED: pyproject.toml][ASSUMED] | No-auth daily data fallback for US/CN futures and ETFs. | Use as fallback for daily data only; AKShare loader notes US/CN futures paths return daily data only. [VERIFIED: agent/backtest/loaders/akshare_loader.py] |
| `tqsdk` | dependency declared in `pyproject.toml`; exact installed version not verified in this session. [VERIFIED: pyproject.toml][ASSUMED] | CN futures loader with `1D`, `1H`, and `4H` duration support. | Use only if credentials/environment are available; loader marks `requires_auth = True`. [VERIFIED: pyproject.toml][VERIFIED: agent/backtest/loaders/tqsdk_loader.py] |
| `tushare` | dependency declared in `pyproject.toml`; exact installed version not verified in this session. [VERIFIED: pyproject.toml][ASSUMED] | A-share/fund/futures data loader. | Avoid for Phase 10 unless `TUSHARE_TOKEN` is configured; loader requires env token. [VERIFIED: agent/backtest/loaders/tushare.py] |
| `pandas` / `numpy` | dependencies declared in `pyproject.toml`; exact installed versions not verified in this session. [VERIFIED: pyproject.toml][ASSUMED] | Metrics, dataframes, resampling, and artifact writing. | Already used throughout backtest and data-health code. [VERIFIED: agent/backtest/metrics.py][VERIFIED: agent/backtest/loaders/yfinance_loader.py] |
| `pytest` | dependency declared in `pyproject.toml`; environment probe did not produce a `pytest --version` line. [VERIFIED: pyproject.toml][VERIFIED: Bash environment audit] | Targeted regression validation. | Use after environment setup; do not assume PATH-level `pytest` exists in this isolated worktree. [VERIFIED: Bash environment audit] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Live yfinance 4H for full 2024-2026 | 1D full-period plus shorter 4H availability report | Full-period 4H may fail because repository yfinance 4H is resampled from 1h bars; record limitation rather than fabricating coverage. [VERIFIED: agent/backtest/loaders/yfinance_loader.py][ASSUMED] |
| CN futures inclusion | US futures + ETF empirical closure | CN futures loaders may require TqSdk/Tushare credentials; US futures/ETF have no-auth yfinance paths. [VERIFIED: agent/backtest/loaders/tqsdk_loader.py][VERIFIED: agent/backtest/loaders/tushare.py][VERIFIED: agent/backtest/loaders/yfinance_loader.py] |
| Existing signal-only `scripts/backtest_composite_strategy.py` | Backtest runner + comparison + composite report modules | The script is a separate signal-level empirical script and does not produce runner run cards or the RPT sections Phase 10 needs. [VERIFIED: scripts/backtest_composite_strategy.py][VERIFIED: agent/backtest/reporting/composite_report.py] |

**Installation:** No new packages should be installed in Phase 10. [VERIFIED: user request][VERIFIED: pyproject.toml]

**Version verification:** No new package versions were verified because Phase 10 should reuse the existing project environment and not add dependencies. [VERIFIED: pyproject.toml][VERIFIED: user request]

## Package Legitimacy Audit

Not applicable: this phase should install no external packages. [VERIFIED: user request] If the planner introduces a new dependency, it must run the GSD package legitimacy gate before installation. [ASSUMED]

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| None | — | — | — | — | — | No install planned. [VERIFIED: user request] |

**Packages removed due to slopcheck [SLOP] verdict:** none. [VERIFIED: no package install planned]  
**Packages flagged as suspicious [SUS]:** none. [VERIFIED: no package install planned]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 10 closure request
  |
  v
Wave 0: Environment + data readiness audit
  |-- check Python/project env ------------------------------------|
  |-- check local watchlist data health ---------------------------|
  |-- record live-data credential/network limitations -------------|
  v                                                               |
Empirical run matrix manifest                                      |
  |                                                               |
  |-- US futures 1D 2024-2026 config ------------------------------|
  |-- US futures 4H config / availability-limited config ----------|
  |-- ETF 1D sample config if DATA-02 needs ETF evidence ----------|
  v                                                               |
`python -m backtest.composite_backtest_compare --config ...`        |
  |                                                               |
  |-- Variant A: MTES+SuperTrend -> `backtest.runner` -------------|
  |-- Variant B: MTESv3-only     -> `backtest.runner` -------------|
  |-- Variant C: SuperTrend-only -> `backtest.runner` -------------|
  v                                                               |
Run dirs + artifacts                                               |
  |-- run_card.json / run_card.md ---------------------------------|
  |-- equity.csv / metrics.csv / trades.csv -----------------------|
  |-- signals_key_nodes.csv / signals_per_source.json -------------|
  v                                                               |
`generate_composite_report(run_dirs, CompositeReportConfig)`        |
  |                                                               |
  |-- Strategy Comparison (RPT-01, METR-01/02) --------------------|
  |-- Best Configuration (RPT-02) ---------------------------------|
  |-- Per-Source Performance (METR-03) ----------------------------|
  |-- Data Quality (RPT-03, DATA-01/02/03 caveats) ----------------|
  v                                                               |
Final empirical report + REQUIREMENTS traceability update
```

This architecture follows existing runner, comparison, report, metrics, and run-card boundaries. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/reporting/composite_report.py][VERIFIED: agent/backtest/run_card.py]

### Recommended Project Structure

```text
.planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/
├── 10-RESEARCH.md                         # this research artifact [VERIFIED: user request]
├── 10-PLAN.md                             # planner output [ASSUMED]
├── 10-UAT.md                              # closure acceptance results [ASSUMED]
├── 10-SUMMARY.md                          # final closure summary [ASSUMED]
└── artifacts/                             # empirical closure evidence [ASSUMED]
    ├── data_health_us_futures.json
    ├── data_health_etf.json
    ├── run_manifest.json
    ├── empirical_composite_report.md
    └── requirements_traceability.md

agent/runs/composite_compare/phase10-*/
├── comparison_report.md
├── MTES_SuperTrend/...
├── MTESv3_only/...
└── SuperTrend_only/...
```

The `agent/runs/...` run-root location is compatible with default safe run roots. [VERIFIED: agent/src/tools/path_utils.py] The `artifacts/` folder under Phase 10 planning is a recommended evidence aggregation location, not an existing repository convention verified before this phase. [ASSUMED]

### Pattern 1: Run matrix as evidence manifest

**What:** Create explicit run configs and a manifest listing symbols, interval, date range, source, run root, commands, and expected artifacts. [ASSUMED]  
**When to use:** Use for every empirical closure run so DATA/RPT/METR evidence can be traced without re-reading logs. [ASSUMED]  
**Example:**

```json
{
  "requirement_ids": ["DATA-01", "DATA-02", "DATA-03", "METR-01", "METR-02", "METR-03", "RPT-01", "RPT-02", "RPT-03"],
  "runs": [
    {
      "name": "us_futures_1d_2024_2026",
      "config": "agent/backtest/configs/phase10_us_futures_1d.yaml",
      "source": "yfinance",
      "interval": "1D",
      "start_date": "2024-01-01",
      "end_date": "2026-01-01",
      "symbols": ["GC=F", "SI=F", "CL=F"],
      "expected_artifacts": ["comparison_report.md", "run_card.json", "artifacts/metrics.csv", "artifacts/signals_per_source.json"]
    }
  ]
}
```

Source pattern: comparison configs already use YAML with `codes`, date range, source, interval, and strategy settings. [VERIFIED: agent/backtest/configs/composite_backtest.yaml]

### Pattern 2: Generate final report from run dirs, not from logs

**What:** Use `generate_composite_report(run_dirs, CompositeReportConfig)` after empirical run dirs exist. [VERIFIED: agent/backtest/reporting/composite_report.py]  
**When to use:** Use after each comparison command creates run dirs for composite and single variants. [VERIFIED: agent/backtest/composite_backtest_compare.py]  
**Example:**

```python
from pathlib import Path
from backtest.reporting.composite_report import CompositeReportConfig, generate_composite_report

report = generate_composite_report(
    [
        ("MTES+SuperTrend 1D", Path("agent/runs/composite_compare/phase10-us-futures-1d/MTES_SuperTrend")),
        ("MTESv3-only 1D", Path("agent/runs/composite_compare/phase10-us-futures-1d/MTESv3_only")),
        ("SuperTrend-only 1D", Path("agent/runs/composite_compare/phase10-us-futures-1d/SuperTrend_only")),
    ],
    CompositeReportConfig(
        symbol="US futures watchlist sample",
        period="2024-01-01 to 2026-01-01",
        data_quality_notes="Attach watchlist health JSON and run-card warnings."
    ),
)
Path(".planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/empirical_composite_report.md").write_text(report, encoding="utf-8")
```

This exact wrapper file does not currently exist; it is a small closure helper pattern based on verified report APIs. [VERIFIED: agent/backtest/reporting/composite_report.py][ASSUMED]

### Pattern 3: Treat data-quality gaps as evidence, not as silent failures

**What:** Capture `scripts/check_watchlist_data.py` JSON output and run-card warnings into final RPT-03 evidence. [VERIFIED: scripts/check_watchlist_data.py][VERIFIED: agent/backtest/run_card.py]  
**When to use:** Use before and after empirical runs to explain missing symbols/timeframes or degraded data. [ASSUMED]  
**Example command:**

```bash
python scripts/check_watchlist_data.py \
  --watchlist watchlist/us_futures_watchlist.csv \
  --data-dir data \
  --format both \
  --json-output .planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data_health_us_futures.json
```

The script supports `--watchlist`, `--data-dir`, `--format`, and `--json-output`. [VERIFIED: scripts/check_watchlist_data.py]

### Anti-Patterns to Avoid

- **Treating Phase 09 smoke tests as DATA/RPT closure:** Phase 09 UAT confirms infrastructure behavior, while Phase 10 must produce final empirical evidence artifacts. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-UAT.md][VERIFIED: user request]
- **Hand-writing report tables:** Use `StrategyComparator`, `calc_metrics()`, run cards, and `generate_composite_report()` to avoid mismatched metric semantics. [VERIFIED: agent/backtest/strategies/comparison.py][VERIFIED: agent/backtest/metrics.py][VERIFIED: agent/backtest/reporting/composite_report.py]
- **Relying on `source: auto` for US futures without validation:** Explicit `source: yfinance` is safer for US futures/ETF closure because the reference composite config already uses yfinance and loader support is verified. [VERIFIED: agent/backtest/configs/composite_backtest.yaml][VERIFIED: agent/backtest/loaders/yfinance_loader.py]
- **Forcing CN futures into closure without credentials:** TqSdk and Tushare paths require credentials or tokens, so they can block reproducibility. [VERIFIED: agent/backtest/loaders/tqsdk_loader.py][VERIFIED: agent/backtest/loaders/tushare.py]
- **Expanding into Phase 11 Daily Scan Report:** User explicitly scoped Daily Scan Report out of Phase 10. [VERIFIED: user request]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Composite-vs-single orchestration | A new custom loop over strategies | `backtest.composite_backtest_compare.run_comparison()` / CLI | Existing code already prepares per-variant run dirs, copies the trusted engine, runs `backtest.runner`, and writes `comparison_report.md`. [VERIFIED: agent/backtest/composite_backtest_compare.py] |
| Backtest execution | Direct calls into strategy classes | `python -m backtest.runner <run_dir>` | Runner enforces config schema, safe run dirs, trusted signal engines, data limits, and artifact writing. [VERIFIED: agent/backtest/runner.py] |
| Metrics calculations | Manual Sharpe/drawdown/win-rate tables | `calc_metrics()` and `StrategyComparator` | Existing modules already standardize metric names and comparison output. [VERIFIED: agent/backtest/metrics.py][VERIFIED: agent/backtest/strategies/comparison.py] |
| RPT-01/RPT-02/RPT-03 report sections | Ad-hoc Markdown report generation | `generate_composite_report()` | The report module emits named sections for strategy comparison, best configuration, per-source performance, and data quality. [VERIFIED: agent/backtest/reporting/composite_report.py] |
| Data completeness checks | Custom CSV/parquet scanners | `scripts/check_watchlist_data.py` / `check_watchlist_data()` | Existing data-health code has timeframe aliases, stale thresholds, blocking vs warning logic, and JSON output. [VERIFIED: agent/src/data/watchlist_data_health.py][VERIFIED: scripts/check_watchlist_data.py] |
| Reproducibility metadata | Manual hashes in notes | `run_card.json` / `run_card.md` | Run cards include config hash, strategy hash, data sources, metrics, warnings, and artifact hashes. [VERIFIED: agent/backtest/run_card.py] |

**Key insight:** Phase 10’s value is evidence integrity, not new infrastructure; custom reimplementation would weaken traceability and bypass Phase 09 security controls. [VERIFIED: user request][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md]

## Common Pitfalls

### Pitfall 1: 4H over 2024-2026 may not be available from yfinance

**What goes wrong:** A full 2024-2026 `4H` run may fail or return incomplete data. [ASSUMED]  
**Why it happens:** The yfinance loader maps `4H` to `1h` downloads and resamples to `4h`, so `4H` depends on intraday `1h` availability. [VERIFIED: agent/backtest/loaders/yfinance_loader.py]  
**How to avoid:** Plan a data-availability gate before claiming DATA-03; if full-period 4H fails, record the limitation in RPT-03 and produce the maximum reproducible 4H evidence instead of silently substituting 1D. [ASSUMED]  
**Warning signs:** Empty run-card data sources, missing `equity.csv`, no `ohlcv_*.csv`, or `Data Quality (RPT-03)` warnings. [VERIFIED: agent/backtest/run_card.py][VERIFIED: agent/backtest/reporting/composite_report.py]

### Pitfall 2: Existing local data reports do not prove DATA-01

**What goes wrong:** Planner may cite existing May 2026 local data reports as 2024-2026 closure evidence. [ASSUMED]  
**Why it happens:** Existing data-quality text reports cover selected US futures from 2025-05-27 to 2026-05-08 and include failures for `vibe (cache)`. [VERIFIED: data_quality_report_20260524_122047.txt][VERIFIED: data_quality_report_20260524_122250.txt]  
**How to avoid:** Use them only as historical context; create Phase 10 run cards and reports from the actual 2024-2026 run matrix. [ASSUMED]  
**Warning signs:** Final evidence references only `data_quality_report_20260524_*` instead of Phase 10 artifact paths. [ASSUMED]

### Pitfall 3: `comparison_report.md` alone may not close RPT-03/METR-03

**What goes wrong:** The comparison CLI writes `comparison_report.md`, but the richer report sections for per-source performance and data quality live in `generate_composite_report()`. [VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/reporting/composite_report.py]  
**Why it happens:** `run_comparison()` returns `generate_standard_report(comparator)` output, while `composite_report.py` separately renders `Per-Source Performance (METR-03)` and `Data Quality (RPT-03)`. [VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/reporting/composite_report.py]  
**How to avoid:** Include an explicit Wave 3 task that calls `generate_composite_report()` from the run dirs created by the comparison CLI. [ASSUMED]  
**Warning signs:** Final artifact has no `## Per-Source Performance (METR-03)` or `## Data Quality (RPT-03)` headings. [VERIFIED: agent/backtest/reporting/composite_report.py]

### Pitfall 4: Stale requirements status can hide closure gaps

**What goes wrong:** Phase 09 appears complete in UAT/security, but `.planning/REQUIREMENTS.md` still marks all v2.1 requirements Pending. [VERIFIED: .planning/REQUIREMENTS.md][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-UAT.md]  
**Why it happens:** Infrastructure implementation and final empirical evidence are separate closure states. [VERIFIED: user request]  
**How to avoid:** Plan a final traceability update that maps each requirement to exact Phase 10 artifact paths and marks status only after artifacts exist. [ASSUMED]  
**Warning signs:** `REQUIREMENTS.md` stays Pending after empirical reports are generated. [VERIFIED: .planning/REQUIREMENTS.md]

### Pitfall 5: Environment assumptions may fail in this worktree

**What goes wrong:** Planner may assume `.venv/bin/python` and PATH-level `pytest` exist. [ASSUMED]  
**Why it happens:** Environment probe printed system `Python 3.14.4` and did not show `.venv/bin/python` or `pytest --version` output in this isolated worktree. [VERIFIED: Bash environment audit]  
**How to avoid:** Wave 0 should verify or create/use the correct project environment before empirical runs. [ASSUMED]  
**Warning signs:** Import errors for `pandas`, `yfinance`, `akshare`, or `pytest`. [ASSUMED]

## Code Examples

Verified patterns from repository sources:

### Empirical comparison CLI

```bash
PYTHONPATH=agent python -m backtest.composite_backtest_compare \
  --config agent/backtest/configs/composite_backtest.yaml \
  --run-root agent/runs/composite_compare/phase10-us-futures-1d \
  --timeout-seconds 300
```

The CLI supports `--config`, `--run-root`, and `--timeout-seconds`. [VERIFIED: agent/backtest/composite_backtest_compare.py] The run root must pass `safe_run_dir` constraints. [VERIFIED: agent/src/tools/path_utils.py]

### Watchlist data-health evidence

```bash
python scripts/check_watchlist_data.py \
  --watchlist watchlist/us_futures_watchlist.csv \
  --data-dir data \
  --format both \
  --json-output .planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/data_health_us_futures.json
```

The script writes JSON output when `--json-output` is supplied and returns 0 only when `report.can_backtest` is true. [VERIFIED: scripts/check_watchlist_data.py]

### Final composite report generation helper

```python
from pathlib import Path
from backtest.reporting.composite_report import CompositeReportConfig, generate_composite_report

run_root = Path("agent/runs/composite_compare/phase10-us-futures-1d")
report = generate_composite_report(
    [
        ("MTES+SuperTrend", run_root / "MTES_SuperTrend"),
        ("MTESv3-only", run_root / "MTESv3_only"),
        ("SuperTrend-only", run_root / "SuperTrend_only"),
    ],
    CompositeReportConfig(
        symbol="US futures watchlist sample",
        period="2024-01-01 to 2026-01-01",
        data_quality_notes="See data_health_us_futures.json and run_card.json warnings.",
    ),
)
Path(".planning/phases/10-close-gap-data-rpt-empirical-composite-backtest-validation/artifacts/empirical_composite_report.md").write_text(report, encoding="utf-8")
```

`generate_composite_report()` accepts `List[Tuple[str, Path]]` and an optional `CompositeReportConfig`. [VERIFIED: agent/backtest/reporting/composite_report.py]

### Targeted validation commands

```bash
python -m py_compile \
  agent/backtest/runner.py \
  agent/backtest/composite_backtest_compare.py \
  agent/backtest/reporting/composite_report.py \
  agent/backtest/configs/signal_engine.py
```

These files are the primary Phase 10 execution/reporting surface. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/reporting/composite_report.py][VERIFIED: agent/backtest/configs/signal_engine.py]

```bash
python -m pytest -q \
  agent/tests/test_composite_backtest_compare.py \
  agent/tests/test_metrics.py \
  agent/tests/test_watchlist_data_health.py \
  agent/tests/test_backtest_runner_security.py
```

The listed test files cover comparison orchestration/security behavior, metrics, data-health gate behavior, and runner security controls. [VERIFIED: agent/tests/test_composite_backtest_compare.py][VERIFIED: agent/tests/test_metrics.py][VERIFIED: agent/tests/test_watchlist_data_health.py][VERIFIED: agent/tests/test_backtest_runner_security.py]

## Likely Closure Plan / Waves

### Wave 0 — Environment and data readiness audit

| Task | Output | Requirement Support |
|------|--------|---------------------|
| Verify Python environment, dependency importability, and pytest availability. [ASSUMED] | `artifacts/environment.json` or equivalent. [ASSUMED] | Prevents false execution failures. [ASSUMED] |
| Run `scripts/check_watchlist_data.py` for US futures and ETF watchlists. [VERIFIED: scripts/check_watchlist_data.py] | `data_health_us_futures.json`, `data_health_etf.json`. [ASSUMED] | RPT-03, DATA-02, DATA-03. [VERIFIED: .planning/REQUIREMENTS.md] |
| Decide empirical matrix based on actual availability. [ASSUMED] | `run_manifest.json`. [ASSUMED] | DATA-01/02/03 traceability. [ASSUMED] |

### Wave 1 — Create empirical configs/manifests

| Task | Output | Requirement Support |
|------|--------|---------------------|
| Create US futures 1D config using 2024-01-01 to 2026-01-01 and yfinance. [VERIFIED: agent/backtest/configs/composite_backtest.yaml] | `phase10_us_futures_1d.yaml`. [ASSUMED] | DATA-01, DATA-02, DATA-03. [VERIFIED: .planning/REQUIREMENTS.md] |
| Create US futures 4H config or documented fallback if unavailable. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/loaders/yfinance_loader.py] | `phase10_us_futures_4h.yaml` and/or availability note. [ASSUMED] | DATA-03, RPT-03. [VERIFIED: .planning/REQUIREMENTS.md] |
| Create ETF 1D sample config if DATA-02 requires ETF-specific empirical evidence. [VERIFIED: watchlist/etf_watchlist.csv][VERIFIED: agent/backtest/loaders/yfinance_loader.py] | `phase10_etf_1d.yaml`. [ASSUMED] | DATA-02. [VERIFIED: .planning/REQUIREMENTS.md] |

### Wave 2 — Execute empirical comparison runs

| Task | Output | Requirement Support |
|------|--------|---------------------|
| Run `backtest.composite_backtest_compare` for each config. [VERIFIED: agent/backtest/composite_backtest_compare.py] | `agent/runs/composite_compare/phase10-*` run trees and `comparison_report.md`. [ASSUMED] | METR-01/02, RPT-01/02. [VERIFIED: .planning/REQUIREMENTS.md] |
| Verify per-variant run cards and artifacts exist. [VERIFIED: agent/backtest/engines/base.py][VERIFIED: agent/backtest/run_card.py] | `run_card.json`, `metrics.csv`, `equity.csv`, `signals_per_source.json`. [ASSUMED] | METR-02/03, RPT-03. [VERIFIED: .planning/REQUIREMENTS.md] |
| Capture failures as reproducibility limitations, not silent skips. [ASSUMED] | `run_manifest.json` statuses and warnings. [ASSUMED] | RPT-03. [VERIFIED: .planning/REQUIREMENTS.md] |

### Wave 3 — Generate final empirical closure report

| Task | Output | Requirement Support |
|------|--------|---------------------|
| Use `generate_composite_report()` over successful run dirs. [VERIFIED: agent/backtest/reporting/composite_report.py] | `artifacts/empirical_composite_report.md`. [ASSUMED] | RPT-01/02/03, METR-01/02/03. [VERIFIED: .planning/REQUIREMENTS.md] |
| Add data-quality notes from health JSON, run-card warnings, and interval limitations. [VERIFIED: scripts/check_watchlist_data.py][VERIFIED: agent/backtest/run_card.py] | Data Quality section. [VERIFIED: agent/backtest/reporting/composite_report.py] | RPT-03, DATA-01/02/03. [VERIFIED: .planning/REQUIREMENTS.md] |
| Confirm report contains required headings. [VERIFIED: agent/backtest/reporting/composite_report.py] | heading check result. [ASSUMED] | RPT closure. [ASSUMED] |

### Wave 4 — Requirements/UAT closure

| Task | Output | Requirement Support |
|------|--------|---------------------|
| Update `.planning/REQUIREMENTS.md` traceability from Pending to artifact-linked status. [VERIFIED: .planning/REQUIREMENTS.md] | Requirements traceability table with Phase 10 artifact paths. [ASSUMED] | All scoped requirements. [VERIFIED: user request] |
| Create Phase 10 UAT with artifact checks and command results. [ASSUMED] | `10-UAT.md`. [ASSUMED] | Evidence for closure. [ASSUMED] |
| Run targeted regression and compile checks. [ASSUMED] | command transcript / UAT evidence. [ASSUMED] | Prevents closure regressions. [ASSUMED] |

## Expected Artifacts

| Artifact | Producer | Closure Role |
|----------|----------|--------------|
| `artifacts/data_health_us_futures.json` | `scripts/check_watchlist_data.py` [VERIFIED: scripts/check_watchlist_data.py] | DATA-02/DATA-03/RPT-03 data health evidence. [ASSUMED] |
| `artifacts/data_health_etf.json` | `scripts/check_watchlist_data.py` [VERIFIED: scripts/check_watchlist_data.py] | ETF coverage evidence for DATA-02 if ETF empirical closure is included. [ASSUMED] |
| `artifacts/run_manifest.json` | small Phase 10 closure helper [ASSUMED] | Maps requirements to configs, commands, run roots, and status. [ASSUMED] |
| `agent/runs/composite_compare/phase10-*/comparison_report.md` | `backtest.composite_backtest_compare` [VERIFIED: agent/backtest/composite_backtest_compare.py] | RPT-01/RPT-02 and METR-01/METR-02 source comparison evidence. [ASSUMED] |
| `agent/runs/composite_compare/phase10-*/*/run_card.json` | `write_run_card()` [VERIFIED: agent/backtest/run_card.py] | Reproducibility evidence: config hash, strategy hash, metrics, warnings, artifact hashes. [VERIFIED: agent/backtest/run_card.py] |
| `agent/runs/composite_compare/phase10-*/*/artifacts/signals_per_source.json` | `_write_signal_engine_artifacts()` [VERIFIED: agent/backtest/engines/base.py] | METR-03 per-source signal evidence. [VERIFIED: agent/backtest/reporting/composite_report.py] |
| `artifacts/empirical_composite_report.md` | `generate_composite_report()` [VERIFIED: agent/backtest/reporting/composite_report.py] | Final human-readable DATA/RPT/METR closure report. [ASSUMED] |
| `.planning/REQUIREMENTS.md` updated traceability | Phase 10 docs update [ASSUMED] | Formal closure status for the requirements originally Pending. [VERIFIED: .planning/REQUIREMENTS.md] |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Signal-only comparison script over local parquet files. [VERIFIED: scripts/backtest_composite_strategy.py] | Runner-based comparison with run cards, artifacts, and strategy variants. [VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/run_card.py] | Phase 09. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SUMMARY.md] | Phase 10 should use runner evidence, not standalone signal printouts. [ASSUMED] |
| Infrastructure smoke/UAT evidence. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-UAT.md] | Empirical DATA/RPT closure with artifact-linked traceability. [VERIFIED: user request] | Phase 10. [VERIFIED: user request] | Planner should create evidence-producing waves rather than feature-building waves. [ASSUMED] |
| Ad-hoc data quality text reports. [VERIFIED: data_quality_report_20260524_122047.txt][VERIFIED: data_quality_report_20260524_122250.txt] | JSON data-health plus run-card warnings plus report Data Quality section. [VERIFIED: scripts/check_watchlist_data.py][VERIFIED: agent/backtest/run_card.py][VERIFIED: agent/backtest/reporting/composite_report.py] | Phase 10 closure plan. [ASSUMED] | RPT-03 becomes reproducible and machine-checkable. [ASSUMED] |

**Deprecated/outdated for Phase 10:**
- `scripts/backtest_composite_strategy.py` as primary closure evidence: it does not generate runner run cards or RPT-01/RPT-02/RPT-03 sections. [VERIFIED: scripts/backtest_composite_strategy.py][VERIFIED: agent/backtest/reporting/composite_report.py]
- Existing `watchlist_report.md` / `etf_report.md` as closure evidence: these are watchlist analysis reports, not composite backtest evidence reports. [VERIFIED: watchlist_report.md][VERIFIED: etf_report.md]
- Existing May 2026 data-quality text reports as DATA-01 closure: they do not cover the full 2024-2026 requirement. [VERIFIED: data_quality_report_20260524_122047.txt][VERIFIED: data_quality_report_20260524_122250.txt]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Full-period yfinance 4H may fail because it depends on intraday 1h availability. | Common Pitfalls | Planner may overstate DATA-03 closure; must validate empirically. |
| A2 | A small closure helper script may be needed to call `generate_composite_report()` and write final Phase 10 artifacts. | Architecture Patterns / Closure Waves | Planner may under-scope Wave 3 if no helper is needed or if existing CLI is extended instead. |
| A3 | Phase 10 artifacts should live under the Phase 10 planning directory for traceability. | Recommended Project Structure | Repository may prefer another artifact convention. |
| A4 | ETF 1D sample is sufficient for ETF side of DATA-02 if full ETF watchlist is too broad. | Closure Waves | User may require broader ETF empirical coverage. |
| A5 | Environment setup may be needed because `.venv` and PATH `pytest` were not available in the isolated worktree probe. | Environment Availability | Planner may need to adjust commands for actual executor environment. |

## Open Questions

1. **What minimum symbol coverage qualifies as “main watchlist instruments” for DATA-02?** [VERIFIED: .planning/REQUIREMENTS.md]
   - What we know: US futures watchlist has 8 instruments with `1D-4H`; ETF watchlist has 35 entries mostly `1W-1D`. [VERIFIED: watchlist/us_futures_watchlist.csv][VERIFIED: watchlist/etf_watchlist.csv]
   - What's unclear: Whether DATA-02 requires all watchlist symbols or a representative sample. [ASSUMED]
   - Recommendation: Plan full US futures 1D sample if runtime allows, a smaller US futures 4H sample if 4H data is constrained, and optional ETF 1D sample for ETF evidence. [ASSUMED]

2. **How should Phase 10 represent 4H if full 2024-2026 intraday data is unavailable?** [ASSUMED]
   - What we know: Runner supports `4H`; yfinance loader resamples `1h` to `4h`. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/loaders/yfinance_loader.py]
   - What's unclear: Actual live provider retention and network behavior in the execution environment. [ASSUMED]
   - Recommendation: Treat failed/partial 4H as RPT-03 data-quality evidence and document exact coverage obtained. [ASSUMED]

3. **Should the Phase 10 planner fix the `StrategyComparator.to_markdown()` risk-adjusted ranking metric key if empirical report output is misleading?** [VERIFIED: agent/backtest/strategies/comparison.py]
   - What we know: `ComparisonResult.to_markdown()` calls `get_ranking("sharpe")`, while `StrategyMetrics` stores `sharpe_ratio`. [VERIFIED: agent/backtest/strategies/comparison.py]
   - What's unclear: Whether current empirical output visibly mis-ranks that subsection. [ASSUMED]
   - Recommendation: Include a small conditional fix task only if artifact verification shows incorrect risk-adjusted ranking; otherwise avoid code changes. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backtest/reporting execution | ✓ | `Python 3.14.4` from `python3 --version`. [VERIFIED: Bash environment audit] | Project constraint says Python 3.11+. [CITED: /Users/iagent/projects/CLAUDE.md] |
| `.venv/bin/python` | Standard project command style | ✗ / not observed | No output in probe. [VERIFIED: Bash environment audit] | Use `python3`/create or locate venv before runs. [ASSUMED] |
| `pytest` on PATH | Validation Architecture | ✗ / not observed | No output in probe. [VERIFIED: Bash environment audit] | Use environment-specific `python -m pytest` after dependency setup. [ASSUMED] |
| `yfinance` | US futures/ETF live data | Unknown | Declared dependency only. [VERIFIED: pyproject.toml] | Use existing env or install from project dependency workflow if missing; do not add new package. [ASSUMED] |
| `akshare` | Daily no-auth fallback | Unknown | Declared dependency only. [VERIFIED: pyproject.toml] | Use only as daily fallback; not for 4H US futures. [VERIFIED: agent/backtest/loaders/akshare_loader.py] |
| `TUSHARE_TOKEN` | Tushare loader | Unknown | Env-only token. [VERIFIED: agent/backtest/loaders/tushare.py] | Avoid Tushare-dependent closure unless token exists. [ASSUMED] |
| `TQSDK_ACCOUNT` / `TQSDK_PASSWORD` | TqSdk loader | Unknown | Env-only credentials. [VERIFIED: agent/backtest/loaders/tqsdk_loader.py] | Avoid CN futures empirical closure unless credentials exist. [ASSUMED] |
| Local parquet data under `data/` | Watchlist health gate | Not found in probe | No cached data files printed. [VERIFIED: Bash data audit] | Use live loader runs and document local-cache absence. [ASSUMED] |

**Missing dependencies with no fallback:** none confirmed, but empirical execution is blocked until a working project Python environment with declared dependencies is available. [VERIFIED: Bash environment audit][ASSUMED]

**Missing dependencies with fallback:** `.venv/bin/python` and PATH `pytest` were not observed; fallback is to locate/create the project environment or use `python3 -m pytest` after dependencies are installed. [VERIFIED: Bash environment audit][ASSUMED]

## Validation Architecture

`.planning/config.json` was not found in this worktree, so Nyquist validation is treated as enabled by default. [VERIFIED: Read error]

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest declared in `pyproject.toml`; installed availability not confirmed in probe. [VERIFIED: pyproject.toml][VERIFIED: Bash environment audit] |
| Config file | `pyproject.toml` contains pytest config with `testpaths = ["agent/tests"]` and `pythonpath = ["agent"]`. [VERIFIED: pyproject.toml] |
| Quick run command | `python -m pytest -q agent/tests/test_composite_backtest_compare.py agent/tests/test_metrics.py agent/tests/test_watchlist_data_health.py` [VERIFIED: agent/tests/test_composite_backtest_compare.py][VERIFIED: agent/tests/test_metrics.py][VERIFIED: agent/tests/test_watchlist_data_health.py] |
| Full suite command | `python -m pytest -q` [VERIFIED: pyproject.toml] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DATA-01 | Config/run cards prove requested 2024-2026 date range. [VERIFIED: .planning/REQUIREMENTS.md] | artifact inspection + smoke | `python -m py_compile agent/backtest/runner.py agent/backtest/composite_backtest_compare.py` [ASSUMED] | ✅ code exists. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/composite_backtest_compare.py] |
| DATA-02 | Watchlist coverage and data-health output recorded. [VERIFIED: .planning/REQUIREMENTS.md] | script smoke | `python scripts/check_watchlist_data.py --watchlist watchlist/us_futures_watchlist.csv --data-dir data --format json` [VERIFIED: scripts/check_watchlist_data.py] | ✅ [VERIFIED: scripts/check_watchlist_data.py] |
| DATA-03 | `1D` and `4H` configs/runs attempted and recorded. [VERIFIED: .planning/REQUIREMENTS.md] | integration/artifact | Empirical run command per config. [ASSUMED] | ✅ runner supports intervals. [VERIFIED: agent/backtest/runner.py] |
| METR-01 | Composite vs single returns compared. [VERIFIED: .planning/REQUIREMENTS.md] | unit + artifact | `python -m pytest -q agent/tests/test_composite_backtest_compare.py` [VERIFIED: agent/tests/test_composite_backtest_compare.py] | ✅ [VERIFIED: agent/tests/test_composite_backtest_compare.py] |
| METR-02 | win rate, Sharpe, max drawdown metrics appear. [VERIFIED: .planning/REQUIREMENTS.md] | unit + artifact | `python -m pytest -q agent/tests/test_metrics.py` [VERIFIED: agent/tests/test_metrics.py] | ✅ [VERIFIED: agent/tests/test_metrics.py] |
| METR-03 | per-source signal breakdown appears. [VERIFIED: .planning/REQUIREMENTS.md] | artifact inspection | Check `signals_per_source.json` and report `Per-Source Performance (METR-03)` heading. [VERIFIED: agent/backtest/engines/base.py][VERIFIED: agent/backtest/reporting/composite_report.py] | ✅ code exists. [VERIFIED: agent/backtest/engines/base.py][VERIFIED: agent/backtest/reporting/composite_report.py] |
| RPT-01 | final report has composite-vs-single comparison. [VERIFIED: .planning/REQUIREMENTS.md] | artifact inspection | Check report heading `Strategy Comparison (RPT-01)`. [VERIFIED: agent/backtest/reporting/composite_report.py] | ✅ [VERIFIED: agent/backtest/reporting/composite_report.py] |
| RPT-02 | final report identifies best configuration. [VERIFIED: .planning/REQUIREMENTS.md] | artifact inspection | Check report heading `Best Configuration (RPT-02)`. [VERIFIED: agent/backtest/reporting/composite_report.py] | ✅ [VERIFIED: agent/backtest/reporting/composite_report.py] |
| RPT-03 | final report records data quality. [VERIFIED: .planning/REQUIREMENTS.md] | artifact inspection | Check report heading `Data Quality (RPT-03)` and health JSON. [VERIFIED: agent/backtest/reporting/composite_report.py][VERIFIED: scripts/check_watchlist_data.py] | ✅ [VERIFIED: agent/backtest/reporting/composite_report.py][VERIFIED: scripts/check_watchlist_data.py] |

### Sampling Rate

- **Per task commit:** run targeted pytest for touched module plus py_compile for runner/reporting files. [ASSUMED]
- **Per wave merge:** run targeted suite: `test_composite_backtest_compare.py`, `test_metrics.py`, `test_watchlist_data_health.py`, `test_backtest_runner_security.py`. [ASSUMED]
- **Phase gate:** empirical artifacts exist, final report headings exist, and `.planning/REQUIREMENTS.md` traceability maps each scoped requirement to artifact paths. [ASSUMED]

### Wave 0 Gaps

- [ ] Verify or restore a project Python environment with dependencies; `.venv/bin/python` was not observed. [VERIFIED: Bash environment audit]
- [ ] Add a small tested report-generation wrapper only if the planner does not extend an existing CLI. [ASSUMED]
- [ ] Add artifact inspection checks for report headings and required run-card files. [ASSUMED]

## Security Domain

Security enforcement is treated as enabled because `.planning/config.json` was absent. [VERIFIED: Read error]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No for core Phase 10 CLI execution. [ASSUMED] | Env-only handling for data-source credentials; do not commit tokens. [CITED: /Users/iagent/projects/CLAUDE.md][VERIFIED: agent/backtest/loaders/tushare.py][VERIFIED: agent/backtest/loaders/tqsdk_loader.py] |
| V3 Session Management | No. [ASSUMED] | Not applicable to batch backtest closure. [ASSUMED] |
| V4 Access Control | Yes for filesystem run roots. [VERIFIED: agent/src/tools/path_utils.py] | Use `safe_run_dir` and default allowed run roots. [VERIFIED: agent/src/tools/path_utils.py] |
| V5 Input Validation | Yes. [VERIFIED: agent/backtest/runner.py] | Use `BacktestConfigSchema`, safe YAML loading, and strategy-variant allowlists. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/composite_backtest_compare.py] |
| V6 Cryptography | Yes for integrity hashes, not encryption. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/run_card.py] | Trusted signal-engine SHA256 and run-card artifact hashes. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/run_card.py] |

### Known Threat Patterns for Phase 10 CLI/reporting

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted signal engine execution | Elevation of Privilege / Tampering | Use packaged trusted engine or configured SHA256 allowlist; do not disable trusted-engine verification. [VERIFIED: agent/backtest/runner.py][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md] |
| Run-root path traversal or artifact overwrite | Tampering | Use `safe_run_dir`; keep run roots under default allowed `agent/runs`. [VERIFIED: agent/src/tools/path_utils.py] |
| YAML/config injection | Tampering | Use existing `_load_config()` with JSON or `yaml.safe_load`. [VERIFIED: agent/backtest/composite_backtest_compare.py] |
| CSV formula injection in artifacts | Information Disclosure / Tampering | Preserve Phase 09 CSV safety controls. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md] |
| Hanging subprocesses or secret leakage in diagnostics | Denial of Service / Information Disclosure | Use comparison timeout argument and redacted/truncated subprocess output. [VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/tests/test_composite_backtest_compare.py] |
| Silent data-source degradation | Repudiation | Record run-card warnings, data sources, data-health JSON, and final RPT-03 notes. [VERIFIED: agent/backtest/run_card.py][VERIFIED: scripts/check_watchlist_data.py][VERIFIED: agent/backtest/reporting/composite_report.py] |

## What Phase 10 Must Not Include

| Exclusion | Reason |
|-----------|--------|
| Daily Scan Report UI/output | User said this belongs to Phase 11. [VERIFIED: user request] |
| New strategy scoring framework | User scoped Phase 10 to empirical evidence closure, not future scoring. [VERIFIED: user request] |
| Strategy parameter optimization/search | RPT-02 should identify the best among fixed variants, not create a tuning system. [VERIFIED: .planning/REQUIREMENTS.md][ASSUMED] |
| Production scheduler/automation | Closure phase only needs reproducible commands and artifacts. [VERIFIED: user request][ASSUMED] |
| New data-source integration | Existing loaders are sufficient to attempt evidence; new integrations would expand scope. [VERIFIED: agent/backtest/loaders/registry.py][ASSUMED] |
| Refactor of Phase 09 infrastructure | Phase 09 security/UAT already passed; only minimal fixes should be planned if artifact verification exposes a closure blocker. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-UAT.md][VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md] |

## Sources

### Primary (HIGH confidence)

- `/Users/iagent/projects/CLAUDE.md` — project constraints and workflow requirements. [CITED: /Users/iagent/projects/CLAUDE.md]
- `.planning/REQUIREMENTS.md` — scoped DATA/METR/RPT requirement text and Pending status. [VERIFIED: .planning/REQUIREMENTS.md]
- `.planning/ROADMAP.md` — v2.1 milestone structure and phase context. [VERIFIED: .planning/ROADMAP.md]
- `.planning/STATE.md` — current planning state and stale/inconsistent milestone information. [VERIFIED: .planning/STATE.md]
- `.planning/phases/09-composite-strategy-backtest/09-SUMMARY.md` — Phase 09 implementation summary and verification results. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SUMMARY.md]
- `.planning/phases/09-composite-strategy-backtest/09-UAT.md` — Phase 09 UAT pass evidence. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-UAT.md]
- `.planning/phases/09-composite-strategy-backtest/09-SECURITY.md` — Phase 09 security closure and threat controls. [VERIFIED: .planning/phases/09-composite-strategy-backtest/09-SECURITY.md]
- `agent/backtest/runner.py` — runner schema, data loading, trusted engine, data limits, artifact execution path. [VERIFIED: agent/backtest/runner.py]
- `agent/backtest/composite_backtest_compare.py` — empirical comparison orchestrator. [VERIFIED: agent/backtest/composite_backtest_compare.py]
- `agent/backtest/reporting/composite_report.py` — final report API and RPT/METR sections. [VERIFIED: agent/backtest/reporting/composite_report.py]
- `agent/backtest/metrics.py` — metrics and per-source/equity quality helpers. [VERIFIED: agent/backtest/metrics.py]
- `agent/backtest/run_card.py` — reproducibility metadata and artifact hashing. [VERIFIED: agent/backtest/run_card.py]
- `agent/backtest/engines/base.py` — backtest artifact writer. [VERIFIED: agent/backtest/engines/base.py]
- `agent/src/data/watchlist_data_health.py` and `scripts/check_watchlist_data.py` — data-health gate logic and CLI. [VERIFIED: agent/src/data/watchlist_data_health.py][VERIFIED: scripts/check_watchlist_data.py]
- `watchlist/us_futures_watchlist.csv`, `watchlist/etf_watchlist.csv`, `watchlist/cn_futures_watchlist.csv` — watchlist coverage and declared timeframes. [VERIFIED: watchlist/us_futures_watchlist.csv][VERIFIED: watchlist/etf_watchlist.csv][VERIFIED: watchlist/cn_futures_watchlist.csv]

### Secondary (MEDIUM confidence)

- Existing local reports `data_quality_report_20260524_122047.txt`, `data_quality_report_20260524_122250.txt`, `watchlist_report.md`, `etf_report.md` — historical context, not closure evidence. [VERIFIED: data_quality_report_20260524_122047.txt][VERIFIED: data_quality_report_20260524_122250.txt][VERIFIED: watchlist_report.md][VERIFIED: etf_report.md]
- `scripts/backtest_composite_strategy.py` and `scripts/backtest_trend_indicators.py` — older or adjacent empirical/reporting patterns that should not replace runner-based closure. [VERIFIED: scripts/backtest_composite_strategy.py][VERIFIED: scripts/backtest_trend_indicators.py]

### Tertiary (LOW confidence)

- Live yfinance provider retention behavior and network/proxy reliability were not verified by executing live data fetches in this session. [ASSUMED]
- Minimum acceptable watchlist coverage for DATA-02 was not explicitly defined beyond “main watchlist instruments.” [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for repository modules; MEDIUM for installed dependency availability because `.venv`/pytest were not observed. [VERIFIED: codebase Read][VERIFIED: Bash environment audit]
- Architecture: HIGH for existing runner/comparison/report pipeline; MEDIUM for suggested helper/wave artifacts because they are planning recommendations. [VERIFIED: agent/backtest/runner.py][VERIFIED: agent/backtest/composite_backtest_compare.py][VERIFIED: agent/backtest/reporting/composite_report.py][ASSUMED]
- Pitfalls: MEDIUM-HIGH for code-derived pitfalls; LOW-MEDIUM for live data retention because no live fetch was executed. [VERIFIED: codebase Read][ASSUMED]

**Research date:** 2026-06-07  
**Valid until:** 2026-07-07 for repository architecture; 2026-06-14 for live data availability assumptions. [ASSUMED]
